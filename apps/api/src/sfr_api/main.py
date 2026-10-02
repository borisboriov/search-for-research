"""FastAPI application: three endpoints over one preloaded index (SPEC_SFR2 §2)."""

import asyncio
import hashlib
import json
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.responses import Response

from sfr_api.analytics.capture import (
    client_ip,
    identifier,
    private_context,
    search_record,
    traffic_type,
)
from sfr_api.analytics.contracts import EventBatch
from sfr_api.analytics.store import DurableStore, StorageUnavailable
from sfr_api.schemas import (
    HealthResponse,
    MatchRequest,
    MatchResponse,
    SupervisorCard,
    SupervisorsPage,
)
from sfr_api.service import MatchService, QueryError
from sfr_api.settings import ApiSettings

router = APIRouter(prefix="/api")

# Legacy successful /match JSONL output remains compatible. Durable history lives
# in the private analytics journal/PostgreSQL; Docker stdout rotation is not retention.
match_logger = logging.getLogger("sfr_api.match")
if not match_logger.handlers:  # uvicorn конфигурирует только свои логгеры
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    match_logger.addHandler(_handler)
    match_logger.setLevel(logging.INFO)
    match_logger.propagate = False


def _service(request: Request) -> MatchService:
    service: MatchService = request.app.state.service
    return service


def _ip_hash(request: Request, salt: str) -> str:
    """Сырой IP в лог не попадает: sha256(соль + IP), первые 16 hex.

    Forwarded IP принимается только от настроенной доверенной цепочки;
    иначе берём адрес соединения. Пустая соль оставляет IPv4 перебираемым — на сервере
    задаётся SFR_API_LOG_SALT.
    """
    settings: ApiSettings = request.app.state.settings
    ip = client_ip(request, settings) or ""
    if not ip:
        return ""
    return hashlib.sha256((salt + ip).encode()).hexdigest()[:16]


def _log_match(
    request: Request, query: str, response: MatchResponse, *, cache_hit: bool, wall_ms: float
) -> None:
    service = _service(request)
    settings: ApiSettings = request.app.state.settings
    record = {
        "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
        "ip_hash": _ip_hash(request, settings.log_salt),
        "query": query,
        "query_len": len(query),
        "top1_score": round(response.results[0].score, 4) if response.results else None,
        "confidence": response.confidence,
        "below_threshold": response.below_threshold,
        "cache_hit": cache_hit,
        "took_ms": response.took_ms,
        "wall_ms": round(wall_ms, 1),
        "model": service.backend.meta.hf_id or service.backend.meta.model_key,
        "index_version": response.index_version,
    }
    match_logger.info(json.dumps(record, ensure_ascii=False))


async def _capture(request: Request, record: dict[str, Any]) -> bool:
    store: DurableStore | None = request.app.state.analytics
    if store is None:
        return False
    try:
        # A stalled disk must not indefinitely delay search. The bounded thread
        # completes if the disk recovers; a timeout is an honest diagnostic gap.
        await asyncio.wait_for(run_in_threadpool(store.append, "search", [record]), timeout=0.25)
        return True
    except (StorageUnavailable, TimeoutError, OSError):
        logging.getLogger("sfr_api.analytics").error("analytics search capture unavailable")
        request.app.state.analytics_capture_failures += 1
        return False


@router.post("/events")
async def events(request: Request) -> dict[str, list[str]]:
    # Stream and bound before parsing, including when Content-Length is absent.
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > 16384:
            raise HTTPException(status_code=413, detail="Event batch exceeds 16 KiB")
    try:
        batch = EventBatch.model_validate_json(content)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid event contract") from None
    store: DurableStore | None = request.app.state.analytics
    if store is None:
        raise HTTPException(status_code=503, detail="Analytics unavailable")
    received_at = datetime.now(UTC).isoformat()
    release = request.app.state.settings.analytics_release
    records = [
        event.model_dump(mode="json", exclude_none=True)
        | {"received_at": received_at, "app_version": release}
        for event in batch.events
    ]
    # Nullable fields must exist for DB insert; nested optional data stays sparse.
    for record in records:
        record.setdefault("search_id", None)
        record.setdefault("request_id", None)
        record["traffic_type"] = traffic_type(request)
        record["private_context"] = private_context(request) | {"event_id": record["event_id"]}
    try:
        await asyncio.wait_for(run_in_threadpool(store.append, "events", records), timeout=0.5)
    except (StorageUnavailable, OSError, TimeoutError):
        raise HTTPException(
            status_code=503, detail="Analytics could not be durably saved"
        ) from None
    return {"accepted": [str(event.event_id) for event in batch.events]}


@router.post("/match", response_model=MatchResponse)
async def match(request: Request, body: MatchRequest) -> MatchResponse:
    """Search behavior is unchanged; analytics records server facts separately."""
    state = request.app.state
    settings: ApiSettings = state.settings
    started = time.perf_counter()
    if state.match_inflight >= settings.match_concurrency + settings.match_queue_limit:
        await _capture(
            request, search_record(request, body.query, body.k, status=503, error="overloaded")
        )
        raise HTTPException(
            status_code=503, detail="Сервис перегружен, запрос не принят. Попробуйте через минуту."
        )
    state.match_inflight += 1
    try:
        async with state.match_semaphore:
            try:
                response, cache_hit = await run_in_threadpool(
                    _service(request).match_cached, body.query, body.k
                )
            except QueryError as exc:
                await _capture(
                    request,
                    search_record(
                        request,
                        body.query,
                        body.k,
                        status=422,
                        wall_ms=(time.perf_counter() - started) * 1000,
                        error="validation",
                    ),
                )
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            except Exception:
                await _capture(
                    request,
                    search_record(
                        request,
                        body.query,
                        body.k,
                        status=500,
                        wall_ms=(time.perf_counter() - started) * 1000,
                        error="internal",
                    ),
                )
                # Do not leak exception strings or user query through diagnostics.
                raise HTTPException(
                    status_code=500, detail="Search temporarily unavailable"
                ) from None
    finally:
        state.match_inflight -= 1
    wall_ms = (time.perf_counter() - started) * 1000
    await _capture(
        request,
        search_record(
            request,
            body.query,
            body.k,
            status=200,
            response=response,
            cache_hit=cache_hit,
            wall_ms=wall_ms,
        ),
    )
    _log_match(request, body.query.strip(), response, cache_hit=cache_hit, wall_ms=wall_ms)
    return response


@router.get("/supervisors", response_model=SupervisorsPage)
def supervisors(
    request: Request, limit: int | None = None, cursor: str | None = None
) -> SupervisorsPage:
    """Paginated catalogue listing: author_id + name + institution (sitemap, previews)."""
    service = _service(request)
    settings: ApiSettings = request.app.state.settings
    limit = settings.list_default_limit if limit is None else limit
    if limit < 1 or limit > settings.list_max_limit:
        raise HTTPException(
            status_code=422,
            detail=f"limit должен быть от 1 до {settings.list_max_limit}, получено {limit}.",
        )
    try:
        return service.list_supervisors(limit, cursor)
    except QueryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/supervisors/{author_id}", response_model=SupervisorCard)
def supervisor(request: Request, author_id: str) -> SupervisorCard:
    """One open supervisor card by OpenAlex author id."""
    card = _service(request).card(author_id)
    if card is None:
        raise HTTPException(status_code=404, detail=f"НР с id {author_id} нет в индексе.")
    return card


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    """Which model and which index this process actually serves."""
    return _service(request).health()


def create_app(settings: ApiSettings | None = None, service: MatchService | None = None) -> FastAPI:
    """Build the app. ``service`` is injected by tests so no model is ever loaded there."""
    settings = settings or ApiSettings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Model + index are loaded once here, warmed up, and reused by every request.
        # An injected service (tests) is kept as it is — nothing is loaded then.
        if app.state.service is None:
            app.state.service = MatchService.from_settings(settings)
        task = None
        if settings.analytics_database_url:
            try:
                app.state.analytics = DurableStore(
                    settings.analytics_database_url,
                    settings.analytics_spool_dir,
                    max_bytes=settings.analytics_spool_max_bytes,
                    reserve_bytes=settings.analytics_disk_reserve_bytes,
                )

                async def replay() -> None:
                    while True:
                        try:
                            await run_in_threadpool(app.state.analytics.replay)
                        except Exception:
                            logging.getLogger("sfr_api.analytics").error(
                                "analytics replay unavailable"
                            )
                        await asyncio.sleep(settings.analytics_replay_seconds)

                task = asyncio.create_task(replay())
            except OSError:
                logging.getLogger("sfr_api.analytics").error(
                    "analytics journal startup unavailable"
                )
        try:
            yield
        finally:
            if task:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            if app.state.analytics:
                app.state.analytics.engine.dispose()

    app = FastAPI(
        title="Search For Research — match API",
        version="0.2.0",
        summary="Подбор научных руководителей по описанию интересов (SFR-2)",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.service = service
    app.state.match_semaphore = asyncio.Semaphore(settings.match_concurrency)
    app.state.match_inflight = 0
    app.state.analytics = None
    app.state.analytics_capture_failures = 0

    @app.middleware("http")
    async def request_identity(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = identifier(request.headers.get("x-request-id"))
        request.state.search_id = identifier(request.headers.get("x-sfr-search-id"))
        visit = request.headers.get("x-sfr-visit-id")
        request.state.visit_id = identifier(visit) if visit else None
        request.state.received_at = datetime.now(UTC).isoformat()
        request.state.ip_hash = _ip_hash(request, settings.log_salt)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def _human_422(request: Request, exc: Exception) -> JSONResponse:
        """FastAPI's default 422 body is a list of pydantic errors — say it in words."""
        if request.url.path == "/api/match" and isinstance(exc, RequestValidationError):
            body = exc.body
            if isinstance(body, dict) and isinstance(body.get("query"), str):
                query = body["query"]
                if len(query) <= 2000:
                    k = body.get("k") if isinstance(body.get("k"), int) else None
                    await _capture(
                        request,
                        search_record(request, query, k, status=422, error="schema_validation"),
                    )
        errors = exc.errors() if isinstance(exc, RequestValidationError) else []
        fields = ", ".join(str(error["loc"][-1]) for error in errors) or "тело запроса"
        # На GET нет JSON-тела — подсказка про него только сбивает (REVIEW_SFR3 Low)
        hint = (
            "Проверьте query-параметры запроса."
            if request.method == "GET"
            else 'Ожидается JSON вида {"query": "описание интересов", "k": 10}.'
        )
        detail = f"Запрос не прошёл проверку ({fields}). {hint}"
        return JSONResponse(status_code=422, content={"detail": detail})

    app.include_router(router)
    return app


app = create_app  # uvicorn factory target: `uvicorn sfr_api.main:app --factory`
