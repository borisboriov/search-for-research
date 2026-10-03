"""Offline, uncached ranking comparison. No API configuration or index writes.

Each (variant, repeat) runs in a fresh process; order alternates per repeat.
Latency covers API query validation and full backend query encoding/search, but
not HTTP, card enrichment, response serialization or the API response cache.
Baseline top-50 diagnostics are obtained separately, outside the timed top-5.
Outputs require a new directory and individual files use exclusive creation.
"""

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import resource
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from sfr_api.service import MatchService
from sfr_api.settings import ApiSettings
from sfr_match.evalset import load_queries, profile_fingerprint
from sfr_match.models import resolve_model
from sfr_match.search import Bm25Backend, DenseBackend, Hit

DEPTH = 50
RRF_K = 60
VARIANTS = ("baseline", "hybrid")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def rss_bytes(value: float | None = None, system: str | None = None) -> int:
    """ru_maxrss is bytes on macOS, KiB on Linux; this is process peak RSS."""
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if value is None else value
    return int(raw * (1 if (system or sys.platform) == "darwin" else 1024))


def fuse(dense: list[Hit], lexical: list[Hit], k: int = 5) -> list[Hit]:
    """Equal-weight RRF, ignoring zero/negative BM25 matches; stable id tie break."""
    scores: dict[str, float] = defaultdict(float)
    by_id: dict[str, Hit] = {}
    for ranking in (dense, [hit for hit in lexical if hit.score > 0]):
        seen: set[str] = set()
        for rank, hit in enumerate(ranking, 1):
            if hit.author_id in seen:
                raise ValueError("duplicate author in ranking")
            seen.add(hit.author_id)
            scores[hit.author_id] += 1.0 / (RRF_K + rank)
            by_id[hit.author_id] = hit
    ordered = sorted(scores, key=lambda author: (-scores[author], author))[:k]
    return [
        replace(by_id[author], rank=rank, score=scores[author])
        for rank, author in enumerate(ordered, 1)
    ]


def query_inputs(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in paths:
        for query in load_queries(path):
            if query.id in seen:
                raise ValueError(f"duplicate query id across sets: {query.id}")
            seen.add(query.id)
            rows.append({**query.model_dump(), "group": path.stem})
    if not rows:
        raise ValueError("empty query inputs")
    return rows


def model_revision(dense: DenseBackend) -> str | None:
    # Transformers retain resolved cache commit in model config when available.
    model = getattr(dense.embedder, "model", None)
    if model is None:
        return None
    try:
        first = model[0]
    except (TypeError, KeyError, IndexError):
        return None
    config = getattr(getattr(first, "auto_model", None), "config", None)
    return getattr(config, "_commit_hash", None)


def run_worker(index_dir: Path, queries: list[dict[str, Any]], variant: str) -> dict[str, Any]:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    started = time.perf_counter()
    dense = DenseBackend(index_dir, resolve_model("frida"))
    if dense.meta.model_key != "frida" or len(dense.docs) != dense.meta.n_profiles:
        raise ValueError("expected consistent FRIDA index")
    lexical = Bm25Backend(index_dir, resolve_model("bm25")) if variant == "hybrid" else None
    service = MatchService(dense, ApiSettings(), extras={})
    build_seconds = time.perf_counter() - started
    started = time.perf_counter()
    dense.warmup()
    warmup_seconds = time.perf_counter() - started
    rows = []
    for query in queries:
        started = time.perf_counter()
        try:
            text, _ = service.validate(query["text"], 5)
            dense_hits = dense.search(text, k=5 if variant == "baseline" else DEPTH)
            hits = dense_hits if lexical is None else fuse(dense_hits, lexical.search(text, DEPTH))
            latency_ms = (time.perf_counter() - started) * 1000
            diagnostic = dense_hits if variant == "hybrid" else []
            rows.append(
                {
                    "query_id": query["id"],
                    "latency_ms": latency_ms,
                    "hits": [asdict(hit) for hit in hits],
                    "dense_top50": [asdict(hit) for hit in diagnostic],
                    "error": None,
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "query_id": query["id"],
                    "latency_ms": (time.perf_counter() - started) * 1000,
                    "hits": [],
                    "dense_top50": [],
                    "error": {"type": type(exc).__name__, "message": str(exc)},
                }
            )
    timed_peak = rss_bytes()
    if variant == "baseline":
        for query, row in zip(queries, rows, strict=True):
            if row["error"] is None:
                try:
                    text, _ = service.validate(query["text"], 5)
                    row["dense_top50"] = [asdict(hit) for hit in dense.search(text, k=DEPTH)]
                except Exception as exc:
                    row["diagnostic_error"] = type(exc).__name__
    return {
        "variant": variant,
        "build_seconds": build_seconds,
        "warmup_seconds": warmup_seconds,
        "peak_rss_bytes": timed_peak,
        "diagnostic_peak_rss_bytes": rss_bytes(),
        "api_validation": {
            "min_query_chars": service.settings.min_query_chars,
            "max_query_chars": service.settings.max_query_chars,
            "k": 5,
        },
        "search_backend": dense.searcher.name,
        "index_meta": asdict(dense.meta),
        "index_input_sha256": {
            path.name: sha256_file(path) for path in sorted(index_dir.iterdir()) if path.is_file()
        },
        "model_revision": model_revision(dense),
        "results": rows,
    }


def blind_pool(runs: list[dict[str, Any]], queries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    texts = {query["id"]: query["text"] for query in queries}
    pairs: dict[tuple[str, str], dict[str, Any]] = {}
    for run in runs:
        for row in run["results"]:
            for hit in row["hits"][:5]:
                key = (row["query_id"], hit["author_id"])
                text = hit["profile_text"]
                record = {
                    "query_id": key[0],
                    "author_id": key[1],
                    "query": texts[key[0]],
                    "topics": hit.get("topics", []),
                    "name": hit["name"],
                    "profile_text": text,
                    "profile_fp": profile_fingerprint(text),
                    "profile_hash": hashlib.sha256(text.encode()).hexdigest(),
                }
                if key in pairs and pairs[key] != record:
                    raise ValueError(f"inconsistent snapshot: {key}")
                pairs[key] = record
    return [pairs[key] for key in sorted(pairs)]


def snapshot(index_dir: Path, paths: list[Path]) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    versions = {}
    for package in ("numpy", "torch", "sentence-transformers", "transformers", "rank-bm25"):
        versions[package] = importlib.metadata.version(package)
    inputs = [
        *sorted(path for path in index_dir.iterdir() if path.is_file()),
        *paths,
        Path(__file__).resolve(),
        root / "uv.lock",
    ]
    return {
        "code_commit": commit,
        "python": sys.version,
        "platform": platform.platform(),
        "versions": versions,
        "input_sha256": {str(path): sha256_file(path) for path in inputs},
        "rrf_k": RRF_K,
        "criterion_sha256": sha256_file(
            root / "packages/sfr-match/eval/CRITERIA_RANKING17_20261003.md"
        ),
        "dense_depth": DEPTH,
        "bm25_depth": DEPTH,
        "weights": [1, 1],
        "offline": True,
        "repeat": 3,
        "latency_scope": "API validate + uncached backend encode/search; no HTTP/cards",
        "rss_scope": "fresh process peak before separate baseline top50 diagnostics",
        "order": [list(VARIANTS), list(reversed(VARIANTS)), list(VARIANTS)],
        "environment": {
            key: os.environ.get(key)
            for key in (
                "SFR_SEARCH_BACKEND",
                "OMP_NUM_THREADS",
                "MKL_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "TOKENIZERS_PARALLELISM",
            )
        },
    }


def run(index_dir: Path, paths: list[Path], out_dir: Path) -> None:
    queries = query_inputs(paths)
    inputs = snapshot(index_dir, paths)
    out_dir.mkdir(parents=True, exist_ok=False)
    write_json(out_dir / "snapshot.json", inputs)
    write_json(out_dir / "queries.json", queries)
    runs = []
    for repeat in range(3):
        for variant in VARIANTS if repeat % 2 == 0 else reversed(VARIANTS):
            output = out_dir / f"{variant}-{repeat + 1}.json"
            subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "worker",
                    "--index-dir",
                    str(index_dir),
                    "--variant",
                    variant,
                    "--queries-json",
                    str(out_dir / "queries.json"),
                    "--out",
                    str(output),
                ],
                check=True,
            )
            runs.append(json.loads(output.read_text(encoding="utf-8")))
    write_jsonl(out_dir / "blind_pool.jsonl", blind_pool(runs, queries))


def latency_summary(values: list[float]) -> dict[str, float]:
    if not values:
        return {"median": 0.0, "p95": 0.0, "max": 0.0}
    ordered = sorted(values)
    from statistics import median

    return {
        "median": median(values),
        "p95": ordered[math.ceil(0.95 * len(ordered)) - 1],
        "max": max(values),
    }


def latency_reports(runs: list[dict[str, Any]]) -> dict[str, Any]:
    reports = {}
    for variant in VARIANTS:
        samples = [run for run in runs if run["variant"] == variant]
        reports[variant] = {
            "aggregate": latency_summary(
                [row["latency_ms"] for run in samples for row in run["results"]]
            ),
            "repeats": [
                latency_summary([row["latency_ms"] for row in run["results"]]) for run in samples
            ],
        }
    return reports


def measure(out_dir: Path, judgments_path: Path, output: Path) -> None:
    queries = json.loads((out_dir / "queries.json").read_text(encoding="utf-8"))
    runs = [
        json.loads((out_dir / f"{variant}-{repeat}.json").read_text(encoding="utf-8"))
        for variant in VARIANTS
        for repeat in range(1, 4)
    ]
    reference = runs[0]
    for sample in runs[1:]:
        for field in (
            "index_meta",
            "index_input_sha256",
            "model_revision",
            "search_backend",
            "api_validation",
        ):
            if sample.get(field) != reference.get(field):
                raise ValueError(f"inconsistent run snapshot: {field}")
    judgments: dict[tuple[str, str], dict[str, Any]] = {}
    for row in read_jsonl(judgments_path):
        key = (row["query_id"], row["author_id"])
        if key in judgments:
            raise ValueError(f"duplicate judgment: {key}")
        if row["grade"] not in (0, 1, 2) or row.get("alternate_grade", row["grade"]) not in (
            0,
            1,
            2,
        ):
            raise ValueError(f"invalid grade: {key}")
        if row.get("judge") != "gpt-6-astra/max (sfr-judge)":
            raise ValueError(f"unexpected judge: {key}")
        judgments[key] = row
    # Validate the union of ALL repeats; missing/stale labels abort rather than become zero.
    for pair in blind_pool(runs, queries):
        key = (pair["query_id"], pair["author_id"])
        judgment = judgments.get(key)
        if judgment is None or judgment.get("profile_fp") != pair["profile_fp"]:
            raise ValueError(f"missing/stale profile_fp judgment: {key}")
        if judgment.get("profile_hash", pair["profile_hash"]) != pair["profile_hash"]:
            raise ValueError(f"stale profile_hash judgment: {key}")
    by_query = {query["id"]: query for query in queries}
    for sample in runs:
        ids = [row["query_id"] for row in sample["results"]]
        if len(ids) != len(set(ids)) or set(ids) != set(by_query):
            raise ValueError("run has missing, extra or duplicate query results")
    per_query = []
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for variant in VARIANTS:
        samples = [item for item in runs if item["variant"] == variant]
        if len(samples) != 3:
            raise ValueError("expected three repeats")
        for first in samples[0]["results"]:
            qid = first["query_id"]
            repeats = [
                next(row for row in sample["results"] if row["query_id"] == qid)
                for sample in samples
            ]

            def signature(row: dict[str, Any]) -> tuple[list[str], Any]:
                return ([hit["author_id"] for hit in row["hits"]], row["error"])

            if any(signature(row) != signature(first) for row in repeats[1:]):
                raise ValueError(f"nondeterministic ranking/errors: {variant} {qid}")
            grades = [judgments[(qid, hit["author_id"])] for hit in first["hits"][:5]]
            row = {
                "query_id": qid,
                "variant": variant,
                "group": by_query[qid]["group"],
                "expect": by_query[qid]["expect"],
                "error": first["error"],
                "ranked_ids": [hit["author_id"] for hit in first["hits"][:5]],
                "grade2_count": sum(item["grade"] == 2 for item in grades),
                "latency_ms": [sample["latency_ms"] for sample in repeats],
            }
            for k in (1, 5):
                row[f"success@{k}"] = any(item["grade"] >= 2 for item in grades[:k])
                row[f"success@{k}_lower"] = any(
                    min(item["grade"], item.get("alternate_grade", item["grade"])) >= 2
                    for item in grades[:k]
                )
                row[f"success@{k}_upper"] = any(
                    max(item["grade"], item.get("alternate_grade", item["grade"])) >= 2
                    for item in grades[:k]
                )
            row["ood_false_accept"] = (
                bool(first["hits"] and first["hits"][0]["score"] >= 0.33)
                if variant == "baseline" and row["group"] == "ood_queries"
                else None
            )
            per_query.append(row)
            groups[f"{variant}/{row['group']}/{row['expect']}"].append(row)
            if qid.startswith("q") and row["expect"] == "in-domain" and qid not in ("q29", "q30"):
                groups[f"{variant}/historical22/in-domain"].append(row)
    summaries = {}
    for group_key, rows in groups.items():
        summary: dict[str, Any] = {
            "n": len(rows),
            "errors": sum(row["error"] is not None for row in rows),
        }
        for metric in (
            "success@1",
            "success@5",
            "success@1_lower",
            "success@1_upper",
            "success@5_lower",
            "success@5_upper",
        ):
            summary[metric] = {
                "count": sum(row[metric] for row in rows),
                "total": len(rows),
                "rate": sum(row[metric] for row in rows) / len(rows),
            }
        summary["ood_false_accept_count"] = sum(row["ood_false_accept"] is True for row in rows)
        summaries[group_key] = summary
    query_changes = []
    for qid in by_query:
        baseline = next(
            row for row in per_query if row["query_id"] == qid and row["variant"] == "baseline"
        )
        hybrid = next(
            row for row in per_query if row["query_id"] == qid and row["variant"] == "hybrid"
        )
        query_changes.append(
            {
                "query_id": qid,
                "success@1_delta": int(hybrid["success@1"]) - int(baseline["success@1"]),
                "success@5_delta": int(hybrid["success@5"]) - int(baseline["success@5"]),
            }
        )
    write_json(
        output,
        {
            "judgments_sha256": sha256_file(judgments_path),
            "groups": summaries,
            "per_query": per_query,
            "query_changes": query_changes,
            "latencies": latency_reports(runs),
            "recommendation": recommendation(per_query, runs),
            "resources": [
                {
                    key: item[key]
                    for key in ("variant", "build_seconds", "warmup_seconds", "peak_rss_bytes")
                }
                for item in runs
            ],
            "disputed": [
                row
                for row in judgments.values()
                if row.get("alternate_grade", row["grade"]) != row["grade"]
            ],
            "notes": [
                "Errors remain in denominators, with success false.",
                "OOD confidence uses baseline cosine only; hybrid uncalibrated.",
            ],
        },
    )


def recommendation(rows: list[dict[str, Any]], runs: list[dict[str, Any]]) -> dict[str, Any]:
    pairs: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        pairs.setdefault(row["query_id"], {})[row["variant"]] = row
    losses = []
    gains = []
    ood_added = []
    disputed_gain = False
    for qid, pair in pairs.items():
        baseline, hybrid = pair["baseline"], pair["hybrid"]
        if baseline["group"] == "ood_queries":
            if hybrid["grade2_count"] > baseline["grade2_count"]:
                ood_added.append(qid)
            continue
        for k in (1, 5):
            metric = f"success@{k}"
            if baseline[metric] and not hybrid[metric]:
                losses.append({"query_id": qid, "metric": metric})
            if (
                not baseline[metric]
                and hybrid[metric]
                and (qid.startswith("q") or qid.startswith("p"))
            ):
                gains.append({"query_id": qid, "metric": metric})
                disputed_gain |= baseline[f"{metric}_upper"] or not hybrid[f"{metric}_lower"]
    latency = latency_reports(runs)
    rss = {
        variant: max(item["peak_rss_bytes"] for item in runs if item["variant"] == variant)
        for variant in VARIANTS
    }
    checks = {
        "zero_errors": all(row["error"] is None for row in rows),
        "no_success_losses": not losses,
        "golden_or_pilot_gain": bool(gains),
        "no_added_ood_grade2": not ood_added,
        "latency_limit": latency["hybrid"]["aggregate"]["p95"]
        <= latency["baseline"]["aggregate"]["p95"] * 1.25 + 50,
        "memory_limit": rss["hybrid"] <= rss["baseline"] * 1.25 + 256 * 1024 * 1024,
    }
    passed = all(checks.values())
    return {
        "checks": checks,
        "losses": losses,
        "gains": gains,
        "ood_added_queries": ood_added,
        "disputed_gain": bool(disputed_gain),
        "decision": ("hypothesis_only" if disputed_gain else "continue_local_hybrid")
        if passed
        else "keep_current",
        "scope": "These queries and local CPU only; no independent holdout or VPS claim.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    runner = commands.add_parser("run")
    runner.add_argument("--index-dir", type=Path, required=True)
    runner.add_argument("--queries", type=Path, nargs="+", required=True)
    runner.add_argument("--out-dir", type=Path, required=True)
    worker = commands.add_parser("worker")
    worker.add_argument("--index-dir", type=Path, required=True)
    worker.add_argument("--variant", choices=VARIANTS, required=True)
    worker.add_argument("--queries-json", type=Path, required=True)
    worker.add_argument("--out", type=Path, required=True)
    metrics = commands.add_parser("measure")
    metrics.add_argument("--out-dir", type=Path, required=True)
    metrics.add_argument("--judgments", type=Path, required=True)
    metrics.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "run":
        run(
            args.index_dir.resolve(),
            [path.resolve() for path in args.queries],
            args.out_dir.resolve(),
        )
    elif args.command == "worker":
        write_json(
            args.out,
            run_worker(args.index_dir, json.loads(args.queries_json.read_text()), args.variant),
        )
    else:
        measure(args.out_dir, args.judgments, args.out)


if __name__ == "__main__":
    main()
