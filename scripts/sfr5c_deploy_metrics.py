"""Качество индекса по двум разметкам — цифры §13 и паспорта.

Пересуд топ-5 на индексе делает слепой судья (`sfr-judge`, Fable) по рубрике
26.09: **только эти цифры идут в паспорт** (#95, условия Бориса в #98).
Накопленная разметка `judgments.jsonl` считается рядом — она сравнима с §4 и со
всеми прошлыми отчётами, но получена судьёй-сборщиком и оптимистична. Две
колонки в одном файле, чтобы никто не взял их из разных мест и не сложил.

Индекс задаётся прогоном (`--runs`, в нём `index_version`), разметка — своим
файлом: по умолчанию выложенный индекс 9 002 (`make metrics-deploy-sfr5c`),
тот же скрипт на прежнем боевом индексе 5 538 — `make metrics-base-blind-sfr5c`
(#122, пара «было → стало» одним судьёй, §13.11 отчёта).

Наборы — те же, что в §6: `golden in-domain 24`, «те же 22» (без `q29`/`q30`,
перемеченных на ревью SFR-5) и `edge 6`. Неоценённая пара считается нулём —
пессимистично; их число печатается отдельно, потому что для слепой разметки
пустых мест быть не должно.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from sfr_match.evalset import (
    Judgment,
    load_judgments,
    load_queries,
    query_set_path,
    split_stale,
)
from sfr_match.evaluate import Run, load_run
from sfr_match.index import profile_fingerprints
from sfr_match.metrics import mean, success_at_k

TOP = 5
# Перемечены из out-of-domain в in-domain на ревью SFR-5; набор «те же 22»,
# сравнимый с SFR-2, — действующие in-domain без них (как в SFR-5b и SFR-5c).
RELABELLED_IN_DOMAIN = frozenset({"q29", "q30"})


def _grades(
    run: Run, query_id: str, judgments: dict[tuple[str, str], Judgment]
) -> tuple[list[int], int]:
    """Оценки топ-5 запроса и сколько его пар осталось без оценки."""
    top = run.ranked_ids(query_id)[:TOP]
    grades = [judgments[(query_id, a)].grade if (query_id, a) in judgments else 0 for a in top]
    missing = sum(1 for a in top if (query_id, a) not in judgments)
    return grades, missing


def summarize(
    run: Run, queries: list[Any], judgments: dict[tuple[str, str], Judgment]
) -> dict[str, Any]:
    per_query = []
    for query in queries:
        grades, missing = _grades(run, query.id, judgments)
        per_query.append(
            {
                "id": query.id,
                "s1": success_at_k(grades, 1),
                "s5": success_at_k(grades, TOP),
                "top1": run.top_score(query.id),
                "grades": grades,
                "unjudged": missing,
            }
        )
    return {
        "n": len(per_query),
        "success_at_1": round(mean([float(r["s1"]) for r in per_query]), 3),
        "success_at_5": round(mean([float(r["s5"]) for r in per_query]), 3),
        "unjudged_pairs": sum(int(r["unjudged"]) for r in per_query),
        "per_query": per_query,
    }


def drop_stale(
    name: str, judgments: dict[tuple[str, str], Judgment], fingerprints: dict[str, str] | None
) -> tuple[dict[tuple[str, str], Judgment], dict[str, Any] | None]:
    """Устаревшие оценки (#123) — вон, с отчётом; без индекса — как есть."""
    if fingerprints is None:
        return judgments, None
    usable, counts, stale = split_stale(judgments, fingerprints)
    print(
        f"{name}: оценок с отпечатком профиля {counts['fresh'] + counts['stale']}, "
        f"из них устарели {counts['stale']} (профиль изменился после оценки — пары считаются "
        f"неоценёнными); без отпечатка {counts['no_fingerprint']}"
    )
    if counts["fresh"] + counts["stale"] == 0:
        return usable, None  # строк с отпечатком нет — JSON как до #123
    return usable, {**counts, "stale_pairs": [list(key) for key in stale]}


def load_borderline(path: Path) -> dict[tuple[str, str], int]:
    """Альтернативные оценки спорных пар из `judgments_borderline_*.md` (#131).

    Строка таблицы: `| `q08` | …`A5…`… | <оценка> | <альтернатива> | … |` — id автора
    где угодно во второй колонке, оценка может быть выделена `**…**`.
    """
    alternatives: dict[tuple[str, str], int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        query = re.fullmatch(r"`?(q\d+)`?", cells[0])
        author = re.search(r"`(A\d+)`", cells[1])
        alt = re.fullmatch(r"\**([012])\**", cells[3])
        if query and author and alt:
            alternatives[(query.group(1), author.group(1))] = int(alt.group(1))
    return alternatives


def with_alternatives(
    judgments: dict[tuple[str, str], Judgment],
    alternatives: dict[tuple[str, str], int],
    pick: Any,
) -> dict[tuple[str, str], Judgment]:
    """Разметка, где у спорных пар оценка заменена на min/max(оценка, альтернатива)."""
    out = dict(judgments)
    for key, alt in alternatives.items():
        if key in out:
            out[key] = out[key].model_copy(update={"grade": pick(out[key].grade, alt)})
    return out


def borderline_interval(
    run: Run,
    queries: list[Any],
    judgments: dict[tuple[str, str], Judgment],
    alternatives: dict[tuple[str, str], int],
) -> dict[str, Any]:
    """Интервал Success@k по спорным парам (#131): все альтернативы вниз / все вверх.

    Не доверительный интервал, а чувствительность цифры к колебаниям судьи на
    парах, где он сам назвал вторую оценку: сколько стоит «спорное» в обе стороны.
    """
    low = with_alternatives(judgments, alternatives, min)
    high = with_alternatives(judgments, alternatives, max)
    out: dict[str, Any] = {"borderline_pairs": len(alternatives)}
    for name, subset in sets_of(queries).items():
        point, lo, hi = (summarize(run, subset, j) for j in (judgments, low, high))
        ids = {q.id for q in subset}
        out[name] = {
            # Спорных пар в самом наборе: в защите — «37 из 120 пар этих 24
            # запросов», а не общее число по всем 150 парам пула.
            "borderline_pairs": sum(1 for query_id, _ in alternatives if query_id in ids),
            **{
                metric: {"low": lo[metric], "point": point[metric], "high": hi[metric]}
                for metric in ("success_at_1", "success_at_5")
            },
        }
    return out


def sets_of(queries: list[Any]) -> dict[str, list[Any]]:
    in_domain = [q for q in queries if q.expect == "in-domain"]
    return {
        "golden_in_domain_24": in_domain,
        "golden_same_22": [q for q in in_domain if q.id not in RELABELLED_IN_DOMAIN],
        "golden_edge": [q for q in queries if q.expect == "edge"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runs",
        type=Path,
        default=Path("data/eval/runs_sfr5c/frida_clean.json"),
        help="Прогон golden set на индексе, который оценивается",
    )
    parser.add_argument(
        "--judgments",
        type=Path,
        default=Path("packages/sfr-match/eval/judgments_deploy_sfr5c.jsonl"),
        help="Слепая разметка топ-5 этого же индекса",
    )
    parser.add_argument("--out", type=Path, default=Path("docs/metrics/sfr5c_deploy_metrics.json"))
    parser.add_argument(
        "--index-root",
        type=Path,
        default=None,
        help="Индекс прогона: сверка отпечатков профилей в оценках (#123)",
    )
    parser.add_argument(
        "--borderline",
        type=Path,
        default=None,
        help="Спорные пары судьи (judgments_borderline_*.md) — интервал в --interval-out (#131)",
    )
    parser.add_argument("--interval-out", type=Path, default=None)
    args = parser.parse_args()

    run = load_run(args.runs)
    queries = load_queries(query_set_path("golden"))
    fingerprints = profile_fingerprints(args.index_root) if args.index_root else None
    blind, blind_stale = drop_stale("слепая", load_judgments(args.judgments), fingerprints)
    accumulated, accumulated_stale = drop_stale("накопленная", load_judgments(), fingerprints)

    payload: dict[str, Any] = {
        "index_version": run.index_version,
        "n_profiles": run.n_profiles,
        "judgments": {
            "blind": {
                "path": str(args.judgments),
                "pairs": len(blind),
                "grades": dict(sorted(Counter(j.grade for j in blind.values()).items())),
                "judges": dict(sorted(Counter(j.judge or "" for j in blind.values()).items())),
            },
            "accumulated": {"path": "packages/sfr-match/eval/judgments.jsonl"},
        },
        "sets": {
            name: {
                "blind": summarize(run, subset, blind),
                "accumulated": summarize(run, subset, accumulated),
            }
            for name, subset in sets_of(queries).items()
        },
    }
    # Блок только при оценках с отпечатком: у разметки до #123 его нет, и JSON
    # прошлых прогонов воспроизводится байт в байт.
    if blind_stale is not None:
        payload["judgments"]["blind"]["staleness"] = blind_stale
    if accumulated_stale is not None:
        payload["judgments"]["accumulated"]["staleness"] = accumulated_stale
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.borderline is not None and args.interval_out is not None:
        interval = {
            "index_version": run.index_version,
            "borderline": str(args.borderline),
            **borderline_interval(run, queries, blind, load_borderline(args.borderline)),
        }
        args.interval_out.write_text(
            json.dumps(interval, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        for name in ("golden_in_domain_24", "golden_same_22", "golden_edge"):
            row = interval[name]
            s1, s5 = row["success_at_1"], row["success_at_5"]
            print(
                f"интервал {name:22s} S@1 {s1['low']:.3f}–{s1['high']:.3f} "
                f"(точка {s1['point']:.3f}) · S@5 {s5['low']:.3f}–{s5['high']:.3f} "
                f"(точка {s5['point']:.3f}) · спорных пар {row['borderline_pairs']}"
            )
    for name, both in payload["sets"].items():
        for markup in ("blind", "accumulated"):
            row = both[markup]
            print(
                f"{name:24s} {markup:12s} n={row['n']:2d} "
                f"S@1={row['success_at_1']:.3f} S@5={row['success_at_5']:.3f} "
                f"неоценённых пар {row['unjudged_pairs']}"
            )
    print(f"полные данные → {args.out}")


if __name__ == "__main__":
    main()
