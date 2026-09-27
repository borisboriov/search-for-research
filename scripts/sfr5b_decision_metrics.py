"""Метрики для решения о расширении базы НР (SFR-5b, #92): «5 538 → N».

Success@k сам по себе не отвечает на вопрос «стоит ли снимать квоту»: он
может просесть из-за разбавления (новые люди с оценкой ≤1 вытеснили старых
с оценкой 2), а может — из-за того, что новые релевантные люди вытеснили
старых релевантных (это нормально). Скрипт различает эти случаи по двум
прогонам одного набора запросов на старом и новом индексе.

Что считается (SPEC_SFR5b §6.4):

* **coverage gain** — доля запросов, у которых в топ-5 появился хотя бы один
  **новый** НР (его не было в ``profiles_sfr5.jsonl``); доля, где новый НР
  оценён grade 2; доля, где **топ-1 стал новым**;
* **displacement** — сколько старых НР с оценкой 2 вылетели из топ-5 и кем
  занято освободившееся место: новым grade 2 (нейтрально/хорошо), новым
  grade ≤1 (плохо — «разбавление») или старым;
* **разнообразие организаций** — число различных вузов в объединении топ-10
  по всем запросам было/стало и распределение вузов в топ-5;
* **сдвиг шкалы** — медиана top-1 score по golden и по OOD было/стало.

Ловушка, ради которой здесь есть ``aliases``: дедупликация нового каталога
может склеить автора, на котором стоят оценки SFR-5, в другой канонический id.
Без учёта склеек тот же человек выглядел бы как «новый», а его уход из топ-5 —
как «вытеснение». Поэтому id приводятся к каноническому, «старый» — значит
«его id или любой склеенный в него id был в старом каталоге», оценка пары —
максимум по всей группе склейки. Число пар, которых это коснулось, выводится.

Неоценённые пары считаются grade 0 — это пессимистичная оценка, и число
неоценённых пар в топ-5 выводится рядом с каждой цифрой.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median
from typing import Any

from sfr_match.evalset import Judgment, Query, load_judgments, load_queries, query_set_path
from sfr_match.evaluate import Run, load_run
from sfr_match.metrics import success_at_k

TOP = 5
DIVERSITY_DEPTH = 10
# Запросы, перемеченные из out-of-domain в in-domain на ревью SFR-5: набор
# «те же 22», сравнимый с SFR-2, — это действующие in-domain без них.
RELABELLED_IN_DOMAIN = frozenset({"q29", "q30"})


@dataclass
class Catalogue:
    """Что известно о профилях одного каталога: id и организация."""

    institutions: dict[str, str]

    @property
    def ids(self) -> set[str]:
        return set(self.institutions)


@dataclass
class Aliases:
    """Склейки нового каталога: дубль → канонический id."""

    to_canonical: dict[str, str] = field(default_factory=dict)

    def canonical(self, author_id: str) -> str:
        return self.to_canonical.get(author_id, author_id)

    def group(self, author_id: str) -> set[str]:
        root = self.canonical(author_id)
        return {root} | {dup for dup, canon in self.to_canonical.items() if canon == root}


def load_catalogue(path: Path) -> Catalogue:
    institutions: dict[str, str] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                record = json.loads(line)
                institutions[str(record["id"])] = str(record.get("institution") or "")
    return Catalogue(institutions=institutions)


def load_aliases_from_db(db_path: Path) -> Aliases:
    """Склейки из копии БД эксперимента (``authors.merged_into_id``)."""
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "select d.openalex_id, c.openalex_id from authors d "
            "join authors c on d.merged_into_id = c.id"
        ).fetchall()
    finally:
        connection.close()
    return Aliases({str(dup): str(canon) for dup, canon in rows})


class Grader:
    """Оценка пары с учётом склеек; неоценённое = 0, но это запоминается."""

    def __init__(self, judgments: dict[tuple[str, str], Judgment], aliases: Aliases) -> None:
        self._judgments = judgments
        self._aliases = aliases
        # Пары (запрос, автор), где оценка нашлась только через склеенный id.
        # Множество, а не счётчик: grade() зовётся для одного автора несколько
        # раз за запрос, и счётчик вызовов завышал бы цифру (находка ревью).
        self._alias_pairs: set[tuple[str, str]] = set()

    @property
    def alias_hits(self) -> int:
        return len(self._alias_pairs)

    def grade(self, query_id: str, author_id: str) -> int | None:
        direct = self._judgments.get((query_id, author_id))
        if direct is not None:
            return direct.grade
        via_alias = [
            self._judgments[(query_id, other)].grade
            for other in self._aliases.group(author_id)
            if (query_id, other) in self._judgments
        ]
        if via_alias:
            self._alias_pairs.add((query_id, author_id))
            return max(via_alias)
        return None


def _top(run: Run, query_id: str, depth: int, aliases: Aliases) -> list[str]:
    """Топ-``depth`` канонических id без повторов (склейка могла сдвоить)."""
    seen: list[str] = []
    for author_id in run.ranked_ids(query_id):
        canon = aliases.canonical(author_id)
        if canon not in seen:
            seen.append(canon)
        if len(seen) == depth:
            break
    return seen


def _is_old(author_id: str, old: Catalogue, aliases: Aliases) -> bool:
    return any(member in old.ids for member in aliases.group(author_id))


def per_query_shift(
    query: Query,
    before: Run,
    after: Run,
    grader: Grader,
    old: Catalogue,
    aliases: Aliases,
) -> dict[str, Any]:
    """Одна строка сравнения для запроса: кто пришёл, кто ушёл, с какими оценками."""
    top_before = _top(before, query.id, TOP, aliases)
    top_after = _top(after, query.id, TOP, aliases)

    def graded(author_id: str) -> int:
        value = grader.grade(query.id, author_id)
        return 0 if value is None else value

    new_in_top5 = [a for a in top_after if not _is_old(a, old, aliases)]
    entrants = [a for a in top_after if a not in top_before]
    displaced_relevant = [a for a in top_before if a not in top_after and graded(a) >= 2]
    entrant_kinds = Counter(
        "old" if _is_old(a, old, aliases) else ("new_grade2" if graded(a) >= 2 else "new_grade_le1")
        for a in entrants
    )
    unjudged_after = sum(1 for a in top_after if grader.grade(query.id, a) is None)
    grades_before = [graded(a) for a in top_before]
    grades_after = [graded(a) for a in top_after]
    return {
        "id": query.id,
        "expect": query.expect,
        "top1_before": before.top_score(query.id),
        "top1_after": after.top_score(query.id),
        "s1_before": success_at_k(grades_before, 1),
        "s1_after": success_at_k(grades_after, 1),
        "s5_before": success_at_k(grades_before, TOP),
        "s5_after": success_at_k(grades_after, TOP),
        "new_in_top5": len(new_in_top5),
        "new_grade2_in_top5": sum(1 for a in new_in_top5 if graded(a) >= 2),
        "top1_is_new": bool(top_after) and not _is_old(top_after[0], old, aliases),
        "displaced_grade2": len(displaced_relevant),
        "entrants": dict(entrant_kinds),
        "unjudged_in_top5_after": unjudged_after,
        "top5_before": top_before,
        "top5_after": top_after,
    }


def _share(rows: list[dict[str, Any]], key: str) -> float:
    return round(sum(1 for r in rows if r[key]) / len(rows), 3) if rows else 0.0


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Сводка coverage gain / displacement по списку строк ``per_query_shift``."""
    entrants: Counter[str] = Counter()
    for row in rows:
        entrants.update(row["entrants"])
    return {
        "n_queries": len(rows),
        "success_at_1": {"before": _share(rows, "s1_before"), "after": _share(rows, "s1_after")},
        "success_at_5": {"before": _share(rows, "s5_before"), "after": _share(rows, "s5_after")},
        "coverage_gain": {
            "queries_with_new_in_top5": _share(rows, "new_in_top5"),
            "queries_with_new_grade2_in_top5": _share(rows, "new_grade2_in_top5"),
            "queries_top1_new": _share(rows, "top1_is_new"),
        },
        "displacement": {
            "old_grade2_left_top5": sum(r["displaced_grade2"] for r in rows),
            "queries_with_displaced_grade2": sum(1 for r in rows if r["displaced_grade2"]),
            "entrants_new_grade2": entrants.get("new_grade2", 0),
            "entrants_new_grade_le1": entrants.get("new_grade_le1", 0),
            "entrants_old": entrants.get("old", 0),
        },
        "unjudged_pairs_in_top5_after": sum(r["unjudged_in_top5_after"] for r in rows),
    }


def _institution(catalogue: Catalogue, author_id: str, aliases: Aliases) -> str:
    """Организация автора: по его id, иначе по любому id из группы склейки."""
    for member in [author_id, *sorted(aliases.group(author_id))]:
        if member in catalogue.institutions:
            return catalogue.institutions[member]
    return "?"


def institution_diversity(
    run: Run, queries: list[Query], catalogue: Catalogue, aliases: Aliases
) -> dict[str, Any]:
    """Сколько разных организаций в объединении топ-10 и как они делят топ-5."""
    union: set[str] = set()
    top5: Counter[str] = Counter()
    for query in queries:
        for author_id in _top(run, query.id, DIVERSITY_DEPTH, aliases):
            union.add(_institution(catalogue, author_id, aliases))
        for author_id in _top(run, query.id, TOP, aliases):
            top5[_institution(catalogue, author_id, aliases)] += 1
    total = sum(top5.values()) or 1
    return {
        "distinct_in_top10_union": len(union),
        "top5_by_institution": {
            name: {"n": n, "share": round(n / total, 3)} for name, n in top5.most_common()
        },
        "top5_max_share": round(top5.most_common(1)[0][1] / total, 3) if top5 else 0.0,
    }


def _median_top1(run: Run, queries: list[Query]) -> float | None:
    scores = [s for q in queries if (s := run.top_score(q.id)) is not None]
    return round(median(scores), 4) if scores else None


def decision_metrics(
    *,
    golden: list[Query],
    external: list[Query],
    ood: list[Query],
    before: Run,
    after: Run,
    ood_before: Run,
    ood_after: Run,
    ext_before: Run | None,
    ext_after: Run | None,
    judgments: dict[tuple[str, str], Judgment],
    old: Catalogue,
    new: Catalogue,
    aliases: Aliases,
) -> dict[str, Any]:
    """Чистая функция: все метрики решения по прогонам и каталогам."""
    grader = Grader(judgments, aliases)
    in_domain = [q for q in golden if q.expect == "in-domain"]
    same22 = [q for q in in_domain if q.id not in RELABELLED_IN_DOMAIN]
    edge = [q for q in golden if q.expect == "edge"]

    rows_golden = [per_query_shift(q, before, after, grader, old, aliases) for q in in_domain]
    rows_edge = [per_query_shift(q, before, after, grader, old, aliases) for q in edge]
    rows_ext: list[dict[str, Any]] = []
    if ext_before is not None and ext_after is not None:
        rows_ext = [
            per_query_shift(q, ext_before, ext_after, grader, old, aliases) for q in external
        ]
    by_id = {r["id"]: r for r in rows_golden}
    rows_22 = [by_id[q.id] for q in same22]

    diversity_queries = in_domain + edge
    return {
        "corpus": {
            "before": len(old.ids),
            "after": len(new.ids),
            "aliases": len(aliases.to_canonical),
        },
        "index_version": {"before": before.index_version, "after": after.index_version},
        "sets": {
            "golden_in_domain_24": summarize(rows_golden),
            "golden_same_22": summarize(rows_22),
            "golden_edge": summarize(rows_edge),
            "external": summarize(rows_ext),
            "headline_golden24_plus_external": summarize(rows_golden + rows_ext),
        },
        "institutions": {
            "before": institution_diversity(before, diversity_queries, old, aliases),
            "after": institution_diversity(after, diversity_queries, new, aliases),
        },
        "scale_shift": {
            "golden_in_domain_median_top1": {
                "before": _median_top1(before, in_domain),
                "after": _median_top1(after, in_domain),
            },
            "golden_edge_median_top1": {
                "before": _median_top1(before, edge),
                "after": _median_top1(after, edge),
            },
            "ood_median_top1": {
                "before": _median_top1(ood_before, ood),
                "after": _median_top1(ood_after, ood),
            },
            "ood_max_top1": {
                "before": max(
                    (s for q in ood if (s := ood_before.top_score(q.id)) is not None), default=None
                ),
                "after": max(
                    (s for q in ood if (s := ood_after.top_score(q.id)) is not None), default=None
                ),
            },
        },
        "judgments_via_alias": grader.alias_hits,
        "per_query": {
            "golden": rows_golden + rows_edge,
            "external": rows_ext,
        },
    }


def render_table(payload: dict[str, Any]) -> str:
    """Таблица для отчёта: одна строка на набор запросов."""
    lines = [
        "| Набор | n | S@1 было → стало | S@5 было → стало | новый НР в топ-5 "
        "| новый с оценкой 2 | топ-1 новый | старых grade-2 ушло "
        "| пришло: новых g2 / новых g≤1 / старых | неоценённых пар |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for name, s in payload["sets"].items():
        if not s["n_queries"]:
            continue
        cg, d = s["coverage_gain"], s["displacement"]
        lines.append(
            f"| {name} | {s['n_queries']} "
            f"| {s['success_at_1']['before']:.1%} → {s['success_at_1']['after']:.1%} "
            f"| {s['success_at_5']['before']:.1%} → {s['success_at_5']['after']:.1%} "
            f"| {cg['queries_with_new_in_top5']:.1%} | {cg['queries_with_new_grade2_in_top5']:.1%} "
            f"| {cg['queries_top1_new']:.1%} | {d['old_grade2_left_top5']} "
            f"| {d['entrants_new_grade2']} / {d['entrants_new_grade_le1']} / {d['entrants_old']} "
            f"| {s['unjudged_pairs_in_top5_after']} |"
        )
    inst = payload["institutions"]
    lines += [
        "",
        f"Организаций в объединении топ-10: {inst['before']['distinct_in_top10_union']} → "
        f"{inst['after']['distinct_in_top10_union']}; максимальная доля одного вуза в топ-5: "
        f"{inst['before']['top5_max_share']:.1%} → {inst['after']['top5_max_share']:.1%}.",
    ]
    shift = payload["scale_shift"]
    golden_shift, ood_shift = shift["golden_in_domain_median_top1"], shift["ood_median_top1"]
    lines.append(
        f"Медиана top-1: golden {golden_shift['before']} → {golden_shift['after']}, "
        f"OOD {ood_shift['before']} → {ood_shift['after']} "
        f"(максимум OOD {shift['ood_max_top1']['before']} → {shift['ood_max_top1']['after']})."
    )
    return "\n".join(lines)


def _optional_run(path: Path) -> Run | None:
    return load_run(path) if path.exists() else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, default=Path("data/eval/runs_sfr5/frida_clean.json"))
    parser.add_argument("--after", type=Path, default=Path("data/eval/runs_sfr5b/frida_clean.json"))
    parser.add_argument(
        "--ood-before", type=Path, default=Path("data/eval/runs_ood_sfr5/frida_clean.json")
    )
    parser.add_argument(
        "--ood-after", type=Path, default=Path("data/eval/runs_ood_sfr5b/frida_clean.json")
    )
    parser.add_argument(
        "--ext-before", type=Path, default=Path("data/eval/runs_external_sfr5/frida_clean.json")
    )
    parser.add_argument(
        "--ext-after", type=Path, default=Path("data/eval/runs_external_sfr5b/frida_clean.json")
    )
    parser.add_argument(
        "--profiles-before", type=Path, default=Path("data/exports/profiles_sfr5.jsonl")
    )
    parser.add_argument(
        "--profiles-after", type=Path, default=Path("data/exports/profiles_sfr5b.jsonl")
    )
    parser.add_argument("--db", type=Path, default=Path("data/sfr5b.db"), help="Склейки из БД")
    parser.add_argument(
        "--out", type=Path, default=Path("docs/metrics/sfr5b_decision_metrics.json")
    )
    args = parser.parse_args()

    if args.db.exists():
        aliases = load_aliases_from_db(args.db)
    else:
        # Без карты склеек «старый/новый» делится неверно: дубль старого профиля
        # выглядит новым человеком. Молчать нельзя — это портит displacement.
        print(
            f"ВНИМАНИЕ: {args.db} не найдена — метрики считаются БЕЗ учёта склеек, "
            "старые профили, склеенные в новые id, будут учтены как новые.",
            file=sys.stderr,
        )
        aliases = Aliases()
    payload = decision_metrics(
        golden=load_queries(query_set_path("golden")),
        external=load_queries(query_set_path("external")),
        ood=load_queries(query_set_path("ood")),
        before=load_run(args.before),
        after=load_run(args.after),
        ood_before=load_run(args.ood_before),
        ood_after=load_run(args.ood_after),
        ext_before=_optional_run(args.ext_before),
        ext_after=_optional_run(args.ext_after),
        judgments=load_judgments(),
        old=load_catalogue(args.profiles_before),
        new=load_catalogue(args.profiles_after),
        aliases=aliases,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(render_table(payload))
    print(
        f"\nоценок найдено через склеенный id: {payload['judgments_via_alias']}; "
        f"полные данные → {args.out}"
    )


if __name__ == "__main__":
    main()
