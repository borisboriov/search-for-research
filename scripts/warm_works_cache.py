"""Прогрев дискового кэша работ: только сеть, без записи в БД.

Зачем отдельный шаг. `sfr etl works` однопоточный и держит транзакцию: он
и ходит в сеть, и пишет в БД. На каталоге в 5 тысяч авторов сеть занимает
часы, а запись — минуты. Скрипт выкачивает ровно те же два запроса на автора,
что сделает ингест, и складывает их в дисковый кэш `data/raw`; после этого
`sfr etl works --only-missing` проходит по кэшу за минуты.

Что здесь важно и неочевидно:

* **Квота OpenAlex дневная.** Скрипт останавливается на первом 429 целиком,
  а не ретраит: 429 здесь означает «кредиты кончились до полуночи UTC», и
  ретраи только жгут время. Прогресс не теряется — он в кэше на диске,
  повторный запуск продолжит с того же места.
* **Темп.** Правило репозитория — не больше ``openalex_max_rps`` запросов в
  секунду (10.0 в настройках), и это ограничение **общее**, а не на поток:
  троттлинг внутри клиента видит только свои запросы, так что шесть потоков по
  1.2 rps дают 7.2, а десять — уже 12, о чём ни один из них не знает. Поэтому
  все потоки ходят через один ``RateLimiter``: ``--rps-per-worker`` остаётся
  верхней границей для потока, общий колпак берётся из настроек.
* **В БД скрипт не пишет ничего** и потому безопасен для параллельного чтения.
"""

import argparse
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import httpx
from sqlalchemy import select

from sfr_core.db import make_engine, session_scope
from sfr_core.models import Author, Work
from sfr_core.settings import get_settings
from sfr_etl.client import OpenAlexClient, RateLimiter, RetryableStatusError
from sfr_etl.works import WORK_SELECT_FIELDS


def authors_needing_works(only_missing: bool) -> list[str]:
    """Авторы каталога, для которых надо выкачать работы."""
    settings = get_settings()
    engine = make_engine(settings.sfr_db_url)
    with session_scope(engine) as session:
        query = select(Author.openalex_id).where(
            Author.is_supervisor_candidate.is_(True), Author.merged_into_id.is_(None)
        )
        if only_missing:
            query = query.where(~select(Work.id).where(Work.author_id == Author.id).exists())
        return list(session.execute(query.order_by(Author.openalex_id)).scalars())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--rps-per-worker", type=float, default=1.2)
    parser.add_argument(
        "--all",
        action="store_true",
        help="Греть и тех, у кого работы уже есть (по умолчанию только недостающих)",
    )
    args = parser.parse_args()

    settings = get_settings()
    if not settings.openalex_api_key:
        print(
            "ВНИМАНИЕ: OPENALEX_API_KEY не задан — квота 1 000 запросов в сутки "
            "вместо 10 000 (openalex.org/settings/api).",
            file=sys.stderr,
        )
    ids = authors_needing_works(only_missing=not args.all)
    since_year = datetime.now(UTC).year - settings.works_since_years + 1
    limiter = RateLimiter(settings.openalex_max_rps)
    requested_rps = args.workers * args.rps_per_worker
    print(
        f"авторов к прогреву: {len(ids)} (~{2 * len(ids)} запросов); темп "
        f"{args.workers}x{args.rps_per_worker} = {requested_rps:.1f} rps, "
        f"общий колпак {settings.openalex_max_rps:.1f} rps",
        flush=True,
    )
    if requested_rps > settings.openalex_max_rps:
        print(
            f"ВНИМАНИЕ: запрошено {requested_rps:.1f} rps — выше общего колпака, "
            f"фактический темп будет {settings.openalex_max_rps:.1f} rps.",
            file=sys.stderr,
        )

    local = threading.local()
    lock = threading.Lock()
    stop = threading.Event()
    done = failed = 0
    started = time.monotonic()

    def client() -> OpenAlexClient:
        if not hasattr(local, "client"):
            local.client = OpenAlexClient(
                settings.openalex_mailto,
                api_key=settings.openalex_api_key,
                base_url=settings.openalex_base_url,
                max_rps=args.rps_per_worker,
                rate_limiter=limiter,
                cache_dir=settings.raw_cache_dir,
                # 429 = кредиты кончились: ретраить бессмысленно, останавливаемся.
                max_attempts=1,
            )
        return local.client

    def warm(author_id: str) -> None:
        nonlocal done, failed
        if stop.is_set():
            return
        api = client()
        author_filter = f"authorships.author.id:{author_id}"
        try:
            api.get(
                "/works",
                {
                    "filter": author_filter,
                    "sort": "cited_by_count:desc",
                    "per-page": settings.works_per_author,
                    "select": WORK_SELECT_FIELDS,
                },
            )
            api.get(
                "/works",
                {
                    "filter": f"{author_filter},publication_year:>{since_year - 1}",
                    "sort": "publication_date:desc",
                    "per-page": settings.works_per_author,
                    "select": WORK_SELECT_FIELDS,
                },
            )
        except RetryableStatusError as exc:
            if exc.status_code == 429:
                if not stop.is_set():
                    print(
                        "\n429 — дневная квота OpenAlex исчерпана, останавливаюсь. "
                        "Прогресс в кэше, запусти скрипт снова после сброса (00:00 UTC).",
                        file=sys.stderr,
                        flush=True,
                    )
                stop.set()
                return
            with lock:
                failed += 1
            return
        except httpx.HTTPError:
            with lock:
                failed += 1
            return
        with lock:
            done += 1
            if done % 200 == 0:
                elapsed = time.monotonic() - started
                rate = done / elapsed
                left = (len(ids) - done) / rate / 60 if rate else 0
                print(
                    f"{done}/{len(ids)} за {elapsed / 60:.1f} мин "
                    f"({rate:.1f} авт/с, осталось ~{left:.0f} мин)",
                    flush=True,
                )

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(warm, ids))

    elapsed = time.monotonic() - started
    print(
        f"\nпрогрето: {done}, ошибок: {failed}, "
        f"{'ОСТАНОВЛЕНО по квоте' if stop.is_set() else 'дошло до конца'}; "
        f"{elapsed / 60:.1f} мин",
        flush=True,
    )
    if stop.is_set():
        sys.exit(2)


if __name__ == "__main__":
    main()
