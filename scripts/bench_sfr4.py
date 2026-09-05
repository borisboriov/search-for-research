"""Перемер SFR-4 на боевой компоновке (SPEC_SFR4 §3) + проверки защиты (§2).

Меряет против стека `make deploy-local` (proxy на localhost:8080):

- латентность /match p50/p95 при 1 и 4 параллельных и шторм из 20 параллельных
  запросов — мимо прокси, изнутри compose-сети (docker compose exec api):
  через прокси мерить нельзя, лимитер 10/мин отдаст 429 — и это правильно;
- rate limiting через прокси: /api/match душится после 10/мин, страницы —
  после 120/мин, Googlebot по UA лимиты обходит;
- TTFB страницы НР холодный/из ISR-кэша, кэш /match (повтор -> took_ms 0);
- RAM контейнеров в покое и под штормом, холодный старт api, недоступность
  API снаружи compose.

    uv run python scripts/bench_sfr4.py --out docs/sfr4_bench.json
"""

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx

PROXY = "http://localhost:8080"

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

# Скрипт, выполняемый внутри контейнера api: шлёт запросы на 127.0.0.1:8000
# заданным числом потоков. stdlib-only — httpx в образ не входит.
IN_CONTAINER_LOAD = r"""
import json, statistics, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

queries, workers = json.loads(sys.argv[1]), int(sys.argv[2])

def one(i):
    # уникальный текст на секцию и запрос: иначе секции читают кэш друг друга
    q = queries[i % len(queries)] + f" секция {workers} вариант {i}"
    body = json.dumps({"query": q, "k": 10}).encode()
    req = urllib.request.Request("http://127.0.0.1:8000/api/match", data=body,
                                 headers={"Content-Type": "application/json"})
    t = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            resp.read()
            return (time.perf_counter() - t) * 1000, resp.status
    except urllib.error.HTTPError as e:
        return (time.perf_counter() - t) * 1000, e.code
    except OSError:
        return (time.perf_counter() - t) * 1000, 0

n = int(sys.argv[3])
t0 = time.perf_counter()
with ThreadPoolExecutor(max_workers=workers) as pool:
    out = list(pool.map(one, range(n)))
wall = time.perf_counter() - t0
lat = sorted(x[0] for x in out if x[1] == 200)
codes = {}
for _, c in out:
    codes[str(c)] = codes.get(str(c), 0) + 1
print(json.dumps({
    "n": n, "workers": workers, "wall_s": round(wall, 1), "codes": codes,
    "p50_ms": round(statistics.median(lat), 1) if lat else None,
    "p95_ms": round(lat[min(len(lat) - 1, round(0.95 * (len(lat) - 1)))], 1) if lat else None,
    "max_ms": round(max(lat), 1) if lat else None,
}))
"""


def sh(cmd: list[str], check: bool = True) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} → {result.returncode}\n{result.stderr}")
    return result.stdout.strip()


def in_container_load(workers: int, n: int) -> dict[str, Any]:
    # docker exec, а не compose exec: compose требует env-переменных для
    # интерполяции yaml, а bench их знать не обязан
    out = sh(
        [
            "docker",
            "exec",
            "-i",
            "sfr-api",
            "python",
            "-c",
            IN_CONTAINER_LOAD,
            json.dumps(QUERIES, ensure_ascii=False),
            str(workers),
            str(n),
        ]
    )
    return json.loads(out.splitlines()[-1])


def containers_memory_mb() -> dict[str, float]:
    out = sh(["docker", "stats", "--no-stream", "--format", "{{.Name}} {{.MemUsage}}"], check=False)
    result: dict[str, float] = {}
    for line in out.splitlines():
        name, usage = line.split(" ", 1)
        if not name.startswith("sfr-"):
            continue
        used = usage.split("/")[0].strip().upper()
        number = float("".join(ch for ch in used if ch.isdigit() or ch == "."))
        if used.endswith("GIB"):
            number *= 1024
        elif used.endswith("KIB"):
            number /= 1024
        result[name] = round(number, 1)
    return result


def rate_limit_match() -> dict[str, Any]:
    """12 быстрых POST /api/match через прокси: после 10-го должен пойти 429."""
    codes: list[int] = []
    with httpx.Client(timeout=60) as client:
        for i in range(12):
            response = client.post(
                f"{PROXY}/api/match", json={"query": f"лимитер проверка {i}", "k": 10}
            )
            codes.append(response.status_code)
    return {
        "codes": codes,
        "got_429": 429 in codes,
        "ok_before_429": codes.index(429) if 429 in codes else len(codes),
    }


def rate_limit_pages_and_bots() -> dict[str, Any]:
    """125 GET обычным UA (должны упереться в 120/мин), затем 10 GET Googlebot —
    все 200, хотя лимит для этого IP уже исчерпан."""
    human: list[int] = []
    with httpx.Client(timeout=30) as client:
        for _ in range(125):
            human.append(client.get(f"{PROXY}/robots.txt").status_code)
        bot_headers = {
            "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
        }
        bot = [
            client.get(f"{PROXY}/robots.txt", headers=bot_headers).status_code for _ in range(10)
        ]
    return {
        "human_total": len(human),
        "human_429": human.count(429),
        "bot_codes": sorted(set(bot)),
        "bot_passed": all(c == 200 for c in bot),
    }


def ttfb(url: str, client: httpx.Client) -> float:
    started = time.perf_counter()
    with client.stream("GET", url) as response:
        next(response.iter_bytes(), b"")  # первый чанк тела и есть TTFB
        elapsed = (time.perf_counter() - started) * 1000
    return round(elapsed, 1)


def api_closed_from_host() -> bool:
    # Порт 8000 на хосте может слушать локальный make api — смотрим не на
    # сокет, а на то, публикует ли что-нибудь контейнер (docker port —
    # без compose-интерполяции, ей нужны env-переменные).
    return sh(["docker", "port", "sfr-api"], check=False) == ""


def cold_start_s() -> float:
    sh(["docker", "restart", "sfr-api"])
    started = time.perf_counter()
    deadline = started + 600
    while time.perf_counter() < deadline:
        health = sh(
            [
                "docker",
                "inspect",
                "--format",
                "{{if .State.Health}}{{.State.Health.Status}}{{end}}",
                "sfr-api",
            ],
            check=False,
        )
        if health == "healthy":
            return round(time.perf_counter() - started, 1)
        time.sleep(1)
    raise TimeoutError("api не стал healthy за 10 минут после рестарта")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("docs/sfr4_bench.json"))
    args = parser.parse_args()

    report: dict[str, Any] = {
        "measured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "stack": "make deploy-local (proxy localhost:8080)",
    }

    report["api_port_8000_closed_from_host"] = api_closed_from_host()
    report["rss_idle_mb"] = containers_memory_mb()

    with httpx.Client(timeout=60) as client:
        # прогрев: страница НР ещё не в ISR-кэше
        supervisor = f"{PROXY}/supervisor/A5050048876"
        report["supervisor_ttfb_cold_ms"] = ttfb(supervisor, client)
        report["supervisor_ttfb_cached_ms"] = min(ttfb(supervisor, client) for _ in range(3))
        report["landing_ttfb_ms"] = ttfb(f"{PROXY}/", client)

    print("латентность /match: 1 воркер...", flush=True)
    report["match_seq"] = in_container_load(workers=1, n=16)
    print("латентность /match: 4 воркера...", flush=True)
    report["match_conc4"] = in_container_load(workers=4, n=20)
    print("шторм: 20 параллельных...", flush=True)
    rss_before = containers_memory_mb()
    report["match_burst20"] = in_container_load(workers=20, n=20)
    report["rss_after_burst_mb"] = containers_memory_mb()
    report["rss_before_burst_mb"] = rss_before

    # кэш: одинаковый запрос дважды изнутри сети
    cache_probe = json.loads(
        sh(
            [
                "docker",
                "exec",
                "-i",
                "sfr-api",
                "python",
                "-c",
                r"""
import json, urllib.request
def post():
    body = json.dumps({"query": "кэш проверка повторного запроса", "k": 10}).encode()
    req = urllib.request.Request("http://127.0.0.1:8000/api/match", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.load(resp)
first, second = post(), post()
with urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=10) as resp:
    health = json.load(resp)
print(json.dumps({"first_took_ms": first["took_ms"], "second_took_ms": second["took_ms"],
                  "cache_hits": health["cache_hits"], "cache_hit_rate": health["cache_hit_rate"]}))
""",
            ]
        )
    )
    report["match_cache"] = cache_probe

    print("rate limiting через прокси...", flush=True)
    report["rate_limit_match"] = rate_limit_match()
    report["rate_limit_pages_bots"] = rate_limit_pages_and_bots()

    print("холодный старт api...", flush=True)
    report["api_cold_start_s"] = cold_start_s()

    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"→ {args.out}")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
