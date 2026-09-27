"""Расхождения судейских прогонов на решающих парах SFR-5c — по классам.

Зачем. В SFR-5c решающие пары пересуживались дважды одним и тем же судьёй
(модель Fable, субагент ``sfr-judge``) по одному и тому же слепому пулу:

* **v1** — ``judgments_rejudge_sfr5c.jsonl``: рубрика тогда содержала
  дополнительное правило «сомневаешься между 1 и 2 — ставь 1», которого нет ни
  в рубрике SFR-1, ни в прошлых итерациях (находка ревью SFR-5c);
* **v2** — ``judgments_rejudge_sfr5c_v2.jsonl``: то же самое без этого правила
  (рубрика вынесена в ``packages/sfr-match/eval/JUDGE_RUBRIC.md``).

Три сравнения — ``judgments.jsonl`` ↔ v1, ↔ v2 и **v1 ↔ v2** — разделяют то, что
в отчёте до ревью было слито в одну цифру «37,8 % расхождений»:

* orig ↔ v1 и orig ↔ v2 — расхождение прогонов судьи с накопленной разметкой;
* v1 ↔ v2 — **верхняя граница** эффекта отмены правила: в ней сидит и правило,
  и обычный разброс двух прогонов одной модели по одному пулу. Разделить эти
  два вклада одним прогоном нельзя, и выдавать разницу за «эффект правила»
  нечестно — поэтому граница верхняя.

Классы («строже» = оценка упала): ``2→1``, ``2→0``, ``1→0``; «мягче»: ``1→2``,
``0→1``, ``0→2``. Пары без прежней оценки считаются отдельно (``нет→N``):
неоценённая пара в метриках равна 0, но это не суждение судьи.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sfr_match.evalset import Judgment, load_judgments

Key = tuple[str, str]
MISSING = "нет"


def classify(before: int | None, after: int) -> str:
    """Класс перехода одной пары: ``«2→1»``, ``«нет→0»``, ``«=»`` при совпадении."""
    if before is None:
        return f"{MISSING}→{after}"
    if before == after:
        return "="
    return f"{before}→{after}"


def is_stricter(label: str) -> bool:
    """Строже — оценка упала; ``нет→N`` и ``=`` не строже и не мягче."""
    before, _, after = label.partition("→")
    if not after or before == MISSING:
        return False
    return int(before) > int(after)


def is_softer(label: str) -> bool:
    before, _, after = label.partition("→")
    if not after or before == MISSING:
        return False
    return int(before) < int(after)


def compare(
    before: Mapping[Key, Judgment],
    after: Mapping[Key, Judgment],
    *,
    keys: list[Key] | None = None,
) -> dict[str, Any]:
    """Сравнить две разметки на общих парах: классы, доли, разбивка по запросам.

    ``keys`` — пары, по которым считать (по умолчанию все пары ``after``): так
    сравнение v1 ↔ v2 идёт по тому же множеству, что orig ↔ v1, и доли
    сопоставимы между тремя таблицами.
    """
    pairs = list(after) if keys is None else list(keys)
    classes: Counter[str] = Counter()
    per_query: dict[str, Counter[str]] = {}
    for key in pairs:
        new = after.get(key)
        if new is None:
            continue
        old = before.get(key)
        label = classify(None if old is None else old.grade, new.grade)
        classes[label] += 1
        if label != "=":
            per_query.setdefault(key[0], Counter())[label] += 1
    judged = sum(count for label, count in classes.items() if not label.startswith(MISSING))
    # Пара без прежней оценки — не расхождение судей: судить было не с чем.
    disagreements = sum(
        count for label, count in classes.items() if label != "=" and not label.startswith(MISSING)
    )
    return {
        "pairs": len(pairs),
        "judged_in_both": judged,
        "disagreements": disagreements,
        "share": round(disagreements / judged, 4) if judged else 0.0,
        "stricter": sum(c for label, c in classes.items() if is_stricter(label)),
        "softer": sum(c for label, c in classes.items() if is_softer(label)),
        "classes": dict(sorted(classes.items())),
        "per_query": {
            qid: dict(sorted(counter.items())) for qid, counter in sorted(per_query.items())
        },
    }


def render(title: str, payload: dict[str, Any]) -> str:
    """Одна строка таблицы сравнения — для §6 отчёта."""
    classes = payload["classes"]
    cells = " · ".join(f"{label} ×{count}" for label, count in classes.items() if label != "=")
    return (
        f"| {title} | {payload['judged_in_both']} | **{payload['disagreements']}** "
        f"({payload['share']:.1%}) | {payload['stricter']} | {payload['softer']} | {cells or '—'} |"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    eval_dir = Path("packages/sfr-match/eval")
    parser.add_argument("--v1", type=Path, default=eval_dir / "judgments_rejudge_sfr5c.jsonl")
    parser.add_argument("--v2", type=Path, default=eval_dir / "judgments_rejudge_sfr5c_v2.jsonl")
    parser.add_argument("--out", type=Path, default=Path("docs/sfr5c_rejudge_classes.json"))
    # Подписи строк таблицы: скрипт сравнивает любые два прогона (#122 — два
    # слепых пересуда топ-5 на разных индексах), а не только v1/v2 решающих пар.
    parser.add_argument("--v1-label", default="пересуд v1 (с tie-break)")
    parser.add_argument("--v2-label", default="пересуд v2 (без tie-break)")
    args = parser.parse_args()

    original = load_judgments()
    v1 = load_judgments(args.v1)
    v2 = load_judgments(args.v2)
    keys = sorted(set(v1) | set(v2))
    payload = {
        "pool": {"pairs": len(keys), "v1": str(args.v1), "v2": str(args.v2)},
        "orig_vs_v1": compare(original, v1, keys=keys),
        "orig_vs_v2": compare(original, v2, keys=keys),
        "v1_vs_v2": compare(v1, v2, keys=keys),
        "grade_distribution": {
            "original": dict(
                sorted(Counter(original[k].grade for k in keys if k in original).items())
            ),
            "v1": dict(sorted(Counter(j.grade for j in v1.values()).items())),
            "v2": dict(sorted(Counter(j.grade for j in v2.values()).items())),
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("| Сравнение | пар с оценками в обоих | расхождений | строже | мягче | классы |")
    print("|---|---|---|---|---|---|")
    print(render(f"`judgments.jsonl` ↔ {args.v1_label}", payload["orig_vs_v1"]))
    print(render(f"`judgments.jsonl` ↔ {args.v2_label}", payload["orig_vs_v2"]))
    print(render(f"{args.v1_label} ↔ {args.v2_label}", payload["v1_vs_v2"]))
    print(f"\nполные данные → {args.out}")


if __name__ == "__main__":
    main()
