"""Проштамповать пороги API в meta.json собранного индекса (ревью SFR-5, M8).

Зачем скрипт, а не числа в `make index-sfr5`: пороги живут в одном месте —
`ApiSettings`, — и прописать их в Makefile значит завести второй источник
истины ровно там, где сервис на старте сверяет первые два. Зачем не флаг
`sfr-match stamp-thresholds --from-settings`: `sfr-match` не знает про API и
знать не должен (зависимость идёт в обратную сторону, `sfr-api` → `sfr-match`).
Скрипт — единственное место, где обе стороны встречаются.

Без штампа `/health` отдаёт `thresholds_match: null`, то есть сверка молчит:
пересборка индекса разоружала бы гард той же итерации.
"""

import argparse
from pathlib import Path

from sfr_api.settings import ApiSettings
from sfr_match.index import stamp_thresholds


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--index-dir",
        type=Path,
        default=None,
        help="Каталог индекса; по умолчанию — тот, который откроет сервис",
    )
    args = parser.parse_args()

    settings = ApiSettings()
    index_dir = args.index_dir or settings.resolved_index_dir()
    meta = stamp_thresholds(
        index_dir,
        {
            "none": settings.score_threshold,
            "weak": settings.score_weak,
            "high": settings.score_high,
        },
    )
    print(f"{meta.version}: пороги {meta.thresholds} → {index_dir}")


if __name__ == "__main__":
    main()
