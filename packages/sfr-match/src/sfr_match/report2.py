"""Render ``docs/SFR2_REPORT.md`` from what SFR-2 actually measured (SPEC_SFR2 §7).

Same split as SFR-1: everything here is generated from artefacts on disk and gets
overwritten on every run; the hand-written analysis lives in
``docs/SFR2_REPORT_notes.md`` and is appended verbatim.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean as _mean
from typing import Any

from sfr_match.calibrate import ThresholdRow
from sfr_match.evalset import Query
from sfr_match.index import load_docs
from sfr_match.report import VariantMetrics

SFR2_REPORT_PATH = Path("docs/SFR2_REPORT.md")
SFR2_NOTES_PATH = Path("docs/SFR2_REPORT_notes.md")
RESOURCES_PATH = Path("docs/sfr2_resources.json")

COMPOSITION_TITLES = {
    "full": "полный profile_text (бейзлайн)",
    "topics": "только темы",
    "topics_titles": "темы + названия работ",
}


def indexed_text_chars(index_dir: Path) -> float:
    """Mean length of what was actually embedded — the cost side of a composition."""
    if not (index_dir / "docs.json").exists():
        return 0.0
    docs = load_docs(index_dir)
    return round(_mean([len(str(doc["indexed_text"])) for doc in docs]), 0) if docs else 0.0


def load_resources(path: Path = RESOURCES_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return payload


def _pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def render_resources(resources: dict[str, Any]) -> list[str]:
    """The table the VPS decision is made from."""
    if not resources:
        return ["## Ресурсы", "", "_Замер не выполнялся._", ""]
    host = resources.get("host", {})
    where = "в контейнере" if host.get("docker") else "в venv (без контейнера)"
    lines = [
        "## Ресурсы: FRIDA против запасной mpnet",
        "",
        f"_Замер {resources.get('measured_at', '?')}, {where}. "
        f"Хост: {host.get('platform', '?')} / {host.get('machine', '?')}"
        + (f", docker: {host['docker_info']}" if host.get("docker_info") else "")
        + "._",
        "",
        "| Модель | Холодный старт, с | RAM покой, МБ | RAM под нагрузкой, МБ | "
        "p50, мс | p95, мс | p50 при 4 параллельных, мс | p95 при 4, мс | rps | Образ, МБ |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for entry in resources.get("models", []):
        image = entry.get("image_mb")
        lines.append(
            f"| `{entry['model']}` | {entry['cold_start_s']} | {entry['rss_idle_mb']} | "
            f"{entry['rss_load_mb']} | {entry['seq_p50_ms']} | {entry['seq_p95_ms']} | "
            f"{entry['conc4_p50_ms']} | {entry['conc4_p95_ms']} | {entry['conc4_rps']} | "
            f"{image if image else '—'} |"
        )
    lines.append("")
    return lines


def render_faiss_check(resources: dict[str, Any]) -> list[str]:
    checks = [
        (entry["model"], entry["faiss_vs_numpy"])
        for entry in resources.get("models", [])
        if entry.get("faiss_vs_numpy")
    ]
    if not checks:
        return []
    lines = [
        "## FAISS ≡ NumPy на живых векторах",
        "",
        "| Модель | Бэкенд в контейнере | Запросов сверено | Порядок совпал | "
        "Макс. расхождение score |",
        "|---|---|---|---|---|",
    ]
    for model, check in checks:
        verdict = (
            "да" if check["identical_order"] else "НЕТ: " + ", ".join(check["mismatched_queries"])
        )
        lines.append(
            f"| `{model}` | {check['backend_checked']} | {check['queries']} | "
            f"{verdict} | {check['max_score_delta']:.2e} |"
        )
    lines.append("")
    return lines


def _changes_only(rows: list[ThresholdRow]) -> list[ThresholdRow]:
    """Only thresholds where something changes — the rest of the grid is noise."""
    kept: list[ThresholdRow] = []
    previous: tuple[int, int, int] | None = None
    for row in rows:
        key = (row.false_cuts_in_domain, row.false_cuts_edge, row.ood_caught)
        if key != previous:
            kept.append(row)
            previous = key
    return kept


def render_calibration(
    rows: list[ThresholdRow],
    recommended: ThresholdRow | None,
    counts: dict[str, int],
    variant: str,
    previous_threshold: float,
) -> list[str]:
    lines = [
        "## Порог отсечки «мы никого не нашли»",
        "",
        f"Считается по варианту `{variant}`: у каждой модели и каждого состава индекса "
        "своя шкала score, поэтому порог принадлежит варианту, а не проекту вообще.",
        "",
        f"Точки калибровки: **{counts['in_domain']}** in-domain, **{counts['edge']}** edge, "
        f"**{counts['ood']}** подтверждённых out-of-domain "
        f"(в SFR-1 их было 2 — порог стоял на двух точках).",
        "",
        "| Порог top-1 | Ошибочно отсечёт in-domain | Ошибочно отсечёт edge | Верно отсечёт OOD |",
        "|---|---|---|---|",
    ]
    for row in _changes_only(rows):
        mark = " **←**" if recommended and row.threshold == recommended.threshold else ""
        lines.append(
            f"| {row.threshold:.2f}{mark} | {row.false_cuts_in_domain} / {counts['in_domain']} | "
            f"{row.false_cuts_edge} / {counts['edge']} | {row.ood_caught} / {counts['ood']} |"
        )
    lines.append("")
    if recommended:
        lines += [
            f"**Рекомендация: {recommended.threshold:.2f}** — самый высокий порог, который не "
            f"отсекает ни одного in-domain запроса; ловит "
            f"{recommended.ood_caught} из {counts['ood']} посторонних "
            f"({_pct(recommended.ood_caught / counts['ood']) if counts['ood'] else '—'}). "
            f"Было в SFR-1: {previous_threshold:.2f}.",
            "",
        ]
    else:
        lines += ["Безопасного порога нет: любой отсекает живые запросы.", ""]
    return lines


def render_composition(
    metrics: list[VariantMetrics], chars: dict[str, float], index_versions: dict[str, str]
) -> list[str]:
    lines = [
        "## Что класть в индекс: состав profile_text",
        "",
        "| Вариант | Состав | Символов на профиль | Success@1 | Success@3 | Success@5 | "
        "nDCG@10 | MRR | Индексация, с | Латентность, мс |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for metric in metrics:
        compose = metric.variant.split("__")[1] if "__" in metric.variant else "full"
        lines.append(
            f"| `{metric.variant}` | {COMPOSITION_TITLES.get(compose, compose)} | "
            f"{chars.get(metric.variant, 0):.0f} | **{_pct(metric.success1_strict)}** | "
            f"{_pct(metric.success3_strict)} | **{_pct(metric.success5_strict)}** | "
            f"{metric.ndcg10:.3f} | {metric.mrr:.3f} | {metric.build_seconds:.1f} | "
            f"{metric.latency_ms_mean:.0f} |"
        )
    lines += [
        "",
        "Метрики — по in-domain запросам golden set; судейство то же, что в SFR-1 "
        "(новые пары размечены по той же рубрике и лежат в `judgments.jsonl`).",
        "",
        "Версии индексов: "
        + ", ".join(f"`{key}` = {value}" for key, value in index_versions.items()),
        "",
    ]
    return lines


def render_examples(resources: dict[str, Any]) -> list[str]:
    examples = resources.get("examples") or []
    if not examples:
        return []
    lines = ["## Примеры запрос → ответ API", ""]
    for example in examples:
        below = str(example["below_threshold"]).lower()
        lines += [
            f"**`POST /api/match`** `{json.dumps(example['request'], ensure_ascii=False)}` "
            f"→ {example['took_ms']} мс, `below_threshold: {below}`",
            "",
            "```",
        ]
        for hit in example["results"]:
            topics = "; ".join(hit["topics"][:2])
            lines.append(
                f"{hit['rank']}. {hit['name']:<24} {hit['score']:.3f}  "
                f"{hit['institution'] or '—'} · h={hit['h_index']} · {topics}"
            )
        lines += ["```", ""]
    return lines


def render_sfr2_report(
    *,
    composition: list[VariantMetrics],
    chars: dict[str, float],
    index_versions: dict[str, str],
    calibration: list[ThresholdRow],
    recommended: ThresholdRow | None,
    calibration_counts: dict[str, int],
    calibration_variant: str,
    previous_threshold: float,
    resources: dict[str, Any],
    queries: list[Query],
    ood_queries: list[Query],
    n_profiles: int,
    notes: str = "",
) -> str:
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# SFR-2 — API поиска, FAISS, порог отсечки, состав индекса",
        "",
        f"_Сгенерировано `sfr-match report-sfr2` {stamp}. Корпус: {n_profiles} профилей "
        "МФТИ + МГУ из `data/exports/profiles_mipt_msu.jsonl`._",
        "",
        "## Условия",
        "",
        f"- Golden set SFR-1: **{len(queries)}** запросов "
        f"({sum(1 for q in queries if q.expect == 'in-domain')} in-domain, "
        f"{sum(1 for q in queries if q.expect == 'edge')} edge, "
        f"{sum(1 for q in queries if q.expect == 'out-of-domain')} out-of-domain) — заморожен.",
        f"- Набор out-of-domain SFR-2: **{len(ood_queries)}** запросов, каждый подтверждён "
        "поиском по корпусу (процедура — в разборе ниже).",
        "- Модель — `ai-forever/FRIDA`, выбор SFR-1 не переоткрывался.",
        "",
    ]
    lines += render_resources(resources)
    lines += render_faiss_check(resources)
    lines += render_calibration(
        calibration, recommended, calibration_counts, calibration_variant, previous_threshold
    )
    lines += render_composition(composition, chars, index_versions)
    lines += render_examples(resources)
    if notes:
        lines += [notes.strip(), ""]
    return "\n".join(lines)
