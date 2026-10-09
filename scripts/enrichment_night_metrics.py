"""Числовой итог ночи из сохранённых receipts; без контактов и новых calls."""

import argparse
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

from enrichment_batch import encoded, immutable
from enrichment_experiment import FIELDS, private_root, read, sha, verified_sample
from enrichment_night import checked_result

NIGHT_ROOTS = (
    "enrichment-night-cli-v1-20261009",
    "enrichment-night-cli-v2-20261009",
    "enrichment-night-cli-v3-fixed-20261009",
    "enrichment-night-cli-v4-20261009",
)
IMPORTANT = (
    "personal_contact",
    "coordinator_contact",
    "supervision_history",
    "published_recruitment",
    "direct_willingness",
)


def tokens(receipt: dict[str, Any], stage: str) -> dict[str, Any]:
    if stage == "collector":
        usage = receipt["token_usage"]
        return {
            "input_tokens": usage["input"] + usage["cacheRead"] + usage["cacheWrite"],
            "uncached_input_tokens": usage["input"],
            "cached_input_tokens": usage["cacheRead"],
            "cache_write_input_tokens": usage["cacheWrite"],
            "output_tokens": usage["output"],
            "reasoning_output_tokens": usage.get("reasoning"),
            "input_plus_output": usage["totalTokens"],
            "usage_complete": receipt["usage_complete"],
        }
    usage = receipt["tokens"]
    return {
        **usage,
        "input_plus_output": usage["input_tokens"] + usage["output_tokens"],
        "usage_complete": True,
    }


def physical_jobs(parent: Path) -> list[dict[str, Any]]:
    jobs: dict[str, dict[str, Any]] = {}
    fingerprints: dict[str, str] = {}
    for name in NIGHT_ROOTS:
        root = parent / name
        if not root.exists():
            continue
        for path in sorted((root / "runs").glob("*/*/receipt.json")):
            stage = path.parent.name
            if stage not in ("collector", "native_verifier"):
                continue
            receipt = read(path)
            agent = receipt["agent_id"]
            digest = sha(path)
            if agent in jobs:
                if fingerprints[agent] != digest:
                    raise ValueError("Один physical agent_id с разными receipts")
                jobs[agent]["receipt_copies"].append(str(path))
                continue
            if stage == "native_verifier":
                for file, key in (
                    ("raw-result.json", "raw_result_sha256"),
                    ("events.jsonl", "events_sha256"),
                    ("prompt.txt", "prompt_sha256"),
                ):
                    if sha(path.parent / file) != receipt[key]:
                        raise ValueError("Native первичный артефакт изменён")
            fingerprints[agent] = digest
            jobs[agent] = {
                "agent_id": agent,
                "author_id": path.parent.parent.name,
                "stage": stage,
                "root": name,
                "receipt_sha256": digest,
                "receipt_copies": [str(path)],
                "wall_seconds": receipt["wall_elapsed_seconds"],
                "tokens": tokens(receipt, stage),
                "model_requests": receipt.get("model_requests", 1),
                "budget": receipt.get("budget"),
                "requested_config": receipt.get(
                    "requested_config",
                    {
                        "model": receipt.get("requested_model"),
                        "effort": receipt.get("requested_effort"),
                    },
                ),
                "actual_backend": None,
            }
    return list(jobs.values())


def profile_metrics(root: Path) -> list[dict[str, Any]]:
    profiles = []
    for profile in verified_sample(root):
        aid = profile["id"]
        if not (root / "results" / f"{aid}.json").exists():
            profiles.append({"author_id": aid, "completed": False})
            continue
        wrapper = checked_result(root, aid)
        source = read(Path(wrapper["input_path"]))
        result = wrapper["result"]
        derived = wrapper["classifications"]
        coverage = Counter(
            row["coverage_field"] for row in derived.values() if row["usable_coverage"]
        )
        supported: Counter[str] = Counter()
        for item in source["items"]:
            assessment = next(row for row in result["items"] if row["item_id"] == item["item_id"])
            if all(
                assessment[key] == "supported"
                for key in ("text_verdict", "identity_verdict", "object_relation")
            ) and (
                assessment["field_verdict"] == "correct"
                or (
                    assessment["field_verdict"] == "misclassified"
                    and assessment["corrected_field"] is not None
                )
            ):
                supported[assessment["corrected_field"] or item["original_field"]] += 1
        collector, verifier = wrapper["collector_receipt"], wrapper["verifier_receipt"]
        profiles.append(
            {
                "author_id": aid,
                "completed": True,
                "result_sha256": sha(root / "results" / f"{aid}.json"),
                "candidate_atoms": len(source["items"]),
                "literal_evidence": len(source["evidence_pool"]),
                "rejected_candidates": wrapper["rejected_candidates"],
                "original_coverage_atoms": sum(coverage.values()),
                "original_coverage_fields": dict(coverage),
                "important_fields_with_coverage": [field for field in IMPORTANT if coverage[field]],
                "supported_facts_by_field_including_additional_historical": dict(supported),
                "axes": {key: row["verdict"] for key, row in result["profile_assessments"].items()},
                "unknown_or_unchecked_fields": [field for field in FIELDS if not coverage[field]],
                "collector_seconds": collector["wall_elapsed_seconds"],
                "verifier_seconds": verifier["wall_elapsed_seconds"],
                "pipeline_seconds": collector["wall_elapsed_seconds"]
                + verifier["wall_elapsed_seconds"],
                "collector_tokens": tokens(collector, "collector"),
                "verifier_tokens": tokens(verifier, "native_verifier"),
                "collector_budget": collector["budget"],
                "collector_model_requests": collector["model_requests"],
            }
        )
    return profiles


def total(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"jobs": 0}
    keys = (
        "input_tokens",
        "cached_input_tokens",
        "cache_write_input_tokens",
        "output_tokens",
        "reasoning_output_tokens",
        "input_plus_output",
    )
    return {
        "jobs": len(rows),
        "wall_seconds": sum(row["wall_seconds"] for row in rows),
        "model_requests": sum(row["model_requests"] for row in rows),
        "usage_complete": all(row["tokens"]["usage_complete"] for row in rows),
        "tokens": {
            key: sum(row["tokens"][key] for row in rows)
            if all(type(row["tokens"].get(key)) is int for row in rows)
            else None
            for key in keys
        },
    }


def measured(root: Path) -> dict[str, Any]:
    profiles = profile_metrics(root)
    completed = [row for row in profiles if row["completed"]]
    jobs = physical_jobs(root.parent)
    scenarios = []
    for target in (1000, 10000):
        daily = (target + 59) // 60
        if not completed:
            continue
        # Only a conditional linear workload, not throughput/quota feasibility.
        model_seconds = mean(row["pipeline_seconds"] for row in completed)
        cinput = mean(row["collector_tokens"]["uncached_input_tokens"] for row in completed)
        cached = mean(row["collector_tokens"]["cached_input_tokens"] for row in completed)
        output = mean(row["collector_tokens"]["output_tokens"] for row in completed)
        model_credits = (cinput * 2.3 + cached * 0.56 + output * 8) / 10000
        tool_credits = mean(
            (
                4
                - row["collector_budget"]["search_remaining"]
                + row["collector_budget"]["source_reads"]
            )
            * 1.2
            for row in completed
        )
        scenarios.append(
            {
                "target": target,
                "days": 60,
                "profiles_per_day_ceiling": daily,
                "observed_completed_denominator": len(completed),
                "model_pipeline_hours_per_day_if_linear": daily * model_seconds / 3600,
                "observed_seconds_per_completed_range": [
                    min(row["pipeline_seconds"] for row in completed),
                    max(row["pipeline_seconds"] for row in completed),
                ],
                "glm_documentary_credits_per_day_range": [
                    daily * (model_credits * 0.5 + tool_credits),
                    daily * (model_credits + tool_credits),
                ],
                "glm_credit_formula_is_not_actual_quota_or_payment": True,
                "gpt_input_plus_output_per_day_if_linear": daily
                * mean(row["verifier_tokens"]["input_plus_output"] for row in completed),
                "human_hours_per_day": None,
                "real_quota_capacity": None,
                "subscription_cost_usd": None,
                "commercial_scale_permission": "unverified",
                "catalogue_unique_profiles": 9002,
                "target_exceeds_current_catalogue": target > 9002,
                "failed_attempts_development_review_and_queue_time_excluded": True,
            }
        )
    return {
        "method": "night-measurements-v1",
        "pipeline_manifest_sha256": sha(root / "manifest.json"),
        "profiles_selected": len(profiles),
        "profiles_completed": len(completed),
        "profiles": profiles,
        "unique_physical_jobs": jobs,
        "physical_totals": {
            stage: total([row for row in jobs if row["stage"] == stage])
            for stage in ("collector", "native_verifier")
        },
        "conditional_scale_scenarios": scenarios,
        "human_reviewed": 0,
        "tokens_are_not_subscription_payment": True,
        "preparation_and_independent_review_usage_excluded": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    private_root(args.output.parent)
    immutable(args.output, encoded(measured(args.root)))


if __name__ == "__main__":
    main()
