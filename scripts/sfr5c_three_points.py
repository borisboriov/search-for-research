"""Три точки каталога одной таблицей: 5 538 (квота) → потолок → 12 119 (без квоты).

`scripts/sfr5b_decision_metrics.py` сравнивает **две** точки, и в нём вся логика
coverage gain / displacement / разнообразия вузов. Этот скрипт его не
переписывает: он дважды вызывает ``decision_metrics`` от одной базы 5 538 —
к каталогу с потолком (склейки из ``data/sfr5c.db``) и к каталогу без квоты
(склейки из ``data/sfr5b.db``, **пересчитываются заново**, а не берутся из
``docs/metrics/sfr5b_decision_metrics.json``: так поправка судейства #94 гарантированно
попадает в обе правые колонки) — и рендерит одну таблицу на три колонки.

Почему база одна для обеих правых точек: «новый НР» — это человек, которого не
было в каталоге 5 538, и вытеснение считается относительно того же топ-5. Взяв
разные базы, колонки нельзя было бы поставить рядом.

**Два варианта метрик.** Судейство пар делает агент, поэтому решающие пары
(те, из-за которых Success@k двигается) пересуживаются отдельным прогоном судьи.
Таблица считается дважды: по ``judgments.jsonl`` как есть и с подстановкой
пересуженных оценок. Расхождения печатаются отдельной таблицей — она и есть мера
доверия к цифрам.

По умолчанию подставляется **v2** (``judgments_rejudge_sfr5c_v2.jsonl``) — прогон
по рубрике без правила «сомневаешься между 1 и 2 — ставь 1», которое ревью SFR-5c
нашло в рубрике первого пересуда. Файл v1 остаётся в репозитории и читается
флагом ``--rejudged``; сравнение трёх разметок по классам —
``scripts/sfr5c_rejudge_classes.py``.

Оговорка про базу (§6.5 спеки): «старый» = id (или любой склеенный в него) есть
в ``profiles_sfr5.jsonl`` — это 5 538 профилей на 06.09. Копия БД стартует с
5 541: три расклеенных 26.09 дубля (``A5073953503``, ``A5007427934``,
``A5101454427``) относительно этой базы выглядят новыми людьми, хотя это
разделённые профили уже known людей. Их список печатается в JSON, чтобы в
отчёте они не считались приростом покрытия.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sfr5b_decision_metrics import (
    Aliases,
    Catalogue,
    decision_metrics,
    load_aliases_from_db,
    load_catalogue,
)

from sfr_match.evalset import Judgment, load_judgments, load_queries, query_set_path, split_stale
from sfr_match.evaluate import Run, load_run
from sfr_match.index import profile_fingerprints

# Три профиля, расклеенные руками 26.09 (#108): в базе 5 538 их нет, но это не
# новые люди. Список короткий и осознанный — хардкод честнее, чем «вычислить».
UNMERGED_2609 = ("A5073953503", "A5007427934", "A5101454427")

SET_TITLES = {
    "golden_in_domain_24": "golden in-domain, 24",
    "golden_same_22": "те же 22",
    "golden_edge": "edge, 6",
    "external": "external, 1",
    "headline_golden24_plus_external": "golden 24 + external",
}


@dataclass
class Point:
    """Одна точка сравнения: прогоны, состав каталога, склейки, пороги индекса."""

    name: str
    golden: Run
    ood: Run
    external: Run | None
    catalogue: Catalogue
    aliases: Aliases
    thresholds: dict[str, float] | None = None
    # #123: индекс точки — для сверки отпечатков профилей в оценках.
    index_root: Path | None = None

    @property
    def size(self) -> int:
        return len(self.catalogue.ids)


def load_rejudged(path: Path) -> dict[tuple[str, str], Judgment]:
    """Пересуженные решающие пары — отдельный файл, ``judgments.jsonl`` не тронут."""
    return load_judgments(path)


def overlay_judgments(
    judgments: dict[tuple[str, str], Judgment], rejudged: dict[tuple[str, str], Judgment]
) -> dict[tuple[str, str], Judgment]:
    """Пересуженная оценка перекрывает прежнюю; новые пары просто добавляются."""
    merged = dict(judgments)
    merged.update(rejudged)
    return merged


def rejudge_diff(
    judgments: dict[tuple[str, str], Judgment], rejudged: dict[tuple[str, str], Judgment]
) -> list[dict[str, Any]]:
    """Где второй судья разошёлся с первым — построчно, включая формулировки."""
    rows: list[dict[str, Any]] = []
    for key, new in sorted(rejudged.items()):
        old = judgments.get(key)
        if old is not None and old.grade == new.grade:
            continue
        rows.append(
            {
                "query_id": key[0],
                "author_id": key[1],
                "grade_before": None if old is None else old.grade,
                "grade_after": new.grade,
                "rationale_before": "" if old is None else old.rationale,
                "rationale_after": new.rationale,
                "iteration_before": "" if old is None else old.iteration,
                "judge_after": new.judge,
            }
        )
    return rows


def read_thresholds(index_dir: Path) -> dict[str, float] | None:
    """Пороги из ``meta.json`` индекса; у свежего индекса их ещё нет — это не ошибка."""
    meta_path = index_dir / "meta.json"
    if not meta_path.exists():
        return None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    thresholds = meta.get("thresholds")
    return dict(thresholds) if isinstance(thresholds, dict) else None


def three_points(
    *,
    base: Point,
    cap: Point,
    full: Point,
    golden: list[Any],
    external: list[Any],
    ood: list[Any],
    judgments: dict[tuple[str, str], Judgment],
    stale: Mapping[str, set[tuple[str, str]]] | None = None,
) -> dict[str, Any]:
    """Две дельты от одной базы + состав точек. Чистая функция — вся логика тестируема.

    ``stale`` (#123) — по имени точки: оценки, профиль которых изменился после
    судейства относительно базы **или** этой точки; для точки они не берутся —
    пара считается неоценённой.
    """
    stale = stale or {}
    if len({base.name, cap.name, full.name}) != 3:
        raise ValueError("имена трёх точек должны различаться: это ключи JSON и колонки таблицы")
    payloads = {
        point.name: decision_metrics(
            golden=golden,
            external=external,
            ood=ood,
            before=base.golden,
            ood_before=base.ood,
            ext_before=base.external,
            judgments={k: v for k, v in judgments.items() if k not in stale.get(point.name, set())},
            old=base.catalogue,
            after=point.golden,
            ood_after=point.ood,
            ext_after=point.external,
            new=point.catalogue,
            aliases=point.aliases,
        )
        for point in (cap, full)
    }
    return {
        "points": {
            point.name: {
                "profiles": point.size,
                "index_version": point.golden.index_version,
                "thresholds": point.thresholds,
            }
            for point in (base, cap, full)
        },
        "base_caveat": {
            "profiles_in_base_export": base.size,
            "unmerged_2026_09_26": [
                author_id for author_id in UNMERGED_2609 if author_id not in base.catalogue.ids
            ],
            "note": (
                "расклеенные 26.09 профили относительно базы выглядят новыми людьми; "
                "это разделённые профили известных НР, не прирост покрытия"
            ),
        },
        "delta": payloads,
    }


def _pct(value: float) -> str:
    return f"{value:.1%}"


def render_three_points(payload: dict[str, Any], *, title: str) -> str:
    """Одна таблица на три колонки: базовая точка и две дельты от неё."""
    names = list(payload["points"])
    base_name, cap_name, full_name = names
    deltas = payload["delta"]
    sizes = {name: payload["points"][name]["profiles"] for name in names}
    lines = [
        f"**{title}.** Колонки — три каталога: "
        + ", ".join(f"{name} ({sizes[name]} профилей)" for name in names)
        + ". Относительные метрики (новые НР, вытеснение) считаются от базы, "
        "поэтому в её строке стоит «—».",
        "",
        "| Набор | Каталог | n | S@1 | S@5 | новый НР в топ-5 | новый с оценкой 2 "
        "| топ-1 новый | старых g2 ушло | пришло g2 / g≤1 | неоценённых |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for set_key, set_title in SET_TITLES.items():
        cap_set = deltas[cap_name]["sets"][set_key]
        if not cap_set["n_queries"]:
            continue
        n = cap_set["n_queries"]
        lines.append(
            f"| {set_title} | {base_name} ({sizes[base_name]}) | {n} "
            f"| {_pct(cap_set['success_at_1']['before'])} "
            f"| {_pct(cap_set['success_at_5']['before'])} | — | — | — | — | — | — |"
        )
        for name in (cap_name, full_name):
            s = deltas[name]["sets"][set_key]
            cg, d = s["coverage_gain"], s["displacement"]
            lines.append(
                f"| {set_title} | **{name} ({sizes[name]})** | {s['n_queries']} "
                f"| **{_pct(s['success_at_1']['after'])}** "
                f"| **{_pct(s['success_at_5']['after'])}** "
                f"| {_pct(cg['queries_with_new_in_top5'])} "
                f"| {_pct(cg['queries_with_new_grade2_in_top5'])} "
                f"| {_pct(cg['queries_top1_new'])} | {d['old_grade2_left_top5']} "
                f"| {d['entrants_new_grade2']} / {d['entrants_new_grade_le1']} "
                f"| {s['unjudged_pairs_in_top5_after']} |"
            )
    lines += ["", _render_institutions(payload), "", _render_scale(payload)]
    return "\n".join(lines)


def _render_institutions(payload: dict[str, Any]) -> str:
    """Распределение вузов в слотах топ-5 (30 запросов × 5 = 150) в три колонки."""
    names = list(payload["points"])
    base_name, cap_name, full_name = names
    deltas = payload["delta"]
    columns = {
        base_name: deltas[cap_name]["institutions"]["before"],
        cap_name: deltas[cap_name]["institutions"]["after"],
        full_name: deltas[full_name]["institutions"]["after"],
    }
    universities: list[str] = []
    for column in columns.values():
        for name in column["top5_by_institution"]:
            if name not in universities:
                universities.append(name)
    lines = [
        "**Вузы в слотах топ-5** (30 запросов × 5 слотов; «доля» — от 150 слотов):",
        "",
        "| Вуз | " + " | ".join(names) + " |",
        "|---|" + "---|" * len(names),
    ]
    for university in universities:
        cells = []
        for name in names:
            entry = columns[name]["top5_by_institution"].get(university)
            cells.append("—" if entry is None else f"{entry['n']} ({_pct(entry['share'])})")
        lines.append(f"| {university} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "Организаций в объединении топ-10: "
        + " → ".join(str(columns[name]["distinct_in_top10_union"]) for name in names)
        + "; максимальная доля одного вуза в топ-5: "
        + " → ".join(_pct(columns[name]["top5_max_share"]) for name in names)
        + ".",
    ]
    return "\n".join(lines)


def _render_scale(payload: dict[str, Any]) -> str:
    """Сдвиг шкалы и пороги трёх индексов — тоже три колонки."""
    names = list(payload["points"])
    _, cap_name, full_name = names
    deltas = payload["delta"]
    rows = {
        "медиана top-1, golden in-domain": "golden_in_domain_median_top1",
        "медиана top-1, edge": "golden_edge_median_top1",
        "медиана top-1, посторонние": "ood_median_top1",
        "максимум top-1, посторонние": "ood_max_top1",
    }
    lines = [
        "**Сдвиг шкалы и пороги.**",
        "",
        "| Величина | " + " | ".join(names) + " |",
        "|---|" + "---|" * len(names),
    ]
    for title, key in rows.items():
        cap_shift = deltas[cap_name]["scale_shift"][key]
        full_shift = deltas[full_name]["scale_shift"][key]
        lines.append(
            f"| {title} | {cap_shift['before']} | {cap_shift['after']} | {full_shift['after']} |"
        )
    thresholds = []
    for name in names:
        values = payload["points"][name]["thresholds"]
        thresholds.append(
            "не проштампованы"
            if not values
            else " / ".join(f"{values[k]}" for k in ("none", "weak", "high"))
        )
    lines.append("| пороги индекса (none / weak / high) | " + " | ".join(thresholds) + " |")
    lines += [
        "",
        "Версии индексов: "
        + "; ".join(f"{name} — `{payload['points'][name]['index_version']}`" for name in names)
        + ".",
    ]
    return "\n".join(lines)


def render_rejudge_table(rows: list[dict[str, Any]]) -> str:
    """Расхождения второго судьи с первым — отдельной таблицей, как требует §6 спеки."""
    if not rows:
        return "Расхождений с прежними оценками нет: пересуженные пары совпали до оценки."
    lines = [
        f"Расхождений: **{len(rows)}**.",
        "",
        "| Пара | было | стало | обоснование прежнее | обоснование пересуда |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        before = "—" if row["grade_before"] is None else row["grade_before"]
        lines.append(
            f"| `{row['query_id']}` × `{row['author_id']}` | {before} | **{row['grade_after']}** "
            f"| {row['rationale_before'] or '—'} | {row['rationale_after'] or '—'} |"
        )
    return "\n".join(lines)


def _point(
    name: str,
    *,
    runs: Path,
    ood_runs: Path,
    ext_runs: Path,
    profiles: Path,
    db: Path | None,
    index_root: Path,
) -> Point:
    variant = "frida_clean.json"
    return Point(
        name=name,
        golden=load_run(runs / variant),
        ood=load_run(ood_runs / variant),
        external=load_run(ext_runs / variant) if (ext_runs / variant).exists() else None,
        catalogue=load_catalogue(profiles),
        aliases=load_aliases_from_db(require_db(db)) if db is not None else Aliases(),
        thresholds=read_thresholds(index_root / "frida_clean"),
        index_root=index_root,
    )


def require_db(db: Path) -> Path:
    """БД точки обязана существовать: без неё карта склеек молча пуста.

    Прежде несуществующий путь давал пустой ``Aliases()`` без единого слова —
    и `--cap-suffix sfr5c_9010` без `--cap-db` считал точку «потолок» без
    склеек (ревью выкладки SFR-5c, #126). Точка без склеек задаётся явно
    (``db=None``, как у базы 5 538), а не опечаткой в пути.
    """
    if not db.exists():
        raise SystemExit(
            f"нет БД точки {db}: карта склеек была бы пустой. "
            "Для архива 9 010 — --cap-db data/backups/sfr5c_2026-09-26_before_decisions.db"
        )
    return db


def stale_by_point(
    judgments: dict[tuple[str, str], Judgment], base: Point, points: Sequence[Point]
) -> dict[str, set[tuple[str, str]]]:
    """Устаревшие оценки (#123) для каждой точки: относительно базы или точки.

    Строк с отпечатком нет (разметка до #123) — индексы даже не читаются, и
    результат совпадает с прежним байт в байт.
    """
    if not any(j.profile_fp for j in judgments.values()):
        return {}
    by_root: dict[Path, set[tuple[str, str]]] = {}
    for point in (base, *points):
        if point.index_root is not None and point.index_root not in by_root:
            _, counts, stale = split_stale(judgments, profile_fingerprints(point.index_root))
            by_root[point.index_root] = set(stale)
            print(
                f"{point.name}: оценок с отпечатком {counts['fresh'] + counts['stale']}, "
                f"устарели {counts['stale']} — для точки считаются неоценёнными"
            )
    base_stale = by_root.get(base.index_root, set()) if base.index_root else set()
    return {
        point.name: base_stale
        | (by_root.get(point.index_root, set()) if point.index_root else set())
        for point in points
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-name", default="5 538")
    parser.add_argument("--cap-name", default="потолок")
    parser.add_argument("--full-name", default="12 119")
    parser.add_argument(
        "--rejudged",
        type=Path,
        default=Path("packages/sfr-match/eval/judgments_rejudge_sfr5c_v2.jsonl"),
        help="Пересуженные решающие пары; нет файла — только вариант «как есть»",
    )
    parser.add_argument(
        "--out", type=Path, default=Path("docs/metrics/sfr5c_decision_metrics.json")
    )
    # Точка «потолок» пересобрана при выкладке (#98): 9 010 → 9 002. Её пути —
    # аргументы, чтобы §4 и §6 отчёта воспроизводились по архивным `*_9010`.
    parser.add_argument("--cap-suffix", default="sfr5c", help="Суффикс артефактов точки «потолок»")
    parser.add_argument("--cap-db", type=Path, default=None, help="По умолчанию data/<суффикс>.db")
    parser.add_argument(
        "--ood-queries",
        type=Path,
        default=None,
        help="Файл набора посторонних; по умолчанию — действующий (17 с 26.09). "
        "Архивные 19 — `make ood19-sfr5c`",
    )
    args = parser.parse_args()

    eval_dir = Path("data/eval")
    base = _point(
        args.base_name,
        runs=eval_dir / "runs_sfr5",
        ood_runs=eval_dir / "runs_ood_sfr5",
        ext_runs=eval_dir / "runs_external_sfr5",
        profiles=Path("data/exports/profiles_sfr5.jsonl"),
        db=None,  # база: склейки применяются к новому каталогу, не к ней
        index_root=Path("data/indexes_sfr5"),
    )
    cap_suffix = args.cap_suffix
    cap = _point(
        args.cap_name,
        runs=eval_dir / f"runs_{cap_suffix}",
        ood_runs=eval_dir / f"runs_ood_{cap_suffix}",
        ext_runs=eval_dir / f"runs_external_{cap_suffix}",
        profiles=Path(f"data/exports/profiles_{cap_suffix}.jsonl"),
        db=args.cap_db if args.cap_db is not None else Path(f"data/{cap_suffix}.db"),
        index_root=Path(f"data/indexes_{cap_suffix}"),
    )
    full = _point(
        args.full_name,
        runs=eval_dir / "runs_sfr5b",
        ood_runs=eval_dir / "runs_ood_sfr5b",
        ext_runs=eval_dir / "runs_external_sfr5b",
        profiles=Path("data/exports/profiles_sfr5b.jsonl"),
        db=Path("data/sfr5b.db"),
        index_root=Path("data/indexes_sfr5b"),
    )

    queries = {
        "golden": load_queries(query_set_path("golden")),
        "external": load_queries(query_set_path("external")),
        "ood": load_queries(args.ood_queries or query_set_path("ood")),
    }
    as_judged = load_judgments()
    variants = {
        "as_judged": three_points(
            base=base,
            cap=cap,
            full=full,
            judgments=as_judged,
            stale=stale_by_point(as_judged, base, (cap, full)),
            **queries,
        )
    }
    diff: list[dict[str, Any]] = []
    if args.rejudged.exists():
        rejudged = load_rejudged(args.rejudged)
        diff = rejudge_diff(as_judged, rejudged)
        overlaid = overlay_judgments(as_judged, rejudged)
        variants["with_rejudged"] = three_points(
            base=base,
            cap=cap,
            full=full,
            judgments=overlaid,
            stale=stale_by_point(overlaid, base, (cap, full)),
            **queries,
        )
    else:
        print(
            f"ВНИМАНИЕ: {args.rejudged} не найден — считается только вариант "
            "«по judgments.jsonl как есть»",
            file=sys.stderr,
        )

    payload = {
        "variants": variants,
        "rejudge": {
            "path": str(args.rejudged),
            "pairs": 0 if not args.rejudged.exists() else len(load_rejudged(args.rejudged)),
            "disagreements": diff,
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    titles = {
        "as_judged": "Три точки по `judgments.jsonl` как есть",
        "with_rejudged": "Три точки с подстановкой пересуженных решающих пар",
    }
    for key, variant in variants.items():
        print(render_three_points(variant, title=titles[key]))
        print()
    print("**Пересуд решающих пар.**", render_rejudge_table(diff), sep=" ")
    print(f"\nполные данные → {args.out}")


if __name__ == "__main__":
    main()
