"""Resource and latency measurements of the API, for the VPS decision (SPEC_SFR2 §3).

Runs the container once per model and records what a hosting choice actually needs:
cold start, RAM at rest and under load, p50/p95 at 1 and 4 concurrent requests, and
the image size. The same pass also checks, on real 1536-dim vectors, that the FAISS
search path returns what the NumPy scan returns — the equivalence the unit tests can
only assert on toy vectors.

    uv run python scripts/bench_api.py --out docs/sfr2_resources.json

With ``--no-docker`` the same measurements are taken against a locally started
uvicorn (honest fallback: RAM and cold start are then host numbers, not container ones).
"""

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import httpx

QUERIES = [
    "нейросети для медицинских изображений",
    "оптимизация маршрутов доставки и алгоритмы для логистики",
    "нейтринные эксперименты и безнейтринный двойной бета-распад",
    "квантовые вычисления и алгоритмы для них",
    "машинное обучение в физике частиц",
    "материалы для солнечных батарей",
    "обработка естественного языка, языковые модели",
    "биоинформатика и анализ геномных данных",
]
BASE_URL = "http://127.0.0.1:8000"

# Shown in the report as «запрос → ответ»: one broad, one narrow, one deliberately
# outside the corpus (that one must come back with below_threshold = true).
EXAMPLE_QUERIES = [
    "нейросети для медицинских изображений",
    "нейтринные эксперименты и безнейтринный двойной бета-распад",
    "как самому починить стиральную машину, которая не сливает воду",
]


def percentile(values: list[float], share: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, round(share * (len(ordered) - 1)))
    return round(ordered[index], 1)


def run(command: list[str], env: dict[str, str] | None = None, check: bool = True) -> str:
    result = subprocess.run(
        command, capture_output=True, text=True, env={**os.environ, **(env or {})}, check=False
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"{' '.join(command)} → {result.returncode}\n{result.stderr}")
    return result.stdout.strip()


def container_memory_mb() -> float | None:
    """Resident memory of the container as Docker reports it."""
    out = run(
        ["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", "sfr-api"], check=False
    )
    if not out or "/" not in out:
        return None
    used = out.split("/")[0].strip()
    number = float("".join(ch for ch in used if ch.isdigit() or ch == "."))
    if used.upper().endswith("GIB"):
        number *= 1024
    elif used.upper().endswith("KIB"):
        number /= 1024
    return round(number, 1)


def wait_until_healthy(timeout: float = 600.0) -> tuple[float, dict[str, Any]]:
    """Seconds from process start to the first successful /api/health."""
    started = time.perf_counter()
    deadline = started + timeout
    while time.perf_counter() < deadline:
        try:
            response = httpx.get(f"{BASE_URL}/api/health", timeout=5.0)
            if response.status_code == 200:
                return round(time.perf_counter() - started, 1), response.json()
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise TimeoutError("API did not become healthy in time")


def ask(client: httpx.Client, query: str, k: int = 10) -> tuple[float, dict[str, Any]]:
    started = time.perf_counter()
    response = client.post(f"{BASE_URL}/api/match", json={"query": query, "k": k}, timeout=60.0)
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.raise_for_status()
    return elapsed_ms, response.json()


def measure_sequential(n: int) -> list[float]:
    with httpx.Client() as client:
        return [ask(client, QUERIES[i % len(QUERIES)])[0] for i in range(n)]


def measure_concurrent(n: int, workers: int) -> tuple[list[float], float]:
    from concurrent.futures import ThreadPoolExecutor

    clients = [httpx.Client() for _ in range(workers)]
    started = time.perf_counter()
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            latencies = list(
                pool.map(
                    lambda i: ask(clients[i % workers], QUERIES[i % len(QUERIES)])[0], range(n)
                )
            )
    finally:
        for client in clients:
            client.close()
    return latencies, round(n / (time.perf_counter() - started), 2)


def rankings() -> dict[str, list[tuple[str, float]]]:
    """Top-10 (author, score) per query — the artefact compared across backends."""
    with httpx.Client() as client:
        return {
            query: [(hit["author_id"], hit["score"]) for hit in ask(client, query)[1]["results"]]
            for query in QUERIES
        }


def examples(k: int = 5) -> list[dict[str, Any]]:
    """Full API answers for the report — the same shape a front-end would render."""
    captured = []
    with httpx.Client() as client:
        for query in EXAMPLE_QUERIES:
            _, body = ask(client, query, k=k)
            captured.append(
                {
                    "request": {"query": query, "k": k},
                    "took_ms": body["took_ms"],
                    "below_threshold": body["below_threshold"],
                    "index_version": body["index_version"],
                    "results": [
                        {
                            "rank": hit["rank"],
                            "name": hit["name"],
                            "score": hit["score"],
                            "institution": hit["institution"],
                            "h_index": hit["h_index"],
                            "topics": hit["topics"],
                        }
                        for hit in body["results"]
                    ],
                }
            )
    return captured


def compose_up(model: str, search_backend: str) -> None:
    run(
        ["docker", "compose", "up", "-d", "--force-recreate"],
        env={
            "SFR_API_MODEL": model,
            "SFR_SEARCH_BACKEND": search_backend,
            "SFR_HF_CACHE": str(Path.home() / ".cache" / "huggingface"),
        },
    )


def compose_down() -> None:
    run(["docker", "compose", "down"], check=False)


def image_size_mb() -> float | None:
    out = run(["docker", "image", "inspect", "sfr-api:latest", "-f", "{{.Size}}"], check=False)
    return round(int(out) / 1024 / 1024, 1) if out.isdigit() else None


def bench_model(model: str, requests_n: int, docker: bool) -> dict[str, Any]:
    print(f"--- {model}", flush=True)
    if docker:
        compose_up(model, "auto")
    else:
        process = start_uvicorn(model)
    try:
        cold_start_s, health = wait_until_healthy()
        rss_idle = container_memory_mb() if docker else host_rss_mb(process)
        measure_sequential(3)  # let the first requests pay for any remaining lazy work

        peak = {"mb": rss_idle}
        stop = threading.Event()

        def sample() -> None:
            while not stop.wait(0.5):
                value = container_memory_mb() if docker else host_rss_mb(process)
                if value and (peak["mb"] is None or value > peak["mb"]):
                    peak["mb"] = value

        sampler = threading.Thread(target=sample, daemon=True)
        sampler.start()
        sequential = measure_sequential(requests_n)
        concurrent, rps = measure_concurrent(requests_n, workers=4)
        stop.set()
        sampler.join(timeout=2)

        result = {
            "model": model,
            "health": health,
            "cold_start_s": cold_start_s,
            "rss_idle_mb": rss_idle,
            "rss_load_mb": peak["mb"],
            "seq_p50_ms": percentile(sequential, 0.5),
            "seq_p95_ms": percentile(sequential, 0.95),
            "seq_mean_ms": round(statistics.mean(sequential), 1),
            "conc4_p50_ms": percentile(concurrent, 0.5),
            "conc4_p95_ms": percentile(concurrent, 0.95),
            "conc4_rps": rps,
            "requests": requests_n,
            "image_mb": image_size_mb() if docker else None,
            "faiss_rankings": rankings(),
            "examples": examples(),
        }
    finally:
        if docker:
            compose_down()
        else:
            process.terminate()
            process.wait(timeout=30)
    return result


def start_uvicorn(model: str) -> "subprocess.Popen[bytes]":
    env = {**os.environ, "SFR_API_MODEL": model, "SFR_API_INDEX_ROOT": "data/indexes_sfr2"}
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "sfr_api.main:app", "--factory", "--port", "8000"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def host_rss_mb(process: "subprocess.Popen[bytes]") -> float | None:
    out = run(["ps", "-o", "rss=", "-p", str(process.pid)], check=False)
    return round(int(out) / 1024, 1) if out.strip().isdigit() else None


def compare_backends(model: str, faiss_rankings: dict[str, list[Any]]) -> dict[str, Any]:
    """Same container, same index, NumPy scan instead of FAISS — must rank identically."""
    compose_up(model, "numpy")
    try:
        _, health = wait_until_healthy()
        numpy_rankings = rankings()
    finally:
        compose_down()
    mismatched_order, max_score_delta = [], 0.0
    for query, faiss_hits in faiss_rankings.items():
        numpy_hits = numpy_rankings[query]
        if [hit[0] for hit in faiss_hits] != [hit[0] for hit in numpy_hits]:
            mismatched_order.append(query)
        for (_, faiss_score), (_, numpy_score) in zip(faiss_hits, numpy_hits, strict=False):
            max_score_delta = max(max_score_delta, abs(faiss_score - numpy_score))
    return {
        "backend_checked": health["search_backend"],
        "queries": len(faiss_rankings),
        "identical_order": not mismatched_order,
        "mismatched_queries": mismatched_order,
        "max_score_delta": max_score_delta,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", default="frida,mpnet")
    parser.add_argument("--out", type=Path, default=Path("docs/sfr2_resources.json"))
    parser.add_argument("--requests", type=int, default=30)
    parser.add_argument("--no-docker", action="store_true")
    args = parser.parse_args()

    docker = not args.no_docker
    report: dict[str, Any] = {
        "measured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "host": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "docker": docker,
        },
        "models": [],
    }
    if docker:
        report["host"]["docker_info"] = run(
            ["docker", "info", "--format", "{{.MemTotal}} {{.NCPU}} {{.Architecture}}"]
        )

    for model in [name.strip() for name in args.models.split(",") if name.strip()]:
        result = bench_model(model, args.requests, docker)
        if docker:
            result["faiss_vs_numpy"] = compare_backends(model, result.pop("faiss_rankings"))
        else:
            result.pop("faiss_rankings")
        # The report shows examples from the model that actually ships.
        model_examples = result.pop("examples", [])
        if model == "frida" or "examples" not in report:
            report["examples"] = model_examples
        report["models"].append(result)
        print(json.dumps({k: v for k, v in result.items() if k != "health"}, ensure_ascii=False))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"→ {args.out}")


if __name__ == "__main__":
    main()
