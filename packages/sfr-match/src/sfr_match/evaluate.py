"""Eval harness: run the golden set against a backend, persist rankings, build the judging pool."""

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import mean, median
from typing import Any

from sfr_match.evalset import Query
from sfr_match.search import Backend

DEFAULT_RUNS_DIR = Path("data/eval/runs")
POOL_DEPTH = 5  # SPEC_SFR1 §5.1: pool the top-5 of every model/variant


@dataclass
class QueryRun:
    query_id: str
    latency_ms: float
    hits: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Run:
    variant: str
    model_key: str
    hf_id: str | None
    clean: bool
    k: int
    n_profiles: int
    build_seconds: float
    results: list[QueryRun] = field(default_factory=list)

    @property
    def latencies(self) -> list[float]:
        return [result.latency_ms for result in self.results]

    def ranked_ids(self, query_id: str) -> list[str]:
        for result in self.results:
            if result.query_id == query_id:
                return [str(hit["author_id"]) for hit in result.hits]
        return []

    def top_score(self, query_id: str) -> float | None:
        for result in self.results:
            if result.query_id == query_id and result.hits:
                return float(result.hits[0]["score"])
        return None


def run_queries(backend: Backend, queries: list[Query], k: int = 10) -> Run:
    """Search every golden-set query, recording ranking and per-query latency.

    The backend is warmed up first: loading the model is a one-off cost of the
    process, not part of query latency.
    """
    backend.warmup()
    results: list[QueryRun] = []
    for query in queries:
        started = time.perf_counter()
        hits = backend.search(query.text, k=k)
        latency_ms = (time.perf_counter() - started) * 1000
        results.append(
            QueryRun(
                query_id=query.id,
                latency_ms=round(latency_ms, 2),
                hits=[
                    {
                        "rank": hit.rank,
                        "author_id": hit.author_id,
                        "name": hit.name,
                        "score": round(hit.score, 6),
                    }
                    for hit in hits
                ],
            )
        )
    meta = backend.meta
    return Run(
        variant=f"{meta.model_key}_clean" if meta.clean else meta.model_key,
        model_key=meta.model_key,
        hf_id=meta.hf_id,
        clean=meta.clean,
        k=k,
        n_profiles=meta.n_profiles,
        build_seconds=meta.build_seconds,
        results=results,
    )


def save_run(run: Run, runs_dir: Path = DEFAULT_RUNS_DIR) -> Path:
    runs_dir.mkdir(parents=True, exist_ok=True)
    path = runs_dir / f"{run.variant}.json"
    path.write_text(json.dumps(asdict(run), ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def load_run(path: Path) -> Run:
    payload = json.loads(path.read_text(encoding="utf-8"))
    results = [QueryRun(**result) for result in payload.pop("results", [])]
    return Run(**payload, results=results)


def load_runs(runs_dir: Path = DEFAULT_RUNS_DIR) -> list[Run]:
    if not runs_dir.exists():
        raise FileNotFoundError(f"{runs_dir} not found — run `sfr-match eval` first")
    return [load_run(path) for path in sorted(runs_dir.glob("*.json"))]


def latency_summary(run: Run) -> dict[str, float]:
    values = run.latencies
    if not values:
        return {"mean": 0.0, "median": 0.0, "max": 0.0}
    return {
        "mean": round(mean(values), 1),
        "median": round(median(values), 1),
        "max": round(max(values), 1),
    }


def build_pool(runs: list[Run], depth: int = POOL_DEPTH) -> list[tuple[str, str]]:
    """Union of the top-``depth`` results of every run, sorted by author id.

    Sorting by author (not by score) keeps the judge blind to which model produced
    the pair — a requirement of the judging protocol.
    """
    pairs: set[tuple[str, str]] = set()
    for run in runs:
        for result in run.results:
            for hit in result.hits[:depth]:
                pairs.add((result.query_id, str(hit["author_id"])))
    return sorted(pairs, key=lambda pair: (pair[0], pair[1]))
