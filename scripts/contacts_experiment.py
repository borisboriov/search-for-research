"""SFR-5 §5: сколько адресов НР удаётся получить легально — только измерение.

Продуктовый факт SFR-3: email нет ни у одного профиля каталога (в OpenAlex его
нет вовсе). Эксперимент меряет достижимость трёх источников на случайной выборке
профилей нового корпуса:

а) **ORCID public record** — публичный API, ключа не требует; адрес виден, только
   если владелец сам выставил ему видимость «public»;
б) **email корреспондирующего автора из метаданных публикаций** — Crossref по DOI
   работ (сами DOI берутся из ORCID-записи, чтобы не тратить бюджет OpenAlex);
в) **страницы вуза** — вручную, вне этого скрипта (SPEC_SFR5 §5 запрещает
   краулер); скрипт только готовит выборку из 10 профилей для ручной проверки.

**Найденные адреса в каталог не пишутся.** Сырой результат (с адресами) кладётся
в ``data/`` — это персональные данные, каталог и git их не видят; наружу идут
только проценты.
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select

from sfr_core.db import make_engine, session_scope
from sfr_core.models import Author
from sfr_core.settings import get_settings
from sfr_etl.dedup import normalize_orcid

ORCID_API = "https://pub.orcid.org/v3.0"
CROSSREF_API = "https://api.crossref.org/works"
DEFAULT_OUT = Path("data/experiments/contacts_sfr5.json")
SAMPLE_SIZE = 50
MANUAL_SAMPLE = 10
CROSSREF_DOIS_PER_AUTHOR = 3
SEED = 20260905


def sample_authors(n: int, seed: int) -> list[dict[str, Any]]:
    settings = get_settings()
    engine = make_engine(settings.sfr_db_url)
    with session_scope(engine) as session:
        rows = [
            {
                "author_id": author.openalex_id,
                "name": author.display_name,
                "orcid": normalize_orcid(author.orcid),
                "institution": (
                    None
                    if author.institution is None
                    else (author.institution.name_ru or author.institution.name_en)
                ),
            }
            for author in session.execute(
                select(Author)
                .where(Author.is_supervisor_candidate.is_(True), Author.merged_into_id.is_(None))
                .order_by(Author.openalex_id)
            ).scalars()
        ]
    return random.Random(seed).sample(rows, n)


def orcid_emails(client: httpx.Client, orcid: str) -> list[str]:
    response = client.get(f"{ORCID_API}/{orcid}/email", headers={"Accept": "application/json"})
    response.raise_for_status()
    return [
        entry["email"]
        for entry in response.json().get("email", [])
        if entry.get("email") and entry.get("visibility") == "public"
    ]


def orcid_dois(client: httpx.Client, orcid: str, limit: int) -> list[str]:
    response = client.get(f"{ORCID_API}/{orcid}/works", headers={"Accept": "application/json"})
    response.raise_for_status()
    dois: list[str] = []
    for group in response.json().get("group", []):
        for external in (group.get("external-ids") or {}).get("external-id", []):
            if external.get("external-id-type") == "doi" and external.get("external-id-value"):
                dois.append(str(external["external-id-value"]))
        if len(dois) >= limit:
            break
    return dois[:limit]


def crossref_emails(client: httpx.Client, doi: str) -> list[str]:
    """Есть ли в метаданных Crossref адрес хоть какого-нибудь автора."""
    response = client.get(f"{CROSSREF_API}/{doi}")
    if response.status_code != 200:
        return []
    message = response.json().get("message", {})
    found: list[str] = []
    for author in message.get("author", []):
        for key in ("email", "e-mail", "ORCID-email"):
            if author.get(key):
                found.append(str(author[key]))
    return found


def run(sample_size: int, out_path: Path, mailto: str) -> dict[str, Any]:
    authors = sample_authors(sample_size, SEED)
    headers = {"User-Agent": f"search-for-research/0.1 (mailto:{mailto})"}
    results: list[dict[str, Any]] = []
    started = time.monotonic()
    with httpx.Client(timeout=30.0, headers=headers, follow_redirects=True) as client:
        for i, author in enumerate(authors, start=1):
            record: dict[str, Any] = dict(author, orcid_emails=[], dois=[], crossref_emails=[])
            if author["orcid"]:
                try:
                    record["orcid_emails"] = orcid_emails(client, author["orcid"])
                    record["dois"] = orcid_dois(client, author["orcid"], CROSSREF_DOIS_PER_AUTHOR)
                except httpx.HTTPError as exc:
                    record["orcid_error"] = str(exc)
                for doi in record["dois"]:
                    try:
                        record["crossref_emails"] += crossref_emails(client, doi)
                    except httpx.HTTPError as exc:  # pragma: no cover — сеть
                        record.setdefault("crossref_error", str(exc))
            results.append(record)
            print(f"{i}/{len(authors)} {author['author_id']}", file=sys.stderr, flush=True)

    elapsed = time.monotonic() - started
    with_orcid = [r for r in results if r["orcid"]]
    payload = {
        "sample_size": len(results),
        "seed": SEED,
        "seconds_total": round(elapsed, 1),
        "seconds_per_profile": round(elapsed / max(len(results), 1), 2),
        "with_orcid": len(with_orcid),
        "orcid_email_found": sum(1 for r in results if r["orcid_emails"]),
        "dois_checked": sum(len(r["dois"]) for r in results),
        "crossref_email_found": sum(1 for r in results if r["crossref_emails"]),
        "manual_sample": [
            {"author_id": r["author_id"], "name": r["name"], "institution": r["institution"]}
            for r in results[:MANUAL_SAMPLE]
        ],
        # Персональные данные: файл живёт в data/ (gitignored) и наружу не идёт.
        "raw": results,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=int, default=SAMPLE_SIZE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    payload = run(args.sample, args.out, get_settings().openalex_mailto)
    summary = {k: v for k, v in payload.items() if k not in {"raw", "manual_sample"}}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"сырой результат (с адресами, не для git): {args.out}")


if __name__ == "__main__":
    main()
