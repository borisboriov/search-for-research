"""One finite offline replay of three sealed live Sol replies; no inference or HTTP."""

import argparse
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from enrichment_experiment import now, private_root, read, sha
from enrichment_fragments import (
    CASES,
    CODE,
    PARTIAL_POLICY,
    check_dates,
    process_partial,
    seal_check,
)
from enrichment_glm_tools import SourceHost
from enrichment_native import normalized_provenance, schema
from enrichment_semantics import validate
from enrichment_verification import immutable_bytes, immutable_json
from enrichment_verifier_benchmark import check_schema

INDEX = "transfer-SHA-index-453a94e.json"
SEAL = "83629e8ed2eb537fead733abbce434e953beb9f2e82eedd5f3fc0635e6e0b814"
REPO = Path(__file__).resolve().parent.parent


def replay(args: argparse.Namespace) -> dict[str, Any]:
    args.root, args.previous = args.root.resolve(), args.previous.resolve()
    if args.root.exists():
        raise ValueError("New offline root required; no repeats or overwrite")
    deadline = datetime.fromisoformat(args.deadline).timestamp()
    if not 0 < deadline - time.time() <= 2 * 3600:
        raise ValueError("Offline deadline must be within two hours")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO, text=True).strip():
        raise ValueError("Clean committed code required")
    if sha(args.previous / INDEX) != SEAL:
        raise ValueError("Not the authorized sealed live3 input")
    old_seal = seal_check(args.previous, INDEX)
    if not (args.previous / "stopped.json").exists():
        raise ValueError("Previous work must be stopped")
    sample = {p["id"]: p for p in read(args.previous / "sample.json")}
    snapshots: dict[str, str] = {}
    inputs = {}
    for case in CASES:
        aid = case["author_id"]
        info = read(args.previous / "prepared" / f"{aid}.json")
        path = Path(info["input_path"])
        if sha(path) != info["sha256"]:
            raise ValueError("Old semantic input changed")
        corpus_path = args.previous / "corpora" / f"{aid}.json"
        corpus = read(corpus_path)
        if SourceHost(args.previous, sample[aid], "live").full_corpus() != corpus:
            raise ValueError("Saved source bytes/corpus changed")
        files = {"semantic-input.json": path, "corpus.json": corpus_path}
        directory = args.previous / "verification" / aid
        files.update({name: directory / name for name in ("task.json", "schema.json")})
        files.update(
            {name: directory / "native" / name for name in ("raw-result.json", "receipt.json")}
        )
        for name in ("verdict.json", "failure.json"):
            if (directory / name).exists():
                files["old-" + name] = directory / name
        inputs[aid] = files
        for name, file in files.items():
            relative = str(file.relative_to(args.previous))
            if read(args.previous / INDEX)["private_file_sha256"].get(relative) != sha(file):
                raise ValueError("Input absent from authorized index")
            snapshots[f"inputs/{aid}/{name}"] = sha(file)
    root = private_root(args.root)
    immutable_bytes(root / "scope.md", args.scope.read_bytes())
    for aid, files in inputs.items():
        for name, file in files.items():
            immutable_bytes(root / "inputs" / aid / name, file.read_bytes())
    code = (
        *CODE,
        "scripts/enrichment_glm_tools.py",
        "scripts/enrichment_live_partial.py",
        "scripts/test_enrichment_glm_runner.py",
    )
    for name in code:
        immutable_bytes(root / "code-snapshots" / name, (REPO / name).read_bytes())
    manifest = {
        "processing_policy": PARTIAL_POLICY,
        "created_at": now(),
        "deadline": args.deadline,
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        "scope_url": args.scope_url,
        "scope_sha256": sha(root / "scope.md"),
        "old_seal": old_seal,
        "cases": CASES,
        "input_sha256": snapshots,
        "code_sha256": {name: sha(REPO / name) for name in code},
        "new_model_jobs": 0,
        "new_source_calls": 0,
        "new_search_calls": 0,
        "cumulative_before": 41,
        "cumulative_after": 41,
        "human_gold": 0,
        "new_profile_inference_usage": 0,
        "development_usage": None,
        "money_or_debit": None,
        "old_usage_preserved_as_historical_receipts": True,
        "retries": 0,
    }
    immutable_json(root / "manifest.json", manifest)
    immutable_bytes(root / "manifest.sha256", (sha(root / "manifest.json") + "\n").encode())
    comparisons = []
    try:
        for case in CASES:
            if time.time() >= deadline:
                raise ValueError("Offline deadline reached")
            aid = case["author_id"]
            folder = root / "inputs" / aid
            source, corpus, task, raw, receipt = [
                read(folder / name)
                for name in (
                    "semantic-input.json",
                    "corpus.json",
                    "task.json",
                    "raw-result.json",
                    "receipt.json",
                )
            ]
            result = raw | {
                "provenance": normalized_provenance(receipt, "verify_glm_live_candidates")
            }
            old_classifications: dict[str, Any] = {}
            old_error = None
            try:
                check_schema(raw, schema("verify", strict_levels=True))
                if any(
                    raw[k] != task[k]
                    for k in ("author_id", "input_sha256", "batch_input_sha256", "batch_ticket_id")
                ):
                    raise ValueError("Verifier output belongs to another task")
                old_classifications = validate(source, result, sha(folder / "semantic-input.json"))
                check_dates(corpus, result)
            except (ValueError, KeyError) as error:
                old_error = str(error)
            old_file = folder / ("old-verdict.json" if old_error is None else "old-failure.json")
            old_record = read(old_file)
            if old_error is None:
                if (
                    old_record["result"] != result
                    or old_record["classifications"] != old_classifications
                ):
                    raise ValueError("Old accepted core differs from exact replay")
            elif old_record["reason"] != old_error:
                raise ValueError("Old rejection reason differs from exact replay")
            processing = process_partial(
                source,
                corpus,
                task,
                raw,
                receipt,
                sha(folder / "semantic-input.json"),
                sha(folder / "raw-result.json"),
            )
            immutable_json(root / "processing" / f"{aid}.json", processing)
            comparisons.append(
                {
                    "author_id": aid,
                    "old_status": "rejected"
                    if old_error
                    else "identity_only"
                    if not source["items"]
                    else "accepted",
                    "old_reason": old_error,
                    "old_validated_atoms": 0 if old_error else len(source["items"]),
                    "old_usable_atoms": 0
                    if old_error
                    else sum(c["usable_coverage"] for c in old_classifications.values()),
                    "new_status": processing["packet_status"],
                    "new_counts": processing["counts"],
                    "new_fully_accepted_nonempty": processing["fully_accepted_nonempty"],
                    "raw_sha256": sha(folder / "raw-result.json"),
                    "raw_modified": False,
                    "old_accepted_classifications_preserved": old_error is None
                    and all(
                        r["effective_classification"] == old_classifications[r["item_id"]]
                        for r in processing["items"]
                    ),
                    "rejected_atoms": [
                        {"item_id": r["item_id"], "field": r["field"], "reason": r["reason"]}
                        for r in processing["items"]
                        if r["validation_status"] != "valid"
                    ],
                }
            )
        metrics = {
            "processing_policy": PARTIAL_POLICY,
            "manifest_sha256": sha(root / "manifest.json"),
            "new_model_jobs": 0,
            "new_source_calls": 0,
            "new_search_calls": 0,
            "cumulative_jobs": 41,
            "human_gold": 0,
            "cases": comparisons,
            "original_live_yield_unchanged": "2/3 schema+semantic+date-valid Sol packets",
            "partial_is_not_full_success": True,
            "economy_or_nonregression_claim": False,
        }
        immutable_json(root / "metrics.json", metrics)
        return metrics
    finally:
        immutable_json(
            root / "stopped.json",
            {
                "at": now(),
                "new_model_jobs": "forbidden",
                "new_source_calls": "forbidden",
                "reason": "finite_offline_replay_terminal",
            },
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("root", "previous", "scope"):
        parser.add_argument("--" + option, type=Path, required=True)
    for option in ("deadline", "scope-url"):
        parser.add_argument("--" + option, required=True)
    print(replay(parser.parse_args()))


if __name__ == "__main__":
    main()
