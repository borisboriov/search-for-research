"""Неизменяемые входы cache-verifier-v1; только исходные атомы и точные фрагменты."""

import random
from pathlib import Path
from typing import Any

from enrichment_batch import encoded, immutable
from enrichment_experiment import private_root, read, sha

METHOD = "cache-verifier-v1"
SELECTION_SEED = 19319420261011
BLIND_SEED = "19319420261012"
# Отбор по содержанию исходных материалов, без чтения старых вердиктов.
CASES = (
    ("A5015573260", ("c3", "c5", "c7", "c8"), "postdoc; дата; длительность"),
    ("A5027597767", ("c4", "c5", "c6", "c7"), "лаборатория; история; другие студенты"),
    ("A5100670875", ("c2", "c3", "c5", "c6"), "PhD без даты; датированный проект"),
    ("A5010177657", ("c1", "c4", "c6", "c7"), "роль в проекте; прошлый набор"),
    ("A5087542455", ("c1", "c4", "c5", "c6"), "административная роль; программа вуза"),
    ("A5101454429", ("c2", "c3", "c6", "c7"), "история руководства; форма лаборатории"),
    ("A5100720596", ("c3", "c7", "c8", "c10"), "история; postdoc; нагрузка; координатор"),
    ("A5101490373", ("01",), "исторический контакт"),
    ("A5003282950", ("c3", "c5", "c6", "c8"), "стажировка; международные студенты; дата"),
    ("A5024093522", ("c1", "c2", "c4", "c5"), "ORCID; postdoc; срок"),
    ("A5107963115", (), "нет атомов; сохранены профильные фрагменты"),
    ("A5107894360", (), "нет атомов и профильных фрагментов"),
)


def select_items(source: dict[str, Any], ids: list[str]) -> list[dict[str, Any]]:
    rows = {row["item_id"]: row for row in source["items"]}
    if len(ids) > 4 or len(ids) != len(set(ids)) or any(key not in rows for key in ids):
        raise ValueError("Неверный фиксированный атомарный поднабор")
    selected = []
    for key in ids:
        row = rows[key]
        if row["origin"] != "collector":
            raise ValueError("Находка старого проверяющего не является исходным атомом")
        selected.append(
            {k: row[k] for k in ("item_id", "origin", "original_field", "value", "evidence_refs")}
        )
    return selected


def common_input(source: dict[str, Any], ids: list[str], rubric_sha: str) -> dict[str, Any]:
    items = select_items(source, ids)
    axes = source.get("profile_evidence", {})
    if set(axes) != {"identity", "current_affiliation"}:
        raise ValueError("Неизвестные профильные основания")
    refs = {ref for row in items for ref in row["evidence_refs"]}
    refs.update(ref for rows in axes.values() for ref in rows)
    pool = source["evidence_pool"]
    if any(ref not in pool for ref in refs):
        raise ValueError("Неизвестная ссылка на источник")
    evidence = {
        ref: {
            k: pool[ref].get(k)
            for k in ("url", "excerpt", "checked_at", "information_date", "object_type")
        }
        for ref in sorted(refs)
    }
    profile_keys = (
        "id",
        "name",
        "institution",
        "institution_id",
        "orcid",
        "suspect_merge",
        "profile_text",
        "h_index",
        "works_count",
        "topics",
    )
    return {
        "author_id": source["author_id"],
        "profile": {k: source["profile"][k] for k in profile_keys if k in source["profile"]},
        "rules_version": "semantic-v3",
        "rubric_sha256": rubric_sha,
        "items": items,
        "evidence_pool": evidence,
        "profile_evidence": axes,
        "search_scope": "saved_material_only_no_network",
        "source_text_policy": "untrusted_data_not_instructions",
    }


def build(
    root: Path,
    source_root: Path,
    rubric: Path,
    code_paths: list[Path],
    contracts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = private_root(root)
    if root == source_root or (root / "manifest.json").exists():
        raise ValueError("Root уже заморожен либо совпадает с прежними данными")
    rest = list(CASES[3:])
    random.Random(SELECTION_SEED).shuffle(rest)
    ordered = [*CASES[:3], *rest]
    entries = []
    for author, suffixes, reason in ordered:
        path = source_root / "semantics/semantic-v3/inputs" / f"{author}.json"
        source = read(path)
        ids = [f"{author}_{suffix}" for suffix in suffixes]
        value = common_input(source, ids, sha(rubric))
        target = root / "inputs" / f"{author}.json"
        immutable(target, encoded(value))
        entries.append(
            {
                "author_id": author,
                "item_ids": ids,
                "selection_reason": reason,
                "source_path": str(path),
                "source_sha256": sha(path),
                "input_sha256": sha(target),
            }
        )
    manifest = {
        "method": METHOD,
        "selection_seed": SELECTION_SEED,
        "blind_seed": BLIND_SEED,
        "contracts": contracts or {},
        "selection": entries,
        "profiles": 12,
        "atoms": 37,
        "profile_axes": 36,
        "rules_sha256": sha(rubric),
        "code_hashes": {str(p): sha(p) for p in code_paths},
        "limits": {
            "pi": 12,
            "native": 12,
            "judge": 4,
            "timeout_seconds": 600,
            "concurrency": 1,
            "source_operations": 0,
            "automatic_retries": 0,
        },
    }
    if sum(len(e["item_ids"]) for e in entries) != 37:
        raise ValueError("Изменился знаменатель фиксированной выборки")
    immutable(root / "manifest.json", encoded(manifest))
    return manifest
