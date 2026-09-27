"""Имя владельца ORCID из публичного API — для дедупликации (#118).

OpenAlex приклеивает ORCID к чужим профилям: у `A5055386468` (N. A. Usachev,
МИФИ) ORCID записан на «Nikita Usachev», хотя в работах профиля автор подписан
«Николай Александрович Усачев». Такой ORCID нельзя считать доказательством,
что у пары «разные ORCID» — два человека. Здесь только чтение публичной записи
(`pub.orcid.org`, без ключа) и сравнение имени с профилем; что делать с парой,
решает `dedup.find_splits`.

Ответы кэшируются на диске по образцу клиента OpenAlex (ключ — sha256 от URL,
файл в `data/raw`): повторный прогон в сеть не ходит, на один ORCID — не больше
одного запроса за всё время жизни кэша.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import structlog

from sfr_core.models import Author
from sfr_etl.dedup import first_names_conflict, full_first_name, normalize_orcid, same_surname

log = structlog.get_logger(__name__)

ORCID_PERSON_URL = "https://pub.orcid.org/v3.0/{orcid}/person"


@dataclass(frozen=True)
class OrcidName:
    """Имя в записи ORCID: имя, фамилия и «имя для цитирования», если есть."""

    given: str
    family: str
    credit: str = ""

    @property
    def full(self) -> str:
        return f"{self.given} {self.family}".strip()


def parse_person(payload: dict[str, Any]) -> OrcidName | None:
    """Ответ `/v3.0/<orcid>/person` → имя; скрытое владельцем имя → None."""
    name = payload.get("name") or {}

    def value(key: str) -> str:
        return str(((name.get(key) or {}).get("value")) or "").strip()

    record = OrcidName(value("given-names"), value("family-name"), value("credit-name"))
    return record if record.given or record.family else None


class OrcidClient:
    """Публичный API ORCID с дисковым кэшем; считает запросы и попадания в кэш."""

    def __init__(
        self, cache_dir: Path = Path("data/raw"), http: httpx.Client | None = None
    ) -> None:
        self.cache_dir = cache_dir
        self.http = http or httpx.Client(timeout=15.0, headers={"Accept": "application/json"})
        self.n_requests = 0
        self.n_cache_hits = 0

    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / f"{hashlib.sha256(url.encode()).hexdigest()}.json"

    def person(self, orcid: str) -> dict[str, Any] | None:
        normalized = normalize_orcid(orcid)
        if not normalized:
            return None
        url = ORCID_PERSON_URL.format(orcid=normalized)
        cache_file = self._cache_path(url)
        if cache_file.exists():
            self.n_cache_hits += 1
            envelope = json.loads(cache_file.read_text(encoding="utf-8"))
            data: dict[str, Any] | None = envelope.get("data")
            return data
        self.n_requests += 1
        response = self.http.get(url, headers={"Accept": "application/json"})
        data = response.json() if response.status_code == 200 else None
        if response.status_code not in (200, 404):
            # Временную ошибку не кэшируем: иначе «нет записи» застынет навсегда.
            log.warning("orcid_http_error", orcid=normalized, status=response.status_code)
            return None
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        envelope = {
            "url": url,
            "fetched_at": datetime.now(UTC).isoformat(),
            "status": response.status_code,
            "data": data,
        }
        cache_file.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")
        return data

    def name(self, orcid: str) -> OrcidName | None:
        payload = self.person(orcid)
        return parse_person(payload) if payload else None


def profile_names(author: Author) -> list[str]:
    """Имя профиля и все его варианты из OpenAlex (`display_name_alternatives`)."""
    alternatives = (author.raw or {}).get("display_name_alternatives") or []
    return [author.display_name, *(str(a) for a in alternatives if a)]


def orcid_on_another_name(record: OrcidName, author: Author) -> bool:
    """ORCID записан на другого человека, а не на владельца профиля.

    Фамилия записи не совпадает с фамилией профиля — чужой. Фамилия та же, но
    имя записи спорит со **всеми** развёрнутыми именами профиля (Nikita против
    Николай / Nikolai) — тоже чужой. Если развёрнутых имён у профиля нет, судить
    не по чему — не чужой: инициалы с именем не спорят.
    """
    if record.family and not same_surname(record.full, author.display_name):
        return True
    if not record.given:
        return False
    spelled = [name for name in profile_names(author) if full_first_name(name)]
    return bool(spelled) and all(first_names_conflict(record.full, name) for name in spelled)


def foreign_orcid_note(client: OrcidClient) -> Callable[[Author], str | None]:
    """Для `find_splits`: пометка, если ORCID профиля записан на другое имя."""

    def note(author: Author) -> str | None:
        orcid = normalize_orcid(author.orcid)
        if not orcid:
            return None
        record = client.name(orcid)
        if record is None or not orcid_on_another_name(record, author):
            return None
        return f"ORCID {orcid} записан на другое имя («{record.full}» при «{author.display_name}»)"

    return note
