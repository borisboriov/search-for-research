"""Решающие пары трёх точек: пул на пересуд и раздел выборки для человека.

«Решающая пара» (§6.3 SPEC_SFR5c) — пара (запрос, НР) из топ-5 запроса, у
которого **Success@1, Success@5 или личность топ-1 отличаются хотя бы между
двумя** из трёх точек (5 538 / потолок / 12 119). Именно из-за этих пар
рекомендация «выкладывать / не выкладывать» выглядит так, как выглядит: если
оценка одной такой пары неверна, вывод меняется. Поэтому их судят заново —
отдельный судья, отдельный файл, ``judgments.jsonl`` не трогается.

Два выхода:

* **пул на пересуд** — JSONL в формате ``sfr-match pool`` (``query_id``,
  ``author_id``, ``query``, ``name``, ``topics``, ``profile_text``),
  отсортированный **по ``author_id``** и **без пометки, из какой точки пришла
  пара**: судья не должен знать, какой каталог её выдал, иначе он подтверждает
  ожидание, а не оценивает профиль. По той же причине в нём нет прежней оценки.
* **раздел «Решающие пары»** для ``judgments_for_review_sfr5c.md`` — там,
  наоборот, человеку показывается всё: три точки, позиции, оценки и названия
  работ (#107: оценка ставится по работам, а не по темам OpenAlex).
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sfr_match.evalset import Judgment, Query, load_judgments, load_queries, query_set_path
from sfr_match.evaluate import Run, load_run
from sfr_match.metrics import success_at_k
from sfr_match.report import profile_works

TOP = 5


def cap_label(n_profiles: int) -> str:
    """Подпись точки «потолок» — по числу профилей её прогона, а не константой.

    Константа «потолок 9 010» пережила пересборку каталога до 9 002: цель,
    запущенная на текущем каталоге, подписывала бы его чужим числом (ревью
    выкладки SFR-5c). Число берётся из тех же данных, что и строки таблицы.
    """
    return f"потолок {n_profiles:,}".replace(",", " ")


@dataclass
class PointRuns:
    """Одна точка: как называется, что нашла, какие у неё профили."""

    name: str
    run: Run
    profiles: dict[str, dict[str, Any]]


@dataclass
class Rejudge:
    """Один прогон пересуда: как его называть в колонке и что он поставил."""

    label: str
    grades: dict[tuple[str, str], Judgment]

    @classmethod
    def parse(cls, spec: str) -> Rejudge:
        """``v2=path/to/file.jsonl`` или просто ``path`` (метка — имя файла)."""
        label, sep, raw = spec.partition("=")
        path = Path(raw if sep else spec)
        return cls(label=label if sep else path.stem, grades=load_judgments(path))


def load_profiles(path: Path) -> dict[str, dict[str, Any]]:
    """``profiles_*.jsonl`` → id → запись (имя, вуз, темы, profile_text)."""
    out: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                record = json.loads(line)
                out[str(record["id"])] = record
    return out


def _grade(judgments: dict[tuple[str, str], Judgment], query_id: str, author_id: str) -> int:
    judgment = judgments.get((query_id, author_id))
    return 0 if judgment is None else judgment.grade


def _grades(
    judgments: dict[tuple[str, str], Judgment],
    rejudged: Sequence[Rejudge],
    query_id: str,
    author_id: str,
) -> str:
    """«2», «2 = 2 = 2» или «1 → 2 → 2 ⚠»: накопленная оценка и все пересуды.

    Пересудов может быть несколько (v1 и v2 SFR-5c): человек должен видеть все
    колонки сразу, иначе он сравнивает файл с файлом руками (#114). ⚠ ставится,
    если хоть одна колонка разошлась с любой другой.
    """
    first = _grade(judgments, query_id, author_id)
    if not rejudged:
        return str(first)
    cells = [str(first)]
    grades = [first]
    for pass_ in rejudged:
        judgment = pass_.grades.get((query_id, author_id))
        # «?» — пары нет в этом прогоне пересуда (пул пересуда мог быть уже).
        cells.append("?" if judgment is None else str(judgment.grade))
        if judgment is not None:
            grades.append(judgment.grade)
    if len(set(grades)) == 1 and "?" not in cells:
        return " = ".join(cells)
    return " → ".join(cells) + (" ⚠" if len(set(grades)) > 1 else "")


def decisive_queries(
    queries: Sequence[Query],
    points: Sequence[PointRuns],
    judgments: dict[tuple[str, str], Judgment],
) -> list[dict[str, Any]]:
    """Запросы, у которых хоть одна из трёх величин разошлась между точками.

    Сравниваются все пары точек, а не только «база → новая»: запрос, одинаковый
    на базе и на потолке, но другой на полном каталоге, тоже решающий — он
    показывает, что именно потолок удержал.
    """
    rows: list[dict[str, Any]] = []
    for query in queries:
        per_point = {}
        for point in points:
            top = point.run.ranked_ids(query.id)[:TOP]
            grades = [_grade(judgments, query.id, author_id) for author_id in top]
            per_point[point.name] = {
                "top5": top,
                "s1": success_at_k(grades, 1),
                "s5": success_at_k(grades, TOP),
                "top1": top[0] if top else None,
                "top1_score": point.run.top_score(query.id),
            }
        values = list(per_point.values())
        changed = [
            key for key in ("s1", "s5", "top1") if len({json.dumps(v[key]) for v in values}) > 1
        ]
        if changed:
            rows.append({"query": query, "changed": changed, "points": per_point})
    return rows


def rejudge_pool(
    rows: Sequence[dict[str, Any]], points: Sequence[PointRuns]
) -> list[dict[str, Any]]:
    """Пары на пересуд: уникальные, по ``author_id``, без следа своей точки.

    ``profile_text`` берётся из последней точки, в которой автор есть: корпус
    рос, и у более позднего профиля больше работ — судить надо по самому полному.
    """
    pairs: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        query: Query = row["query"]
        for point in points:
            for author_id in row["points"][point.name]["top5"]:
                record = point.profiles.get(author_id)
                if record is None:
                    continue
                pairs[(query.id, author_id)] = {
                    "query_id": query.id,
                    "author_id": author_id,
                    "query": query.text,
                    "expect": query.expect,
                    "name": record["name"],
                    "topics": record.get("topics") or [],
                    "profile_text": record.get("profile_text") or "",
                }
    return [pairs[key] for key in sorted(pairs, key=lambda k: (k[1], k[0]))]


def _disagreements(judgments: dict[tuple[str, str], Judgment], pass_: Rejudge) -> int:
    """Сколько пар этого прогона разошлись с накопленной разметкой."""
    return sum(
        1
        for key, value in pass_.grades.items()
        if key in judgments and judgments[key].grade != value.grade
    )


def render_decisive_section(
    rows: Sequence[dict[str, Any]],
    points: Sequence[PointRuns],
    judgments: dict[tuple[str, str], Judgment],
    rejudged: Sequence[Rejudge] = (),
) -> str:
    """Раздел «Решающие пары» для человека: три точки рядом, с работами.

    ``rejudged`` — прогоны пересуда. Если они есть, у каждой пары печатаются
    **все** оценки в одну строку: расхождение судей на решающей паре — первое,
    что стоит смотреть человеку, и искать его по нескольким файлам он не должен.
    """
    names = [point.name for point in points]
    lines = [
        "# Решающие пары трёх точек — обязательный раздел выборки (§6.3 SPEC_SFR5c)",
        "",
        f"Запросов, у которых Success@1, Success@5 или топ-1 разошлись хотя бы между "
        f"двумя из трёх каталогов: **{len(rows)}**. Для каждого — топ-5 всех трёх "
        "точек с оценками и названиями работ. Оценка ставится **по работам**, а не "
        "по темам OpenAlex (#107).",
        "",
        "Колонки точек: " + " · ".join(f"**{name}**" for name in names) + ".",
        "",
    ]
    if rejudged:
        columns = " → ".join(["**было**"] + [f"**{p.label}**" for p in rejudged])
        counts = ", ".join(
            f"{p.label}: {len(p.grades)} пар, расхождений с накопленной "
            f"{_disagreements(judgments, p)}"
            for p in rejudged
        )
        lines += [
            f"Оценки печатаются как {columns} ({counts}). Судья не независим от "
            "разметки конструктивно — слеп пул, а не он (§6 отчёта). Пары, где хоть "
            "одна колонка разошлась с другой, помечены ⚠ — смотреть их первыми.",
            "",
        ]
    for row in rows:
        query: Query = row["query"]
        lines += [
            f"## `{query.id}` — {query.text}",
            "",
            f"*Разошлось:* {', '.join(row['changed'])}. *Тип запроса:* {query.expect}.",
            "",
            "| Каталог | S@1 | S@5 | top-1 score | Топ-5 (оценка) |",
            "|---|---|---|---|---|",
        ]
        for point in points:
            state = row["points"][point.name]
            top = ", ".join(
                f"`{a}` ({_grades(judgments, rejudged, query.id, a)})" for a in state["top5"]
            )
            score = "—" if state["top1_score"] is None else f"{state['top1_score']:.3f}"
            lines.append(
                f"| {point.name} | {int(state['s1'])} | {int(state['s5'])} | {score} | {top} |"
            )
        lines.append("")
        seen: set[str] = set()
        for point in points:
            for author_id in row["points"][point.name]["top5"]:
                if author_id in seen:
                    continue
                seen.add(author_id)
                record = point.profiles.get(author_id)
                if record is None:
                    continue
                works = profile_works(str(record.get("profile_text") or ""))
                lines += [
                    f"- `{author_id}` **{record['name']}** — {record.get('institution') or '?'}; "
                    f"оценка **{_grades(judgments, rejudged, query.id, author_id)}**",
                    f"  - работы: {'; '.join(works) or '—'}",
                ]
        lines.append("")
    return "\n".join(lines)


def render_review_file(decisive: str, sample: str | None) -> str:
    """Оба раздела выборки в один файл — тот, который читает человек.

    Раньше файл склеивался руками, и повторный прогон его не воспроизводил
    (#114). Заголовки первого уровня у частей срезаются: в собранном файле H1
    один, а части — H2.
    """

    def body(text: str) -> str:
        lines = text.splitlines()
        if lines and lines[0].startswith("# "):
            lines = lines[1:]
        return "\n".join(lines).strip("\n")

    parts = [
        "# Судейские оценки SFR-5c — выборка для ручной проверки",
        "",
        "Два раздела. **Первый — «Решающие пары»** (обязательный, §6.3 спеки): "
        "пары, из-за которых метрики трёх каталогов расходятся, со всеми "
        "оценками, которые по ним есть, — смотреть их первыми, начиная с "
        "помеченных ⚠. **Второй — случайная выборка** из новой партии оценок "
        "этой итерации.",
        "",
        "Порог из спеки: **≥4 расхождений из 20** в случайной выборке → партию "
        "надо пересуживать. В решающих парах расхождение судей — не повод "
        "пересуживать, а повод решить, какое чтение рубрики верное: вердикт "
        "человека здесь и есть истина.",
        "",
        "---",
        "",
        "## Часть 1. Решающие пары трёх точек",
        "",
        body(decisive),
    ]
    if sample is not None:
        parts += ["", "---", "", "## Часть 2. Случайная выборка новой партии", "", body(sample)]
    return "\n".join(parts) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool-out", type=Path, default=Path("data/eval/pool_rejudge_sfr5c.jsonl"))
    parser.add_argument(
        "--section-out",
        type=Path,
        default=Path("data/eval/judgments_decisive_sfr5c.md"),
    )
    parser.add_argument(
        "--rejudged",
        action="append",
        default=[],
        metavar="LABEL=PATH",
        help="Прогон пересуда: печатать его колонкой «было → …». Можно несколько раз",
    )
    parser.add_argument(
        "--sample",
        type=Path,
        default=None,
        help="Готовая случайная выборка (`sfr-match review-sample`) — второй раздел --out",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Собранный файл выборки для человека: оба раздела и общий заголовок",
    )
    # Точка «потолок» пересобирается при выкладке (#98), поэтому её пути —
    # аргументы: измерения §4–§6 воспроизводятся по архивным `*_9010`.
    parser.add_argument(
        "--cap-name",
        default=None,
        help="Подпись точки «потолок»; по умолчанию — «потолок N» по числу профилей прогона",
    )
    parser.add_argument("--cap-runs", type=Path, default=Path("data/eval/runs_sfr5c"))
    parser.add_argument(
        "--cap-profiles", type=Path, default=Path("data/exports/profiles_sfr5c.jsonl")
    )
    args = parser.parse_args()

    cap_run = load_run(args.cap_runs / "frida_clean.json")
    points = [
        PointRuns(
            name="5 538",
            run=load_run(Path("data/eval/runs_sfr5/frida_clean.json")),
            profiles=load_profiles(Path("data/exports/profiles_sfr5.jsonl")),
        ),
        PointRuns(
            name=args.cap_name or cap_label(cap_run.n_profiles),
            run=cap_run,
            profiles=load_profiles(args.cap_profiles),
        ),
        PointRuns(
            name="12 119",
            run=load_run(Path("data/eval/runs_sfr5b/frida_clean.json")),
            profiles=load_profiles(Path("data/exports/profiles_sfr5b.jsonl")),
        ),
    ]
    judgments = load_judgments()
    queries = load_queries(query_set_path("golden"))
    rows = decisive_queries(queries, points, judgments)
    pool = rejudge_pool(rows, points)

    args.pool_out.parent.mkdir(parents=True, exist_ok=True)
    with args.pool_out.open("w", encoding="utf-8") as handle:
        for record in pool:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    rejudged = [Rejudge.parse(spec) for spec in args.rejudged]
    section = render_decisive_section(rows, points, judgments, rejudged)
    args.section_out.parent.mkdir(parents=True, exist_ok=True)
    args.section_out.write_text(section, encoding="utf-8")
    if args.out is not None:
        sample = args.sample.read_text(encoding="utf-8") if args.sample is not None else None
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(render_review_file(section, sample), encoding="utf-8")
    print(
        f"решающих запросов: {len(rows)} "
        f"({', '.join(r['query'].id for r in rows)}); "
        f"пар на пересуд: {len(pool)} → {args.pool_out}; раздел → {args.section_out}"
        + (f"; выборка → {args.out}" if args.out is not None else "")
    )


if __name__ == "__main__":
    main()
