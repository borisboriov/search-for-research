"""Фиксация метода перед evaluation; результаты и контакты остаются вне git."""

import argparse
import random
from pathlib import Path
from typing import Any

from enrichment_experiment import now, private_root, read, sha, verified_sample, write_new
from enrichment_verification import identifier, validate_result

RULE_FILES = (
    "scripts/enrichment_experiment.py",
    "scripts/enrichment_verification.py",
    "scripts/enrichment_protocol.py",
    ".codex/agents/sfr-enrichment-verifier.toml",
    "docs/experiments/enrichment_verifier_v2.md",
)


def freeze_method(root: Path, version: str, run_id: str, checkout: Path) -> Path:
    root = private_root(root)
    version = identifier(version)
    run_id = identifier(run_id)
    sample = verified_sample(root)
    pilot = [row["id"] for row in sample if row["cohort"] == "pilot"]
    artifacts = {}
    for author_id in pilot:
        for stage in ("inputs", f"outputs/{run_id}"):
            path = root / "verification" / version / stage / f"{author_id}.json"
            value = read(path)
            if stage.startswith("outputs"):
                input_path = root / "verification" / version / "inputs" / f"{author_id}.json"
                validate_result(input_path, value["result"])
                if value.get("input_sha256") != sha(input_path):
                    raise ValueError("Результат не связан с входом")
                if any(
                    item["status"] == "not_checked"
                    for item in value["result"]["field_search"].values()
                ):
                    raise ValueError("Не завершён ограниченный поиск первой десятки")
            artifacts[str(path.relative_to(root))] = sha(path)
    evaluation = sorted(row["id"] for row in sample if row["cohort"] == "evaluation")
    random_ids = random.Random(19319420261009).sample(evaluation, 5)
    value = {
        "version": version,
        "run_id": run_id,
        "locked_at": now(),
        "criteria_accepted": True,
        "criteria_source": "Boris/product-thread/01a11cb7-9131-7733-8047-4810c3020663/2026-10-09",
        "sample_sha256": sha(root / "sample.json"),
        "pilot_artifacts": artifacts,
        "rule_files": {name: sha(checkout / name) for name in RULE_FILES},
        "human_review_pending": True,
        "human_sampling": {
            "random_seed": 19319420261009,
            "random_ids": random_ids,
            "random_denominator": 5,
            "targeted_policy": (
                "First 3 by author_id with identity/affiliation disagreement or disputed claims; "
                "then first 3 without confirmed positives, excluding random and selected IDs. "
                "Do not replace missing strata."
            ),
            "targeted_maximum": 6,
            "statistics": "random and targeted reported separately; actual human decisions only",
        },
        "collector": (
            "ORCID cache → official person/unit/theses → linked coordinator if no personal contact "
            "→ announcements; atomic claims with evidence, no inferred recruitment"
        ),
        "verifier": (
            "independent native context; each positive claim and bounded omission search; "
            "file transport replaceable by API adapter"
        ),
        "per_stage_budget": {"search_queries": 4, "pages": 8},
    }
    path = root / "verification" / version / "method-lock.json"
    write_new(path, value)
    return path


def validate_lock(root: Path, path: Path, checkout: Path) -> dict[str, Any]:
    lock = read(path)
    identifier(lock["version"])
    identifier(lock["run_id"])
    verified_sample(root)
    if not lock.get("criteria_accepted") or lock.get("sample_sha256") != sha(root / "sample.json"):
        raise ValueError("Нужны принятые критерии и неизменная выборка")
    if set(lock.get("rule_files", {})) != set(RULE_FILES):
        raise ValueError("Неполная фиксация метода")
    for name, digest in lock["rule_files"].items():
        if sha(checkout / name) != digest:
            raise ValueError("Метод изменён после фиксации: требуется новая версия")
    pilot = {row["id"] for row in verified_sample(root) if row["cohort"] == "pilot"}
    expected = {
        f"verification/{lock['version']}/{stage}/{author_id}.json"
        for author_id in pilot
        for stage in ("inputs", f"outputs/{lock['run_id']}")
    }
    if set(lock.get("pilot_artifacts", {})) != expected:
        raise ValueError("Не зафиксирована полная первая десятка")
    for name, digest in lock["pilot_artifacts"].items():
        if sha(root / name) != digest:
            raise ValueError("Изменено доказательство пилота")
    return dict(lock)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--checkout", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(freeze_method(args.root, args.version, args.run_id, args.checkout))


if __name__ == "__main__":
    main()
