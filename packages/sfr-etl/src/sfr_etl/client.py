"""OpenAlex API client: polite pool, rate limiting, retries, disk cache."""

import hashlib
import json
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
import structlog
from tenacity import (
    RetryCallState,
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

log = structlog.get_logger(__name__)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class RetryableStatusError(Exception):
    """HTTP status worth retrying (429/5xx); carries Retry-After when the server sent it."""

    def __init__(self, status_code: int, retry_after: float | None = None) -> None:
        super().__init__(f"OpenAlex returned HTTP {status_code}")
        self.status_code = status_code
        self.retry_after = retry_after


def _is_retryable(exc: BaseException) -> bool:
    return isinstance(exc, RetryableStatusError | httpx.TransportError)


class OpenAlexClient:
    """Synchronous OpenAlex client.

    - always sends ``mailto`` (polite pool)
    - <= ``max_rps`` requests per second
    - exponential-backoff retries on 429/5xx, honouring ``Retry-After``
    - disk cache of raw responses keyed by hash of URL+params (``refresh`` bypasses reads)
    """

    def __init__(
        self,
        mailto: str,
        *,
        base_url: str = "https://api.openalex.org",
        max_rps: float = 10.0,
        cache_dir: Path = Path("data/raw"),
        refresh: bool = False,
        http_client: httpx.Client | None = None,
        max_attempts: int = 5,
        backoff_max: float = 30.0,
    ) -> None:
        if not mailto or "@" not in mailto:
            raise ValueError("OpenAlexClient requires a valid mailto (polite pool)")
        self.mailto = mailto
        self.base_url = base_url.rstrip("/")
        self.cache_dir = cache_dir
        self.refresh = refresh
        self._min_interval = 1.0 / max_rps if max_rps > 0 else 0.0
        self._last_request_at = 0.0
        self._http = http_client or httpx.Client(timeout=30.0)
        self._max_attempts = max_attempts
        self._backoff_max = backoff_max
        self.n_network_requests = 0
        self.n_cache_hits = 0

    # -- cache ---------------------------------------------------------------

    def _cache_key(self, path: str, params: dict[str, Any]) -> str:
        # mailto is excluded: it does not affect the response content.
        cacheable = {k: v for k, v in params.items() if k != "mailto"}
        raw = f"{path}?{urlencode(sorted(cacheable.items()))}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def _cache_read(self, key: str) -> dict[str, Any] | None:
        cache_file = self._cache_path(key)
        if not cache_file.exists():
            return None
        try:
            envelope = json.loads(cache_file.read_text(encoding="utf-8"))
            body: dict[str, Any] = envelope["body"]
            return body
        except (json.JSONDecodeError, KeyError):
            log.warning("cache_corrupted", file=str(cache_file))
            return None

    def _cache_write(
        self, key: str, path: str, params: dict[str, Any], body: dict[str, Any]
    ) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        envelope = {
            "path": path,
            "params": {k: v for k, v in params.items() if k != "mailto"},
            "body": body,
        }
        self._cache_path(key).write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")

    # -- network -------------------------------------------------------------

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_at = time.monotonic()

    def _wait_strategy(self, retry_state: RetryCallState) -> float:
        exc = retry_state.outcome.exception() if retry_state.outcome else None
        if isinstance(exc, RetryableStatusError) and exc.retry_after is not None:
            return min(exc.retry_after, self._backoff_max)
        return float(wait_exponential(multiplier=0.5, max=self._backoff_max)(retry_state))

    def _fetch(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        retrying = Retrying(
            retry=retry_if_exception(_is_retryable),
            stop=stop_after_attempt(self._max_attempts),
            wait=self._wait_strategy,
            reraise=True,
        )
        for attempt in retrying:
            with attempt:
                self._throttle()
                self.n_network_requests += 1
                response = self._http.get(f"{self.base_url}{path}", params=params)
                if response.status_code in RETRYABLE_STATUS_CODES:
                    retry_after_header = response.headers.get("Retry-After")
                    retry_after = None
                    if retry_after_header is not None:
                        try:
                            retry_after = float(retry_after_header)
                        except ValueError:
                            retry_after = None
                    raise RetryableStatusError(response.status_code, retry_after)
                response.raise_for_status()
                result: dict[str, Any] = response.json()
                return result
        raise AssertionError("unreachable")  # pragma: no cover

    # -- public API ----------------------------------------------------------

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET a JSON endpoint, cache-aware. ``mailto`` is always attached."""
        params = dict(params or {})
        params["mailto"] = self.mailto
        key = self._cache_key(path, params)
        if not self.refresh:
            cached = self._cache_read(key)
            if cached is not None:
                self.n_cache_hits += 1
                return cached
        body = self._fetch(path, params)
        self._cache_write(key, path, params, body)
        return body

    def paginate(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        per_page: int = 200,
        max_records: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Iterate over list-endpoint records using cursor pagination."""
        params = dict(params or {})
        params["per-page"] = per_page
        cursor: str | None = "*"
        yielded = 0
        while cursor:
            page = self.get(path, {**params, "cursor": cursor})
            for record in page.get("results", []):
                yield record
                yielded += 1
                if max_records is not None and yielded >= max_records:
                    return
            cursor = page.get("meta", {}).get("next_cursor")
