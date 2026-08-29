"""Aggregate eval runs + judgments into docs/SFR1_REPORT.md."""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean as _mean
from typing import Any

from sfr_match.evalset import Judgment, Query
from sfr_match.evaluate import Run, latency_summary
from sfr_match.metrics import mean, ndcg_at_k, reciprocal_rank, success_at_k
from sfr_match.models import REGISTRY

REPORT_PATH = Path("docs/SFR1_REPORT.md")
NOTES_PATH = Path("docs/SFR1_REPORT_notes.md")


@dataclass
class VariantMetrics:
    variant: str
    model_key: str
    clean: bool
    n_profiles: int
    n_in_domain: int
    success5_strict: float
    success5_soft: float
    ndcg10: float
    mrr: float
    build_seconds: float
    latency_ms_mean: float
    latency_ms_median: float
    params_m: float | None
    judged_share: float
    ood_top1_mean: float
    ood_false_positives: int
    in_domain_top1_min: float
    in_domain_top1_mean: float
    ood_top1_max: float


def _grades(
    run: Run, query: Query, judgments: dict[tuple[str, str], Judgment], k: int
) -> list[int]:
    """Graded ranking for one query; unjudged pairs count as non-relevant (grade 0)."""
    return [
        judgments[(query.id, author_id)].grade if (query.id, author_id) in judgments else 0
        for author_id in run.ranked_ids(query.id)[:k]
    ]


def compute_metrics(
    run: Run,
    queries: list[Query],
    judgments: dict[tuple[str, str], Judgment],
) -> VariantMetrics:
    in_domain = [query for query in queries if query.expect == "in-domain"]
    out_of_domain = [query for query in queries if query.expect == "out-of-domain"]

    strict: list[float] = []
    soft: list[float] = []
    ndcgs: list[float] = []
    rrs: list[float] = []
    judged_hits = 0
    total_hits = 0

    for query in in_domain:
        graded5 = _grades(run, query, judgments, 5)
        graded10 = _grades(run, query, judgments, 10)
        pool = [j.grade for (qid, _), j in judgments.items() if qid == query.id]
        strict.append(float(success_at_k(graded5, k=5, min_grade=2)))
        soft.append(float(success_at_k(graded5, k=5, min_grade=1)))
        ndcgs.append(ndcg_at_k(graded10, pool, k=10))
        rrs.append(reciprocal_rank(graded10, min_grade=2))
        judged_hits += sum(
            1 for author_id in run.ranked_ids(query.id)[:5] if (query.id, author_id) in judgments
        )
        total_hits += len(run.ranked_ids(query.id)[:5])

    ood_top1 = [score for query in out_of_domain if (score := run.top_score(query.id)) is not None]
    ood_false = sum(
        1
        for query in out_of_domain
        for author_id in run.ranked_ids(query.id)[:5]
        if judgments.get((query.id, author_id), Judgment(query_id="", author_id="", grade=0)).grade
        >= 1
    )
    in_top1 = [score for query in in_domain if (score := run.top_score(query.id)) is not None]
    latency = latency_summary(run)
    spec = REGISTRY.get(run.model_key)

    return VariantMetrics(
        variant=run.variant,
        model_key=run.model_key,
        clean=run.clean,
        n_profiles=run.n_profiles,
        n_in_domain=len(in_domain),
        success5_strict=mean(strict),
        success5_soft=mean(soft),
        ndcg10=mean(ndcgs),
        mrr=mean(rrs),
        build_seconds=run.build_seconds,
        latency_ms_mean=latency["mean"],
        latency_ms_median=latency["median"],
        params_m=spec.params_m if spec else None,
        judged_share=judged_hits / total_hits if total_hits else 0.0,
        ood_top1_mean=_mean(ood_top1) if ood_top1 else 0.0,
        ood_false_positives=ood_false,
        in_domain_top1_min=min(in_top1) if in_top1 else 0.0,
        in_domain_top1_mean=_mean(in_top1) if in_top1 else 0.0,
        ood_top1_max=max(ood_top1) if ood_top1 else 0.0,
    )


def _fmt_pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def _fmt_params(value: float | None) -> str:
    return "—" if value is None else f"{value:.0f}M"


def render_report(
    metrics: list[VariantMetrics],
    queries: list[Query],
    judgments: dict[tuple[str, str], Judgment],
    notes: str = "",
) -> str:
    """The generated part of the report; the hand-written analysis is appended verbatim."""
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    ordered = sorted(metrics, key=lambda m: m.success5_strict, reverse=True)
    n_in = ordered[0].n_in_domain if ordered else 0
    n_profiles = ordered[0].n_profiles if ordered else 0
    grade_counts = {
        grade: sum(1 for j in judgments.values() if j.grade == grade) for grade in (0, 1, 2)
    }

    lines = [
        "# SFR-1 — мини-тест embedding-моделей на профилях МФТИ",
        "",
        f"_Сгенерировано `sfr-match report` {stamp}. "
        f"Корпус: {n_profiles} профилей МФТИ из `data/exports/profiles.jsonl` (SFR-0)._",
        "",
        "## Условия эксперимента",
        "",
        f"- Golden set: **{len(queries)}** запросов "
        f"({sum(1 for q in queries if q.expect == 'in-domain')} in-domain, "
        f"{sum(1 for q in queries if q.expect == 'edge')} edge, "
        f"{sum(1 for q in queries if q.expect == 'out-of-domain')} out-of-domain).",
        f"- Судейский пул: **{len(judgments)}** пар (query, author); "
        f"оценок 2 — {grade_counts[2]}, 1 — {grade_counts[1]}, 0 — {grade_counts[0]}.",
        "- Метрики считаются по in-domain запросам; неоцененные пары в топ-10 = grade 0.",
        "",
        "## Сводная таблица",
        "",
        "| Вариант | Success@5 (grade=2) | Success@5 (grade≥1) | nDCG@10 | MRR | "
        "Индексация, с | Латентность, мс | Размер |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for m in ordered:
        lines.append(
            f"| `{m.variant}` | **{_fmt_pct(m.success5_strict)}** | {_fmt_pct(m.success5_soft)} | "
            f"{m.ndcg10:.3f} | {m.mrr:.3f} | {m.build_seconds:.1f} | "
            f"{m.latency_ms_mean:.0f} (медиана {m.latency_ms_median:.0f}) | "
            f"{_fmt_params(m.params_m)} |"
        )

    lines += [
        "",
        f"Порог проекта — Success@5 ≥ 70% на in-domain ({n_in} запросов).",
        "",
        "## Поведение на out-of-domain (порог «мы никого не нашли»)",
        "",
        "| Вариант | Средний top-1 score (OOD) | Макс. top-1 (OOD) | "
        "Мин. top-1 (in-domain) | Средний top-1 (in-domain) | Ложные находки (grade≥1 в топ-5) |",
        "|---|---|---|---|---|---|",
    ]
    for m in ordered:
        lines.append(
            f"| `{m.variant}` | {m.ood_top1_mean:.3f} | {m.ood_top1_max:.3f} | "
            f"{m.in_domain_top1_min:.3f} | {m.in_domain_top1_mean:.3f} | {m.ood_false_positives} |"
        )

    lines += [
        "",
        "Разделимость: если максимум top-1 на out-of-domain ниже минимума top-1 на in-domain,",
        "порог отсечки можно поставить между ними — модель честно скажет «никого не нашли».",
        "",
        "## Покрытие пула судейством",
        "",
        "| Вариант | Доля оценённых пар в топ-5 |",
        "|---|---|",
    ]
    for m in ordered:
        lines.append(f"| `{m.variant}` | {_fmt_pct(m.judged_share)} |")
    lines.append("")

    if notes:
        lines += [notes.strip(), ""]
    return "\n".join(lines)


def read_notes(path: Path = NOTES_PATH) -> str:
    """Hand-written analysis appended to the generated report (survives regeneration)."""
    return path.read_text(encoding="utf-8") if path.exists() else ""


def sample_for_review(
    pool: list[tuple[str, str]],
    queries: list[Query],
    judgments: dict[tuple[str, str], Judgment],
    profiles: dict[str, dict[str, Any]],
    n: int = 20,
    seed: int = 20260829,
) -> str:
    """`eval/judgments_for_review.md` — a random sample for a human to re-check."""
    import random

    rng = random.Random(seed)
    sample = rng.sample(pool, min(n, len(pool)))
    by_id = {query.id: query for query in queries}
    lines = [
        "# Судейские оценки — выборка для ручной проверки",
        "",
        f"{len(sample)} случайных пар из пула в {len(pool)} пар "
        f"(seed={seed}). Шкала: **2** — прямое совпадение специализации, "
        "**1** — смежная область, **0** — нерелевантно.",
        "",
    ]
    for i, (query_id, author_id) in enumerate(sample, start=1):
        judgment = judgments.get((query_id, author_id))
        query = by_id.get(query_id)
        profile = profiles.get(author_id, {})
        topics = "; ".join(list(profile.get("topics") or [])[:4])
        grade = judgment.grade if judgment else "?"
        lines += [
            f"## {i}. `{query_id}` × `{author_id}` — grade **{grade}**",
            "",
            f"- **Запрос:** {query.text if query else '?'}",
            f"- **НР:** {profile.get('name', '?')} — {topics}",
            f"- **Обоснование:** {judgment.rationale if judgment else '—'}",
            "",
        ]
    return "\n".join(lines)
