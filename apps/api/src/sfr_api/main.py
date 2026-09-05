"""FastAPI application: three endpoints over one preloaded index (SPEC_SFR2 §2)."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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


def _service(request: Request) -> MatchService:
    service: MatchService = request.app.state.service
    return service


@router.post("/match", response_model=MatchResponse)
async def match(request: Request, body: MatchRequest) -> MatchResponse:
    """Find supervisors for a free-text description of research interests.

    CPU inference is guarded: at most ``match_concurrency`` encodes run at once,
    ``match_queue_limit`` more wait on the semaphore, the rest get an honest 503
    instead of thrashing the model (REVIEW_SFR3 Medium). The counter is safe
    without a lock — the event loop is single-threaded and there is no await
    between the check and the increment.
    """
    state = request.app.state
    settings: ApiSettings = state.settings
    if state.match_inflight >= settings.match_concurrency + settings.match_queue_limit:
        raise HTTPException(
            status_code=503,
            detail="Сервис перегружен, запрос не принят. Попробуйте через минуту.",
        )
    state.match_inflight += 1
    try:
        async with state.match_semaphore:
            try:
                return await run_in_threadpool(_service(request).match, body.query, body.k)
            except QueryError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        state.match_inflight -= 1


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
        yield

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
