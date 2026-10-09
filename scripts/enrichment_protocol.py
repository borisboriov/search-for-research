"""Фиксация метода перед evaluation; результаты и контакты остаются вне git."""

import argparse
import random
from pathlib import Path
from typing import Any

from enrichment_experiment import STATUSES, now, private_root, read, sha, verified_sample, write_new
from enrichment_verification import captured_collector, identifier, validate_result

RULE_FILES = (
    "scripts/enrichment_experiment.py",
    "scripts/enrichment_verification.py",
    "scripts/enrichment_protocol.py",
    ".codex/agents/sfr-enrichment-verifier.toml",
    "docs/experiments/enrichment_verifier_v2.md",
    "docs/experiments/enrichment_method_v2_1.md",
)


def completion_check(input_path: Path, output_path: Path) -> None:
    wrapper = read(output_path)
    source = validate_result(input_path, wrapper["result"])
    captured_collector(input_path.parents[3], source)
    if wrapper.get("input_sha256") != sha(input_path):
        raise ValueError("Результат не связан с входом")
    for stage, fields, journal in (
        ("сборщик", source["collector"].get("field_search", {}), source["collector"]["journal"]),
        ("проверяющий", wrapper["result"]["field_search"], wrapper["result"]["journal"]),
    ):
        if set(fields) != set(source["collector"]["field_status"]):
            raise ValueError(f"Нужны основания поиска всех полей: {stage}")
        if not any(row["kind"] == "page" for row in journal):
            raise ValueError(f"Нет источников: {stage}")
        if stage == "проверяющий" and not any(row["kind"] == "search" for row in journal):
            raise ValueError("Нет самостоятельного поиска проверяющего")
        named_refs = [row["journal_id"] for row in journal if "journal_id" in row]
        if len(named_refs) != len(set(named_refs)) or any(
            not isinstance(ref, str) or not ref for ref in named_refs
        ):
            raise ValueError("Неоднозначные именованные операции журнала")
        for name, field in fields.items():
            if field.get("status") not in STATUSES:
                raise ValueError(f"Неизвестный статус поля: {stage}")
            if stage == "сборщик" and field["status"] != source["collector"]["field_status"][name]:
                raise ValueError("Статусы сборщика противоречат основаниям")
            refs = field.get("journal_refs", [])
            reason = field.get("explanation") or field.get("rationale")
            if (
                field.get("status") == "not_checked"
                or not isinstance(reason, str)
                or not reason.strip()
            ):
                raise ValueError(f"Не завершён разбор полей: {stage}")
            if not refs or any(
                not (
                    (type(ref) is int and 0 <= ref < len(journal))
                    or (isinstance(ref, str) and ref in named_refs)
                )
                for ref in refs
            ):
                raise ValueError(f"Нет связи поля с журналом: {stage}")
    if "not_checked" in source["collector"]["field_status"].values():
        raise ValueError("Не завершён сборщик")
    if not source["collector"]["sources"]:
        raise ValueError("Нет материалов сборщика")


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
            read(path)
            if stage.startswith("outputs"):
                input_path = root / "verification" / version / "inputs" / f"{author_id}.json"
                completion_check(input_path, path)
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
    for author_id in pilot:
        directory = root / "verification" / lock["version"]
        completion_check(
            directory / "inputs" / f"{author_id}.json",
            directory / "outputs" / lock["run_id"] / f"{author_id}.json",
        )
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
