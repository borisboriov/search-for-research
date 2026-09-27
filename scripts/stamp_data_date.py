"""Проштамповать дату данных каталога в meta.json собранного индекса (#16).

Плашка профиля «Данные: OpenAlex · обновлено <дата>» показывала `built_at` —
момент сборки индекса, а посетитель читает её как «когда обновились данные о
человеке». Даты расходятся при первой пересборке индекса без доливки данных.

Какая дата. Самая свежая `updated_date` записи OpenAlex среди авторов каталога
(`authors.raw`): это дата, по состоянию на которую OpenAlex отдал данные, и
меняется она только с новыми данными. Не `authors.fetched_at`: его пишет
upsert, в том числе из дискового кэша без единого запроса к OpenAlex (каталог
SFR-5c собран из кэша целиком), и он показал бы свежесть, которой нет. Работы
своей даты выгрузки в БД не хранят; их кэш догревался и позже, так что дата —
нижняя граница свежести, а не верхняя (решение — `docs/DECISIONS.md` 27.09).

Штамп в meta.json, а не расчёт в API: у контейнера API нет БД, только индекс.
Пересборка индекса без новых данных даёт ту же дату; новая выкачка — новую.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from sfr_core.db import make_engine, session_scope
from sfr_core.models import Author
from sfr_match.index import stamp_data_updated_at


def latest_update(raws: Iterable[dict[str, Any] | None]) -> str | None:
    """Самая свежая дата `updated_date` (YYYY-MM-DD) среди сырых записей авторов."""
    dates = [
        str(raw["updated_date"])[:10]
        for raw in raws
        if raw and isinstance(raw.get("updated_date"), str) and raw["updated_date"]
    ]
    return max(dates) if dates else None


def catalogue_data_date(session: Session) -> str | None:
    """Дата данных каталога: кандидаты в НР, не выбывшие в склейку."""
    raws = session.execute(
        select(Author.raw).where(
            Author.is_supervisor_candidate.is_(True), Author.merged_into_id.is_(None)
        )
    ).scalars()
    return latest_update(raws)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-url", default="sqlite:///data/sfr.db", help="БД каталога (только чтение)"
    )
    parser.add_argument("--index-dir", type=Path, required=True, help="Каталог индекса с meta.json")
    args = parser.parse_args()

    engine = make_engine(args.db_url)
    with session_scope(engine) as session:
        value = catalogue_data_date(session)
    if value is None:
        raise SystemExit("в каталоге нет ни одной записи с updated_date — штамповать нечего")
    meta = stamp_data_updated_at(args.index_dir, value)
    print(f"{args.index_dir}: data_updated_at = {meta.data_updated_at} ({meta.version})")


if __name__ == "__main__":
    main()
