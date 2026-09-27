"""Цифры для `docs/reports/SFR5_REPORT.md`: регрессия качества, страты, пороги.

Отдельный скрипт, а не команда `sfr-match`: `report-sfr2` собирает замороженный
отчёт SFR-2 и его трогать нельзя, а таблицы SFR-5 нужны разовые — в частности
доля страт в топ-5 (полные тексты против метаданных), которой в прошлых
итерациях не существовало.
"""

import argparse
import json
import math
from pathlib import Path
from statistics import median
from typing import Any

from sfr_match.calibrate import calibrate, grid, recommend, top1_scores
from sfr_match.evalset import load_judgments, load_queries, query_set_path
from sfr_match.evaluate import load_runs
from sfr_match.metrics import mean, success_at_k


def strata(profiles_path: Path) -> dict[str, str]:
    """Профиль с загруженными работами («full») или только с метаданными («meta»)."""
    out: dict[str, str] = {}
    with profiles_path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                record = json.loads(line)
                out[str(record["id"])] = "full" if record.get("works") else "meta"
    return out


def quality(run: Any, queries: list[Any], judgments: dict[tuple[str, str], Any]) -> dict[str, Any]:
    by_kind: dict[str, list[tuple[bool, bool]]] = {}
    per_query = []
    for query in queries:
        ranked = run.ranked_ids(query.id)
        grades = [
            judgments[(query.id, a)].grade if (query.id, a) in judgments else 0 for a in ranked
        ]
        s1, s5 = success_at_k(grades, 1), success_at_k(grades, 5)
        by_kind.setdefault(query.expect, []).append((s1, s5))
        per_query.append(
            {
                "id": query.id,
                "expect": query.expect,
                "s1": s1,
                "s5": s5,
                "top1": run.top_score(query.id),
            }
        )
    return {
        "success_at_1": round(mean([float(s1) for v in by_kind.values() for s1, _ in v]), 3),
        "success_at_5": round(mean([float(s5) for v in by_kind.values() for _, s5 in v]), 3),
        "by_kind": {
            kind: {
                "n": len(values),
                "success_at_1": round(mean([float(s1) for s1, _ in values]), 3),
                "success_at_5": round(mean([float(s5) for _, s5 in values]), 3),
            }
            for kind, values in sorted(by_kind.items())
        },
        "per_query": per_query,
    }


def threshold_hints(
    run: Any, queries: list[Any], quality_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    """`weak` и `high` по рецепту SFR-5: из распределения top-1, не калибровка.

    * **`weak`** — минимум top-1 по in-domain, вверх по сетке 0.01: баннер
      «совпадения слабые» получают ровно самые слабые из живых попаданий.
    * **`high`** — медиана top-1 по **удачным** in-domain запросам, вниз по
      сетке. «Удачный» = ``Success@1 = 1``: top-1 действительно релевантен, и
      только тогда его score — пример «хорошего совпадения». Рецепт
      восстановлен по числам SFR-5 (0.4791 → 0.47) и SFR-5b (0.4961 → 0.49);
      §5 SFR-5c посчитал медиану по всем 24 (0.4864 → 0.48) — там все 24
      проходили Success@5, и «удачные» прочитались как S@5.

    Рядом печатается медиана по всем in-domain: расхождение рецептов стоило
    шага сетки, и увидеть его надо в цифрах, а не в прозе.
    """
    by_id = {row["id"]: row for row in quality_rows}
    in_domain = [q for q in queries if q.expect == "in-domain"]
    scores = [run.top_score(q.id) for q in in_domain]
    scores = [s for s in scores if s is not None]
    lucky = [
        run.top_score(q.id)
        for q in in_domain
        if by_id.get(q.id, {}).get("s1") and run.top_score(q.id) is not None
    ]
    return {
        "in_domain_min": round(min(scores), 4),
        "weak": math.ceil(min(scores) * 100) / 100,
        "lucky_n": len(lucky),
        "lucky_median": None if not lucky else round(median(lucky), 4),
        "high": None if not lucky else math.floor(median(lucky) * 100) / 100,
        "all_in_domain_median": round(median(scores), 4),
        "high_by_all_in_domain": math.floor(median(scores) * 100) / 100,
    }


def stratum_share(
    run: Any, queries: list[Any], mapping: dict[str, str], depth: int
) -> dict[str, Any]:
    """Из какой страты приходят результаты топ-``depth`` — прямой замер смещения."""
    counts = {"full": 0, "meta": 0, "unknown": 0}
    for query in queries:
        for author_id in run.ranked_ids(query.id)[:depth]:
            counts[mapping.get(author_id, "unknown")] += 1
    total = sum(counts.values()) or 1
    return {**counts, "full_share": round(counts["full"] / total, 3), "slots": total}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", type=Path, default=Path("data/eval/runs_sfr5"))
    parser.add_argument("--ood-runs-dir", type=Path, default=Path("data/eval/runs_ood_sfr5"))
    parser.add_argument("--profiles", type=Path, default=Path("data/exports/profiles_sfr5.jsonl"))
    parser.add_argument("--variant", default="frida_clean")
    parser.add_argument("--out", type=Path, default=Path("docs/metrics/sfr5_metrics.json"))
    # Набор посторонних менялся (o13/o15 удалены 26.09, 19 → 17): калибровка
    # прошлых отчётов воспроизводится только по тому набору, на котором считалась.
    # Архивный файл достаёт из git цель `make ood19-sfr5c`.
    parser.add_argument(
        "--ood-queries",
        type=Path,
        default=None,
        help="Файл набора посторонних; по умолчанию — действующий ood_queries.jsonl",
    )
    args = parser.parse_args()

    runs = {run.variant: run for run in load_runs(args.runs_dir)}
    ood_runs = {run.variant: run for run in load_runs(args.ood_runs_dir)}
    run, ood_run = runs[args.variant], ood_runs[args.variant]
    queries = load_queries(query_set_path("golden"))
    ood_queries = load_queries(args.ood_queries or query_set_path("ood"))
    judgments = load_judgments()
    mapping = strata(args.profiles)
    quality_payload = quality(run, queries, judgments)

    in_domain = top1_scores(run, queries, {"in-domain"})
    edge = top1_scores(run, queries, {"edge"})
    ood = top1_scores(ood_run, ood_queries, {"out-of-domain"})
    rows = calibrate(in_domain, edge, ood, grid(in_domain, edge, ood))
    best = recommend(rows)

    payload: dict[str, Any] = {
        "index_version": run.index_version,
        "n_profiles": run.n_profiles,
        "corpus_strata": {
            "full": sum(1 for v in mapping.values() if v == "full"),
            "meta": sum(1 for v in mapping.values() if v == "meta"),
        },
        "quality": quality_payload,
        "threshold_hints": threshold_hints(run, queries, quality_payload["per_query"]),
        "stratum_share_top5": stratum_share(run, queries, mapping, depth=5),
        "stratum_share_top1": stratum_share(run, queries, mapping, depth=1),
        "calibration": {
            "counts": {"in_domain": len(in_domain), "edge": len(edge), "ood": len(ood)},
            "recommended": None if best is None else best.__dict__,
            "rows": [row.__dict__ for row in rows],
        },
        "top1_scores": {
            "in_domain": sorted(round(v, 4) for v in in_domain.values()),
            "edge": sorted(round(v, 4) for v in edge.values()),
            "ood": sorted(round(v, 4) for v in ood.values()),
        },
        "ood_per_query": [
            {"id": q.id, "top1": ood_run.top_score(q.id), "comment": q.comment} for q in ood_queries
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    compact = {k: v for k, v in payload.items() if k not in {"calibration", "ood_per_query"}}
    compact.pop("top1_scores", None)
    compact["quality"] = {k: v for k, v in payload["quality"].items() if k != "per_query"}
    compact["recommended_none"] = payload["calibration"]["recommended"]
    print(json.dumps(compact, ensure_ascii=False, indent=2))
    print(f"полные данные → {args.out}")


if __name__ == "__main__":
    main()
