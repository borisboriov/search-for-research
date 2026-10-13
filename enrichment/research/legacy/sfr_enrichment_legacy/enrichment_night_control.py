"""Два новых ограниченных контроля compact после заранее заданного успешного сравнения."""

import argparse
import json
import random
import sqlite3
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sfr_enrichment.semantics import prepare_control, validate
from sfr_enrichment_legacy.enrichment_batch import Batch, encoded, immutable
from sfr_enrichment_legacy.enrichment_experiment import (
    now,
    private_root,
    read,
    sha,
    verified_sample,
)
from sfr_enrichment_legacy.enrichment_gpt_compact import COMPACT, PLAN, allow_new, saved_raw
from sfr_enrichment_legacy.enrichment_gpt_compact import metrics as comparison_metrics
from sfr_enrichment_legacy.enrichment_native import execute, normalized_provenance, schema
from sfr_enrichment_legacy.enrichment_night import (
    DB,
    HARD_STOP,
    INDEX,
    METHOD,
    PARENT,
    REPO,
    RULES,
    bind,
    checked_result,
    collect,
    locked,
    preflight,
    require_access,
)
from sfr_enrichment_legacy.enrichment_pi_pilot import HIGH_CONFIGS, RUBRIC, select_profiles
from sfr_enrichment_legacy.enrichment_verifier_benchmark import (
    AXES,
    JUDGE_CONFIG,
    JUDGE_RULES,
    check_schema,
    judge_schema,
)

CONTROL_METHOD = "fresh-compact-control-v1"
CONTROL_PLAN = REPO / "enrichment/research/methods/enrichment_fresh_compact_control_v1.md"
SEED = 19319420261015


def successful_comparison(path: Path) -> dict[str, Any]:
    if (path / "stopped.json").exists():
        raise ValueError("Сравнение остановлено")
    value = comparison_metrics(path)
    if not value["eligible_for_fresh_control"]:
        raise ValueError("Заранее заданный критерий compact не выполнен")
    return value


def single_schema() -> dict[str, Any]:
    contract = judge_schema()
    for kind in ("atom_evaluations", "profile_evaluations"):
        contract["properties"][kind]["items"]["properties"]["response"]["enum"] = ["A"]
    return contract


def validate_single(packet: dict[str, Any], value: dict[str, Any], digest: str) -> None:
    check_schema(value, single_schema())
    if value["input_sha256"] != digest:
        raise ValueError("Judge другого входа")
    profiles = {row["author_id"]: row for row in packet["profiles"]}
    for kind, suffix, expected in (
        (
            "atom_evaluations",
            "item_id",
            {(aid, "A", item["item_id"]) for aid, row in profiles.items() for item in row["items"]},
        ),
        ("profile_evaluations", "axis", {(aid, "A", axis) for aid in profiles for axis in AXES}),
    ):
        actual = [(row["author_id"], row["response"], row[suffix]) for row in value[kind]]
        if len(actual) != len(set(actual)) or set(actual) != expected:
            raise ValueError("Judge обязан оценить единственный ответ полностью")
        for row in value[kind]:
            if not row["basis"].strip() or any(
                ref not in profiles[row["author_id"]]["evidence_pool"]
                for ref in row["evidence_refs"]
            ):
                raise ValueError("Judge basis/refs не подтверждены")
            if row["grade"] == "correct" and (row["error_types"] or row["severity"] != "none"):
                raise ValueError("Correct не имеет ошибок")
            if row["grade"] != "correct" and (not row["error_types"] or row["severity"] == "none"):
                raise ValueError("Ошибка требует типа и серьёзности")


def freeze(root: Path, comparison: Path) -> None:
    successful_comparison(comparison)
    root = private_root(root)
    if list(root.iterdir()):
        raise ValueError("Нужен пустой root")
    index_manifest = read(PARENT / "enrichment100-20261008/manifest.json")
    hashes = {name: sha(INDEX / name) for name in index_manifest["index_hashes"]}
    docs = read(INDEX / "docs.json")
    if hashes != index_manifest["index_hashes"] or len(docs) != 9002:
        raise ValueError("Каталог изменён")
    exclusions = {
        str(path): sha(path) for path in sorted(PARENT.glob("*/sample.json")) if path.parent != root
    }
    excluded = {row["id"] for name in exclusions for row in read(Path(name))}
    selected = random.Random(SEED).sample(select_profiles(docs, excluded, SEED), 2)
    db_sha = sha(DB)
    with sqlite3.connect(DB.resolve().as_uri() + "?mode=ro", uri=True) as connection:
        rows = connection.execute(
            "SELECT a.openalex_id,a.orcid,a.display_name,a.h_index,i.openalex_id,"
            "COALESCE(i.name_ru,i.name_en),a.merged_into_id,a.suspect_merge "
            "FROM authors a JOIN institutions i ON i.id=a.last_known_institution_id"
        ).fetchall()
    catalogue = {row[0].rsplit("/", 1)[-1]: row for row in rows}
    for profile in selected:
        row = catalogue[profile["id"]]
        if (row[2], row[3], row[5], row[6]) != (
            profile["name"],
            profile["h_index"],
            profile["institution"],
            None,
        ):
            raise ValueError("Профиль БД отличается от индекса")
        profile.update(
            institution_id=row[4].rsplit("/", 1)[-1],
            orcid=row[1],
            suspect_merge=bool(row[7]),
            cohort=CONTROL_METHOD,
        )
    if sha(DB) != db_sha:
        raise ValueError("БД изменилась")
    immutable(root / "sample.json", encoded(selected))
    instruction = (
        JUDGE_RULES.replace("судья A/B", "судья одного ответа")
        .replace("Оцени ОБА ответа отдельно", "Оцени единственный ответ A отдельно")
        .replace("оба могут быть", "ответ может быть")
        + RUBRIC.read_text()
    )
    for name, data in {
        "selected-instruction.txt": COMPACT.read_bytes(),
        "judge-instruction.txt": instruction.encode(),
        "judge-schema.json": encoded(single_schema()),
    }.items():
        immutable(root / name, data)
    files = [
        Path(__file__),
        CONTROL_PLAN,
        PLAN,
        COMPACT,
        RULES,
        RUBRIC,
        *[
            REPO / "scripts" / name
            for name in (
                "enrichment_night.py",
                "enrichment_pi_cli_extension.mjs",
                "enrichment_pi_runner.mjs",
                "enrichment_pi_pilot.py",
                "enrichment_native.py",
                "enrichment_semantics.py",
                "enrichment_verifier_benchmark.py",
                "enrichment_batch.py",
                "enrichment_gpt_compact.py",
            )
        ],
    ]
    immutable(
        root / "manifest.json",
        encoded(
            {
                "method": METHOD,
                "experiment_kind": CONTROL_METHOD,
                "created_at": now(),
                "seed": SEED,
                "sample_sha256": sha(root / "sample.json"),
                "index_hashes": hashes,
                "db_sha256": db_sha,
                "exclusions": exclusions,
                "excluded_count": len(excluded),
                "human_reviewed": 0,
                "comparison_root": str(comparison),
                "comparison_manifest_sha256": sha(comparison / "manifest.json"),
                "comparison_metrics_sha256": sha(comparison / "metrics.json"),
                "rules_hashes": {str(path.relative_to(REPO)): sha(path) for path in files},
                "artifact_hashes": {
                    name: sha(root / name)
                    for name in (
                        "selected-instruction.txt",
                        "judge-instruction.txt",
                        "judge-schema.json",
                    )
                },
                "limits": {
                    "profiles": 2,
                    "collector_jobs": 2,
                    "verifier_jobs": 2,
                    "judge_jobs": 1,
                    "timeout_seconds": 600,
                    "concurrency": 1,
                    "search": 4,
                    "resources_including_robots": 8,
                    "automatic_retries": 0,
                },
            }
        ),
    )
    for index, profile in enumerate(selected, 1):
        Batch.create(root / "batches" / f"{index:02d}", root, [profile["id"]], RULES, concurrency=1)


def control_locked(root: Path) -> dict[str, Any]:
    value = locked(root)
    if value["experiment_kind"] != CONTROL_METHOD or len(verified_sample(root)) != 2:
        raise ValueError("Другой контроль")
    for name, digest in value["artifact_hashes"].items():
        if sha(root / name) != digest:
            raise ValueError("Control артефакт изменён")
    comparison = Path(value["comparison_root"])
    if (
        sha(comparison / "manifest.json") != value["comparison_manifest_sha256"]
        or sha(comparison / "metrics.json") != value["comparison_metrics_sha256"]
    ):
        raise ValueError("Сравнение изменилось")
    successful_comparison(comparison)
    return value


def run_profile(root: Path, index: int, profile: dict[str, Any]) -> None:
    require_access(root)
    aid = profile["id"]
    batch = Batch(root / "batches" / f"{index:02d}")
    raw_path, receipt = collect(root, profile, batch)
    if not read(raw_path.parent / "completion-status.json")["model_completed"]:
        raise ValueError("Сборщик не завершён: partial сохранён, зависимые jobs остановлены")
    value, pool, rejected = bind(root, aid, read(raw_path))
    immutable(root / "rejections" / f"{aid}.json", encoded(rejected))
    value["provenance"] = receipt | {"stage": "collect"}
    value["network_operations"] = []
    with batch.locked() as log:
        value["network_operations"] = [
            row["operation_id"]
            for row in log
            if row["action"] == "reserved" and row["ticket_id"] == aid + "-collect"
        ]
    collector_path = root / "normalized" / aid / "collector.json"
    immutable(collector_path, encoded(value))
    batch.submit(aid + "-collect", collector_path, value["provenance"])
    source_path = prepare_control(
        root,
        profile,
        collector_path,
        pool,
        RUBRIC,
        sha(root / "sample.json"),
        namespace=CONTROL_METHOD,
        source_kind="fresh_pi_cli_collection",
    )
    source = read(source_path)
    ticket = batch.ticket(aid, "verify")
    task = {
        "author_id": aid,
        "batch_ticket_id": aid + "-verify",
        "batch_input_sha256": sha(ticket),
        "input_sha256": sha(source_path),
        "semantic_input": source,
    }
    instruction = (root / "selected-instruction.txt").read_text()
    workspace = root / "native-workspace"
    workspace.mkdir(exist_ok=True, mode=0o700)
    output_schema = schema("verify", strict_levels=True)
    prompt = json.dumps(
        {"task": task},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    allow_new(root)
    require_access(root)
    if datetime.now(UTC) >= HARD_STOP:
        raise ValueError("Дедлайн процесса: native job не запущен")
    result_path, native_receipt = execute(
        root / "runs" / aid / "native_verifier",
        prompt,
        output_schema,
        workspace,
        model="gpt-6.1-sol",
        effort="high",
        timeout_seconds=600,
        deadline_epoch=HARD_STOP.timestamp() - 5,
        skip_git_repo_check=True,
        disable_mcp=True,
        required_config=HIGH_CONFIGS["native_verifier"],
        system_prompt=instruction,
    )
    result = read(result_path)
    check_schema(result, output_schema)
    if any(
        result[key] != task[key]
        for key in ("author_id", "batch_ticket_id", "batch_input_sha256", "input_sha256")
    ):
        raise ValueError("Ответ проверяющего другого задания")
    result["provenance"] = normalized_provenance(native_receipt, "verify")
    derived = validate(source, result, task["input_sha256"])
    result["network_operations"] = []
    normalized = root / "normalized" / aid / "verifier.json"
    immutable(normalized, encoded(result))
    batch.submit(aid + "-verify", normalized, result["provenance"])
    completed_path = root / "results" / f"{aid}.json"
    immutable(
        completed_path,
        encoded(
            {
                "author_id": aid,
                "result": result,
                "classifications": derived,
                "input_path": str(source_path),
                "input_sha256": task["input_sha256"],
                "collector_receipt": receipt,
                "verifier_receipt": native_receipt,
                "rejected_candidates": len(rejected),
                "human_reviewed": 0,
            }
        ),
    )
    immutable(completed_path.with_suffix(".sha256"), (sha(completed_path) + "\n").encode())


def control_result(root: Path, aid: str) -> dict[str, Any]:
    wrapper = checked_result(root, aid)
    directory = root / "runs" / aid / "native_verifier"
    receipt = read(directory / "receipt.json")
    if receipt != wrapper["verifier_receipt"]:
        raise ValueError("Control receipt изменён")
    for file, key in (
        ("raw-result.json", "raw_result_sha256"),
        ("events.jsonl", "events_sha256"),
        ("prompt.txt", "prompt_sha256"),
    ):
        if sha(directory / file) != receipt[key]:
            raise ValueError("Control native raw изменён")
    expected = read(directory / "raw-result.json")
    expected["provenance"] = normalized_provenance(receipt, "verify")
    expected["network_operations"] = []
    if wrapper["result"] != expected:
        raise ValueError("Control result не соответствует raw")
    return wrapper


def run(root: Path) -> None:
    control_locked(root)
    proof = read(root / "preflight.json")
    if (
        proof["manifest_sha256"] != sha(root / "manifest.json")
        or sha(Path(proof["proof"])) != proof["proof_sha256"]
    ):
        raise ValueError("Control preflight изменён")
    for index, profile in enumerate(verified_sample(root), 1):
        if (root / "results" / f"{profile['id']}.json").exists():
            control_result(root, profile["id"])
            continue
        allow_new(root)
        try:
            run_profile(root, index, profile)
            print(json.dumps({"author_id": profile["id"], "completed": True}), flush=True)
        except Exception as exc:
            immutable(
                root / "stopped.json",
                encoded(
                    {
                        "at": now(),
                        "author_id": profile["id"],
                        "reason": type(exc).__name__ + ": " + str(exc),
                    }
                ),
            )
            raise


def packet(root: Path) -> Path:
    control_locked(root)
    rows = []
    for profile in verified_sample(root):
        wrapper = control_result(root, profile["id"])
        source = read(Path(wrapper["input_path"]))
        row = {
            key: source[key]
            for key in ("author_id", "profile", "items", "evidence_pool", "profile_evidence")
        }
        row["responses"] = {
            "A": {
                key: wrapper["result"][key] for key in ("items", "profile_assessments", "summary")
            }
        }
        rows.append(row)
    path = root / "judge-inputs" / "fresh-control.json"
    immutable(path, encoded({"packet_id": "fresh-control", "profiles": rows}))
    return path


def judge(root: Path) -> dict[str, Any]:
    control_locked(root)
    path = packet(root)
    directory = root / "judges" / path.stem
    if (directory / "validated.json").exists():
        saved, _receipt = saved_raw(directory)
        if saved["result"] != read(directory / "raw-result.json"):
            raise ValueError("Control judge result изменён")
        validate_single(read(path), saved["result"], sha(path))
    else:
        allow_new(root)
        require_access(root)
        if directory.exists():
            raise ValueError("Повтор control judge запрещён")
        try:
            raw, receipt = execute(
                directory,
                json.dumps(
                    {"input_sha256": sha(path), "packet": read(path)},
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                read(root / "judge-schema.json"),
                root / "native-workspace",
                model="gpt-6-astra",
                effort="xhigh",
                timeout_seconds=600,
                deadline_epoch=HARD_STOP.timestamp() - 5,
                skip_git_repo_check=True,
                disable_mcp=True,
                required_config=JUDGE_CONFIG,
                system_prompt=(root / "judge-instruction.txt").read_text(),
            )
            result = read(raw)
            validate_single(read(path), result, sha(path))
            saved = {"result": result, "receipt": receipt, "human_reviewed": 0}
            immutable(directory / "validated.json", encoded(saved))
        except Exception as exc:
            immutable(
                root / "stopped.json",
                encoded(
                    {"at": now(), "stage": "judge", "reason": type(exc).__name__ + ": " + str(exc)}
                ),
            )
            raise
    quality = Counter(
        row["grade"]
        for kind in ("atom_evaluations", "profile_evaluations")
        for row in saved["result"][kind]
    )
    high = sum(
        row["severity"] in ("high", "critical")
        for kind in ("atom_evaluations", "profile_evaluations")
        for row in saved["result"][kind]
    )
    value = {
        "method": CONTROL_METHOD,
        "profiles": 2,
        "quality": dict(quality),
        "high_critical": high,
        "human_reviewed": 0,
        "judge_receipt": saved["receipt"],
        "human_truth_or_scale_permission": False,
    }
    immutable(root / "control-quality.json", encoded(value))
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("freeze", "preflight", "run", "judge"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--comparison-root", type=Path)
    args = parser.parse_args()
    if args.command == "freeze":
        if args.comparison_root is None:
            raise ValueError("Нужно успешное сравнение")
        freeze(args.root, args.comparison_root)
    elif args.command == "preflight":
        control_locked(args.root)
        preflight(args.root)
    elif args.command == "run":
        run(args.root)
    else:
        print(json.dumps(judge(args.root), ensure_ascii=False))


if __name__ == "__main__":
    main()
