"""Server-authoritative facts and explicit private context allowlist."""

import ipaddress
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID, uuid4

from fastapi import Request

from sfr_api.schemas import MatchResponse
from sfr_api.settings import ApiSettings


def identifier(value: str | None) -> str:
    try:
        return str(UUID(value or ""))
    except ValueError:
        return str(uuid4())


def safe_url(value: str | None) -> str | None:
    """Never retain URL credentials, query parameters, or fragments."""
    if not value or len(value) > 4096:
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"", "http", "https"}:
            return None
        host = parsed.hostname or ""
        if parsed.port:
            host += f":{parsed.port}"
        return urlunsplit((parsed.scheme, host, parsed.path, "", ""))[:2048]
    except ValueError:
        return None


def client_ip(request: Request, settings: ApiSettings) -> str | None:
    peer = request.client.host if request.client else ""
    try:
        address = ipaddress.ip_address(peer)
        trusted = any(
            address in ipaddress.ip_network(cidr) for cidr in settings.analytics_trusted_proxy_cidrs
        )
        # This header is overwritten by the trusted gateway and forwarded by Next.
        forwarded = request.headers.get("x-sfr-client-ip") if trusted else None
        return str(ipaddress.ip_address(forwarded or peer))
    except ValueError:
        return None


def traffic_type(request: Request) -> str:
    agent = request.headers.get("user-agent", "")[:512]
    if re.search(r"SFR-(Rehearsal|Technical)", agent, re.I):
        return "declared_technical"
    if re.search(r"bot|crawler|spider", agent, re.I):
        return "suspected_bot"
    return "unclassified"


def private_context(request: Request) -> dict[str, Any]:
    return {
        "raw_ip": client_ip(request, request.app.state.settings),
        "url": safe_url(request.headers.get("x-sfr-page-url")),
        "referer": safe_url(request.headers.get("x-sfr-referer")),
        "diagnostic_headers": {
            name: request.headers[name][:512]
            for name in ("user-agent", "accept-language")
            if name in request.headers
        },
    }


def search_record(
    request: Request,
    query: str,
    k: int | None,
    *,
    status: int,
    response: MatchResponse | None = None,
    cache_hit: bool = False,
    wall_ms: float = 0,
    error: str | None = None,
) -> dict[str, Any]:
    settings: ApiSettings = request.app.state.settings
    service = request.app.state.service
    meta = service.backend.meta
    payload: dict[str, Any] = {
        "schema_version": 1,
        "app_version": settings.analytics_release,
        "model": meta.hf_id or meta.model_key,
        "index_version": meta.version,
        "cache_hit": cache_hit,
        "wall_ms": round(wall_ms, 3),
        "k": k if k is not None else settings.default_k,
        "thresholds": {
            "none": settings.score_threshold,
            "weak": settings.score_weak,
            "high": settings.score_high,
        },
        "error": error,
        "traffic_type": traffic_type(request),
    }
    if response:
        payload.update(
            {
                "confidence": response.confidence,
                "took_ms": response.took_ms,
                "results": [
                    {
                        "author_id": hit.author_id,
                        "score": hit.score,
                        "rank": hit.rank,
                        "grade": hit.grade,
                    }
                    for hit in response.results
                ],
            }
        )
        # Backward-compatible successful /match JSONL record retained in export.
        payload["legacy"] = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "ip_hash": request.state.ip_hash,
            "query_len": len(query.strip()),
            "top1_score": round(response.results[0].score, 4) if response.results else None,
            "confidence": response.confidence,
            "below_threshold": response.below_threshold,
            "cache_hit": cache_hit,
            "took_ms": response.took_ms,
            "wall_ms": round(wall_ms, 1),
            "model": payload["model"],
            "index_version": response.index_version,
        }
    return {
        "search": {
            "search_id": request.state.search_id,
            "request_id": request.state.request_id,
            "visit_id": request.state.visit_id,
            "received_at": request.state.received_at,
            "completed_at": datetime.now(UTC).isoformat(),
            "status": status,
            "outcome": "success" if status == 200 else "error",
            "payload": payload,
        },
        "context": {
            "search_id": request.state.search_id,
            "raw_query": query,
            "normalized_query": query.strip(),
            **private_context(request),
        },
    }
