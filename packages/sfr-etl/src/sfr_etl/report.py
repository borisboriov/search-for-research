"""Generate docs/REPORT.md: run statistics, profile samples, top topics, data problems."""

import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sfr_core.models import Author, AuthorTopic, SupervisorProfile, Work


def compute_stats(session: Session) -> dict[str, Any]:
    authors = list(session.execute(select(Author)).scalars())
    candidates = [a for a in authors if a.is_supervisor_candidate]
    candidate_ids = {a.id for a in candidates}

    works = list(session.execute(select(Work)).scalars())
    profiles = list(session.execute(select(SupervisorProfile)).scalars())

    authors_with_abstract = {w.author_id for w in works if w.abstract_text}
    recent_by_author: dict[int, bool] = {}
    for w in works:
        if w.is_recent:
            recent_by_author[w.author_id] = True

    top_topics = session.execute(
        select(AuthorTopic.topic_name, func.count(AuthorTopic.author_id).label("n_authors"))
        .where(AuthorTopic.author_id.in_(candidate_ids))
        .group_by(AuthorTopic.topic_name)
        .order_by(func.count(AuthorTopic.author_id).desc())
        .limit(15)
    ).all()

    profile_lengths = [len(p.profile_text) for p in profiles]
    in_range = [length for length in profile_lengths if 300 <= length <= 1500]

    names = [a.display_name for a in candidates]
    duplicate_names = sorted({n for n in names if names.count(n) > 1})

    return {
        "n_authors": len(authors),
        "n_candidates": len(candidates),
        "n_with_h_index": sum(1 for a in authors if a.h_index is not None),
        "n_candidates_with_abstract": sum(1 for a in candidates if a.id in authors_with_abstract),
        "n_candidates_with_recent_work": sum(
            1 for a in candidates if recent_by_author.get(a.id, False)
        ),
        "median_works_count": median([a.works_count for a in authors]) if authors else 0,
        "median_h_index": median([a.h_index or 0 for a in authors]) if authors else 0,
        "median_works_count_candidates": (
            median([a.works_count for a in candidates]) if candidates else 0
        ),
        "median_h_index_candidates": (
            median([a.h_index or 0 for a in candidates]) if candidates else 0
        ),
        "n_works": len(works),
        "n_works_with_abstract": sum(1 for w in works if w.abstract_text),
        "n_profiles": len(profiles),
        "n_profiles_in_range": len(in_range),
        "profile_len_min": min(profile_lengths) if profile_lengths else 0,
        "profile_len_max": max(profile_lengths) if profile_lengths else 0,
        "top_topics": [(name, n) for name, n in top_topics],
        "duplicate_candidate_names": duplicate_names,
        "n_candidates_without_works": sum(
            1 for a in candidates if a.id not in {w.author_id for w in works}
        ),
        "n_mega_collab_authors": sum(1 for a in candidates if a.works_count > 1000),
    }


def sample_profiles(session: Session, n: int = 5) -> list[dict[str, Any]]:
    """Diverse samples: 2 longest, 2 around the median, the shortest."""
    profiles = list(
        session.execute(
            select(SupervisorProfile).join(Author, SupervisorProfile.author_id == Author.id)
        ).scalars()
    )
    if not profiles:
        return []
    by_len = sorted(profiles, key=lambda p: -len(p.profile_text))
    mid = len(by_len) // 2
    picked: list[SupervisorProfile] = []
    for p in [*by_len[:2], *by_len[mid : mid + 2], by_len[-1]]:
        if p not in picked:
            picked.append(p)
    result = []
    for p in picked[:n]:
        author = session.get(Author, p.author_id)
        result.append(
            {
                "name": author.display_name if author else "?",
                "openalex_id": author.openalex_id if author else "?",
                "length": len(p.profile_text),
                "n_works": p.n_works,
                "n_abstracts": p.n_abstracts,
                "text": p.profile_text,
            }
        )
    return result


def read_run_stats(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return data
    except json.JSONDecodeError:
        return {}


def cache_size_info(cache_dir: Path) -> tuple[int, float]:
    files = list(cache_dir.glob("*.json")) if cache_dir.exists() else []
    return len(files), sum(f.stat().st_size for f in files) / 1024 / 1024


def render_report(
    stats: dict[str, Any],
    samples: list[dict[str, Any]],
    run_stats: dict[str, Any],
    cache_files: int,
    cache_mb: float,
    notes: str = "",
) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = [
        "# REPORT — прогон ETL-пайплайна SFR-0",
        "",
        f"_Сгенерировано `sfr report` {now}. Данные: локальная БД `data/sfr.db`._",
        "",
        "## Статистика",
        "",
        f"- Авторов получено: **{stats['n_authors']}**",
        f"- Прошли эвристику НР (is_supervisor_candidate): **{stats['n_candidates']}**",
        f"- Авторов с h_index: **{stats['n_with_h_index']}**",
        f"- Кандидатов с ≥1 восстановленным abstract: **{stats['n_candidates_with_abstract']}**",
        f"- Кандидатов со «свежей» публикацией (в окне works-ингеста): "
        f"**{stats['n_candidates_with_recent_work']}**",
        f"- Медиана works_count: все авторы **{stats['median_works_count']}**, "
        f"кандидаты **{stats['median_works_count_candidates']}**",
        f"- Медиана h_index: все авторы **{stats['median_h_index']}**, "
        f"кандидаты **{stats['median_h_index_candidates']}**",
        f"- Работ сохранено: **{stats['n_works']}**, с abstract: "
        f"**{stats['n_works_with_abstract']}** "
        f"({_pct(stats['n_works_with_abstract'], stats['n_works'])})",
        f"- Профилей собрано: **{stats['n_profiles']}**, в диапазоне 300–1500 символов: "
        f"**{stats['n_profiles_in_range']}** "
        f"({_pct(stats['n_profiles_in_range'], stats['n_profiles'])}); "
        f"длина min/max: {stats['profile_len_min']}/{stats['profile_len_max']}",
        "",
        "## Примеры profile_text",
        "",
    ]
    for i, sample in enumerate(samples, 1):
        lines += [
            f"### Пример {i}: {sample['name']} ({sample['openalex_id']}, "
            f"{sample['length']} симв., работ: {sample['n_works']}, "
            f"с abstract: {sample['n_abstracts']})",
            "",
            "```",
            sample["text"],
            "```",
            "",
        ]
    lines += ["## Топ-15 тем среди кандидатов в НР", ""]
    lines += ["| Тема | Кандидатов |", "|---|---|"]
    lines += [f"| {name} | {n} |" for name, n in stats["top_topics"]]
    lines += [
        "",
        "## Прогон",
        "",
        f"- Кэш raw-ответов: {cache_files} файлов, {cache_mb:.1f} MiB",
    ]
    for step, history in run_stats.items():
        runs = history if isinstance(history, list) else [history]
        lines.append(f"- `{step}`: первый прогон — {_format_run(runs[0])}")
        if len(runs) > 1:
            lines.append(f"  повторный (кэш) — {_format_run(runs[-1])}")
    lines += [
        "",
        "## Проблемы данных (автоматические проверки)",
        "",
        f"- Дублирующиеся имена среди кандидатов: {len(stats['duplicate_candidate_names'])}"
        + (
            f" ({', '.join(stats['duplicate_candidate_names'][:5])}…)"
            if stats["duplicate_candidate_names"]
            else ""
        ),
        f"- Кандидатов без сохранённых работ: {stats['n_candidates_without_works']}",
        f"- Кандидатов-«мегаколлабораций» (works_count > 1000): {stats['n_mega_collab_authors']}",
        f"- Работ без abstract: {stats['n_works'] - stats['n_works_with_abstract']} "
        f"из {stats['n_works']}",
        "",
    ]
    if notes:
        lines += [notes.strip(), ""]
    return "\n".join(lines)


def read_notes(path: Path) -> str:
    """Hand-written analysis appended to the generated report (survives regeneration)."""
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _format_run(run: dict[str, Any]) -> str:
    text = f"{run.get('seconds', '?')} c"
    if "network" in run:
        text += f", network={run['network']}, cache_hits={run.get('cache_hits', '?')}"
    return text


def _pct(part: int, total: int) -> str:
    return f"{part / total * 100:.0f}%" if total else "n/a"
