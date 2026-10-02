"""Publish safe aggregate proof artifacts from the isolated analytics rehearsal.

Input remains private under data/. No raw query, context, result names or headers
are copied. Run only after rehearsal/restore/browser validation has completed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def collect(source: Path) -> dict[str, Any]:
    def read(name: str) -> Any:
        return json.loads((source / name).read_text())

    baseline = read("baseline-linux.json")
    current = read("with-analytics-linux.json")
    oracle = read("oracle-report-v2/summary.json")
    restored = read("backup-final/restore-sfr_restore_179_handoff.json")
    manifest = read("pull-final/manifest.json")
    result: dict[str, Any] = {
        "schema_version": 1,
        "scope": "isolated local Docker Linux arm64; synthetic traffic, real FRIDA where explicit",
        "persistence": read("persistence-final.json"),
        "invalid_unicode": read("invalid-unicode.json"),
        "write_overhead": read("write-overhead.json"),
        "stalled_disk": {
            variant: {
                key: value
                for key, value in read(f"stress/stress-{variant}.json").items()
                if key not in ("responses",)
            }
            for variant in ("before", "after")
        },
        "resource_snapshot": [
            json.loads(line)
            for line in (source / "docker-resources.jsonl").read_text().splitlines()
        ],
        "search_equivalence": {
            "fixed_queries": 3,
            "identical_results_order_scores_confidence": current[
                "unchanged_ranking_scores_confidence"
            ],
            "real_frida_extra_confidence": current["extra_real_frida_confidence"],
            "model_warmup": True,
            "startup_included": False,
            "baseline_search_miss_ms": [
                r["wall_ms"] for r in baseline["rows"] if r["stage"] == "search-cache-miss"
            ],
            "pipeline_search_miss_ms": [
                r["wall_ms"] for r in current["rows"] if r["stage"] == "search-cache-miss"
            ],
            "pipeline_cache_hit_ms": [
                r["wall_ms"] for r in current["rows"] if r["stage"] == "search-cache-hit"
            ],
            "comparability": (
                "baseline direct service vs new HTTP pipeline; different runtime load; "
                "not an analytics speedup or cold-model benchmark"
            ),
        },
        "oracle": {
            key: oracle[key]
            for key in (
                "start_utc",
                "end_utc",
                "visits",
                "searches",
                "funnel_visits",
                "funnel_attempts",
                "repeat_attempts",
                "direct_profiles",
                "excluded_visits",
                "replay_lag_max_seconds",
                "clock_anomalies",
                "observed_sequence_gap_count",
                "visits_with_sequence_gaps",
            )
        },
        "restore": {
            "source_matches": restored["source_matches"],
            "restored": restored["restored"],
            "dump_sha256": restored["dump_sha256"],
        },
        "mac_copy": {
            "verified": True,
            "files": manifest["files"],
            "consistency": manifest["consistency"],
        },
        "rate_limits": read("rate-limits.json"),
        "diagnostic_exit_policy": read("check-live-final.json"),
        "postgres_initialization": read("pg-initialization.json"),
        "caddy_regression": read("caddy-regression.json"),
        "browser": read("browser-counts-v2.json"),
        "full_browser_suite": read("full-browser-summary.json"),
    }
    for item in manifest["files"]:
        digest = hashlib.sha256()
        with (source / "pull-final" / item["path"]).open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != item["sha256"]:
            raise ValueError("external copy checksum mismatch")
    if not restored["source_matches"] or not current["unchanged_ranking_scores_confidence"]:
        raise ValueError("rehearsal proof failed")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = collect(args.source)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
