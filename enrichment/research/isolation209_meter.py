"""Frozen offline audit for #209 continuation; never invokes HTTP or models."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from sfr_enrichment.common import read, sha
from sfr_enrichment.compact import expand_input
from sfr_enrichment.config import RUBRIC
from sfr_enrichment.contacts import check_contact_input
from sfr_enrichment.fragments import check_dates
from sfr_enrichment.runner import check_result, code_hashes


def unfinished_outcome(run: Path, aid: str) -> dict[str, Any]:
    native = run / "runs" / aid / "native_verifier"
    if (native / "started.json").exists():
        receipt = native / "receipt.json"
        return {
            "outcome": "failed_native_unvalidated" if receipt.exists() else "failed_native_unknown",
            "model_attempted": True,
            "native_start_sha256": sha(native / "started.json"),
            "native_receipt_sha256": sha(receipt) if receipt.exists() else None,
        }
    if (run / "prepared" / f"{aid}.json").exists() or (
        run / "model-inputs" / f"{aid}.json"
    ).exists():
        return {"outcome": "failed_prepared_unverified", "model_attempted": False}
    reserved = [
        p for p in (run / "HTTP-ledger").glob("*-reserved.json") if read(p)["author_id"] == aid
    ]
    sources = list((run / "sources" / aid).glob("source-*.json"))
    if reserved or sources:
        return {
            "outcome": "failed_source_partial",
            "model_attempted": False,
            "source_reservation_sha256": [sha(p) for p in sorted(reserved)],
        }
    return {"outcome": "not_attempted", "model_attempted": False}


def source_http_counts(run: Path) -> dict[str, Any]:
    reserved = sorted((run / "HTTP-ledger").glob("*-reserved.json"))
    proofs = []
    physical = unknown = pre_http_failures = 0
    for path in reserved:
        request = read(path)
        finished_path = path.with_name(path.name.replace("-reserved.json", "-finished.json"))
        proof: dict[str, Any] = {"reservation_path": str(path), "reservation_sha256": sha(path)}
        if not finished_path.exists():
            unknown += 1
            proof["HTTP_started"] = None
        else:
            finished = read(finished_path)
            if any(finished.get(k) != v for k, v in request.items()):
                raise ValueError("Finished reservation binding changed")
            key = hashlib.sha256((request["kind"] + "\0" + request["url"]).encode()).hexdigest()
            candidates = [
                p
                for p in run.rglob(f"request-result-{key}.json")
                if sha(p) == finished["receipt_sha256"]
            ]
            if not candidates:
                raise ValueError("Finished request-result SHA changed")
            receipt = read(candidates[0])
            flag = finished["HTTP_started"]
            if (
                type(flag) is not bool
                or receipt["HTTP_started"] != flag
                or any(receipt[k] != request[k] for k in ("url", "kind"))
            ):
                raise ValueError("HTTP receipt binding changed")
            physical += int(flag)
            pre_http_failures += int(not flag)
            proof.update(
                HTTP_started=flag,
                finished_path=str(finished_path),
                finished_sha256=sha(finished_path),
                receipt_path=str(candidates[0]),
                receipt_sha256=sha(candidates[0]),
            )
        proofs.append(proof)
    return {
        "source_reservations": len(reserved),
        "physical_HTTP": physical,
        "pre_HTTP_failures": pre_http_failures,
        "unknown_HTTP_attempts": unknown,
        "proofs": proofs,
    }


def measure(root: Path) -> dict[str, Any]:
    run = root / "run"
    freeze = read(root / "stage-freeze.json")
    if code_hashes() != freeze["code_hashes"]:
        raise ValueError("Frozen runtime/rubric changed")
    if sha(Path(__file__)) != freeze["meter_sha256"]:
        raise ValueError("Frozen meter changed")
    inherited = read(root / "inherited.json")
    inherited_ids = set(inherited["verified_profile_ids"])
    rows = []
    refs_total = 0
    for profile in read(root / "profiles.json"):
        aid = profile["id"]
        row: dict[str, Any] = {"author_id": aid, "name": profile["name"], "human_reviewed": 0}
        row["source_failures"] = [
            read(p) for p in sorted((run / "source-failures" / aid).glob("*.json"))
        ]
        prepared = run / "prepared" / f"{aid}.json"
        result = run / "results" / f"{aid}.json"
        failure = run / "profile-failures" / f"{aid}.json"
        if prepared.exists():
            inp_path = Path(read(prepared)["input_path"])
            if sha(inp_path) != read(prepared)["sha256"]:
                raise ValueError("Input SHA changed")
            inp = check_contact_input(run, inp_path)
            refs_total += len(inp["evidence_pool"])
            row.update(
                candidates=len(inp["items"]),
                source_refs_audited=len(inp["evidence_pool"]),
                canonical_input_bytes=inp_path.stat().st_size,
                input_sha256=sha(inp_path),
            )
            transport_path = run / "model-inputs" / f"{aid}.json"
            if transport_path.exists():
                transport = read(transport_path)
                if (
                    transport["canonical_input_sha256"] != sha(inp_path)
                    or expand_input(transport["compact_input"]) != inp
                ):
                    raise ValueError("Lossless transport mapping changed")
                row.update(
                    actual_delivered_bytes=transport["actual_delivered_bytes"],
                    compact_blocks=len(transport["compact_input"]["evidence_blocks"]),
                    transport_sha256=sha(transport_path),
                )
        else:
            row["candidates"] = None
        row["Sol_usable"] = None
        if result.exists():
            check_result(run, inp_path, result)
            wrapper = read(result)
            if check_dates(read(run / "corpora" / f"{aid}.json"), wrapper["result"]) != read(
                run / "date-checks" / f"{aid}.json"
            ):
                raise ValueError("Date gate changed")
            native = run / "runs" / aid / "native_verifier"
            receipt = read(native / "receipt.json")
            for name, key in [
                ("raw-result.json", "raw_result_sha256"),
                ("events.jsonl", "events_sha256"),
                ("prompt.txt", "prompt_sha256"),
            ]:
                if sha(native / name) != receipt[key]:
                    raise ValueError("Native receipt SHA changed")
            prompt = read(native / "prompt.txt")
            delivered = prompt["task"]["semantic_input"]
            if aid in inherited_ids:
                if delivered != inp:
                    raise ValueError("Inherited original input changed")
            else:
                if expand_input(delivered) != inp or delivered != transport["compact_input"]:
                    raise ValueError("Actual native prompt not lossless")
                instruction = (native / "instructions.txt").read_text()
                if RUBRIC.read_text() not in instruction:
                    raise ValueError("Full rubric missing")
                actual = (native / "prompt.txt").stat().st_size + len(instruction.encode())
                if actual != transport["actual_delivered_bytes"] or actual > 1_000_000:
                    raise ValueError("Actual delivered cap changed")
            row.update(
                outcome="verified_inherited" if aid in inherited_ids else "verified_new",
                Sol_usable=sum(x["usable_coverage"] for x in wrapper["classifications"].values()),
                profile_assessments=wrapper["result"]["profile_assessments"],
                current="unknown",
                readiness="unknown",
            )
        elif failure.exists():
            data = read(failure)
            row.update(outcome=data["status"], failure=data)
            if data.get("model_called") is not False:
                raise ValueError("Unverified profile must not claim model completion")
            if data["status"] == "input_too_large" and (
                data["actual_delivered_bytes"] <= data["cap_bytes"]
                or (run / "runs" / aid / "native_verifier" / "started.json").exists()
            ):
                raise ValueError("Oversized outcome/model invariant")
        else:
            row.update(unfinished_outcome(run, aid))
        rows.append(row)
    starts = sorted(run.glob("runs/*/native_verifier/started.json"))
    receipts = sorted(run.glob("runs/*/native_verifier/receipt.json"))
    new_receipts = [p for p in receipts if p.parent.parent.name not in inherited_ids]
    native = [read(p) for p in new_receipts]
    http = sorted(run.glob("HTTP-ledger/*-reserved.json"))
    http_counts = source_http_counts(run)
    if len(starts) > 9 or len(http) > 180:
        raise ValueError("New round budgets exceeded")
    metrics = {
        "profiles": len(rows),
        "terminal_outcomes": sum(r["outcome"] != "not_attempted" for r in rows),
        "verified_new": sum(r["outcome"] == "verified_new" for r in rows),
        "verified_inherited": sum(r["outcome"] == "verified_inherited" for r in rows),
        "source_refs_audited": refs_total,
        "new_native_starts": len(starts),
        "new_completed_receipts": len(new_receipts),
        "unknown_attempts": len(starts) - len(new_receipts),
        "new_source_HTTP": http_counts["physical_HTTP"],
        "new_source_reservations": http_counts["source_reservations"],
        "new_pre_HTTP_failures": http_counts["pre_HTTP_failures"],
        "unknown_source_HTTP_attempts": http_counts["unknown_HTTP_attempts"],
        "new_search": 0,
        "inherited_search": 30,
        "tokens": {
            k: sum(r["tokens"].get(k, 0) or 0 for r in native)
            for k in [
                "input_tokens",
                "output_tokens",
                "cached_input_tokens",
                "cache_write_input_tokens",
                "reasoning_output_tokens",
            ]
        },
        "new_native_wall_seconds": sum(r["wall_elapsed_seconds"] for r in native),
        "inherited_old209_HTTP": 5,
        "inherited_old209_native_jobs": 1,
        "inherited_old209_tokens": 76071,
        "human_reviewed": 0,
        "generative_extraction_jobs": 0,
        "GLM_jobs": 0,
        "Astra_profile_jobs": 0,
        "subscription_debit": None,
        "API_licence_fee": 0,
        "search_usage": None,
        "development_review_usage": None,
    }
    return {
        "metrics": metrics,
        "rows": rows,
        "code_head": freeze["code_head"],
        "meter_sha256": sha(Path(__file__)),
        "HTTP_receipts": http_counts["proofs"],
        "new_native_receipts": [{"path": str(p), "sha256": sha(p)} for p in new_receipts],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit = measure(args.root)
    with args.output.open("x") as stream:
        json.dump(audit, stream, ensure_ascii=False, indent=2)
    print(json.dumps(audit["metrics"], ensure_ascii=False, indent=2))
