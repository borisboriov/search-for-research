"""Synthetic persistence rehearsal against an explicitly isolated local Compose stack.

Never accepts a remote host. Uses only its own project, no volume removal or data cleanup.
All output is safe counters/IDs/check results; raw logs and contexts stay in memory.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:18080")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    project = os.environ.get("SFR_COMPOSE_PROJECT", "")
    if not project.startswith("sfr-analytics-") or urlparse(args.url).hostname not in {
        "localhost",
        "127.0.0.1",
    }:
        parser.error("requires a dedicated sfr-analytics-* project and loopback URL")
    compose = [
        "docker",
        "compose",
        "-f",
        "deploy/docker-compose.yml",
        "-f",
        "deploy/docker-compose.local.yml",
        "--project-name",
        project,
    ]
    if env_file := os.environ.get("SFR_COMPOSE_ENV_FILE"):
        compose[2:2] = ["--env-file", env_file]
    if override := os.environ.get("SFR_COMPOSE_OVERRIDE"):
        compose.extend(["-f", override])
    proofs: dict[str, Any] = {
        "platform": "local Docker Linux",
        "synthetic": True,
        "started_at": datetime.now(UTC).isoformat(),
    }

    def command(parts: list[str], *, timeout: int = 300) -> str:
        result = subprocess.run(
            [*compose, *parts], capture_output=True, text=True, timeout=timeout, check=False
        )
        if result.returncode:
            # Neither driver errors nor command output may expose connection settings/logs.
            raise RuntimeError(f"isolated command failed ({parts[0]}, exit {result.returncode})")
        return result.stdout

    def counts() -> dict[str, Any]:
        sql = """SELECT json_build_object(
        'searches',(SELECT count(*) FROM analytics_searches),
        'events',(SELECT count(*) FROM analytics_events),
        'context',(SELECT count(*) FROM analytics_context),
        'event_context',(SELECT count(*) FROM analytics_event_context),
        'migration',(SELECT version_num FROM analytics_alembic_version));"""
        result: dict[str, Any] = json.loads(
            command(
                [
                    "exec",
                    "-T",
                    "postgres",
                    "psql",
                    "-U",
                    "sfr_migrator",
                    "-d",
                    "sfr_analytics",
                    "-Atc",
                    sql,
                ]
            )
        )
        return result

    def wait_counts(expected: dict[str, Any], *, exact: bool = True) -> dict[str, Any]:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            current = counts()
            if all(current[k] == v if exact else current[k] >= v for k, v in expected.items()):
                return current
            time.sleep(0.3)
        raise AssertionError("database counters did not converge")

    with httpx.Client(base_url=args.url, timeout=30) as client:
        visit = str(uuid4())
        search = str(uuid4())
        request = str(uuid4())
        seq = 0

        def event(name: str, *, sid: str | None = search, **data: Any) -> dict[str, Any]:
            nonlocal seq
            seq += 1
            return {
                "schema_version": 1,
                "event_id": str(uuid4()),
                "visit_id": visit,
                "search_id": sid,
                "request_id": request,
                "name": name,
                "client_at": "2036-01-01T00:00:00Z",
                "client_seq": seq,
                "page": "profile" if name.startswith(("profile", "letter")) else "results",
                "data": data,
            }

        headers = {
            "X-SFR-Visit-ID": visit,
            "X-SFR-Search-ID": search,
            "X-Request-ID": request,
            "User-Agent": "sfr-rehearsal-persistence",
        }
        response = client.post(
            "/api/match",
            json={"query": "  машинное обучение для анализа текстов  ", "k": 10},
            headers=headers,
        )
        assert response.status_code == 200, "real FRIDA match failed"
        payload = response.json()
        author = payload["results"][0]["author_id"]
        rows = [
            event("visit_started", sid=None),
            event("search_attempt"),
            event("results_shown", confidence=payload["confidence"], elapsed_ms=123),
            event("profile_opened", author_id=author, position=1),
            event("letter_copy_success", author_id=author),
        ]
        accepted = client.post(
            "/api/events", json={"events": list(reversed(rows))}, headers=headers
        )
        assert accepted.status_code == 200, "durable event receiver failed"
        assert set(accepted.json()["accepted"]) == {e["event_id"] for e in rows}
        before = counts()
        # Database replay might already include rows; compare by IDs rather than race on counter.
        ids = ",".join("'" + e["event_id"] + "'" for e in rows)
        sql = f"SELECT count(*) FROM analytics_events WHERE event_id IN ({ids});"
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if int(
                command(
                    [
                        "exec",
                        "-T",
                        "postgres",
                        "psql",
                        "-U",
                        "sfr_migrator",
                        "-d",
                        "sfr_analytics",
                        "-Atc",
                        sql,
                    ]
                )
            ) == len(rows):
                break
            time.sleep(0.3)
        else:
            raise AssertionError("event replay timeout")
        before = counts()
        for _ in range(2):
            assert (
                client.post("/api/events", json={"events": rows}, headers=headers).status_code
                == 200
            )
        time.sleep(3)
        assert counts() == before, "duplicate events inflated persisted data"
        proofs["duplicate_and_late_delivery"] = {
            "passed": True,
            "events": len(rows),
            "wrong_clock_year": 2036,
        }
        # Fully synthetic markers are never printed; this checks header/query leak exclusion.
        marker = "REHEARSAL_SECRET_MARKER_" + uuid4().hex
        secret_headers = {
            **headers,
            "Authorization": "Bearer " + marker,
            "Cookie": "key=" + marker,
            "X-Revalidate-Secret": marker,
            "X-Unknown-Secret": marker,
            "X-Forwarded-For": "203.0.113.90",
            "Referer": f"https://example.test/path?token={marker}",
        }
        probe = event("address_copy_failed", author_id=author)
        assert (
            client.post(
                "/api/events?api_key=" + marker, json={"events": [probe]}, headers=secret_headers
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/api/events", json={"events": [{**probe, "secret": marker}]}, headers=headers
            ).status_code
            == 422
        )
        assert client.post("/api/events", content=b"x" * 17000, headers=headers).status_code == 413
        time.sleep(3)
        access = command(["exec", "-T", "proxy", "cat", "/data/access.log"])
        assert marker not in access, "Caddy secret leak detected"
        context_sql = (
            "SELECT row_to_json(t) FROM analytics_event_context t WHERE event_id='"
            + probe["event_id"]
            + "';"
        )
        context = command(
            [
                "exec",
                "-T",
                "postgres",
                "psql",
                "-U",
                "sfr_migrator",
                "-d",
                "sfr_analytics",
                "-Atc",
                context_sql,
            ]
        )
        assert marker not in context and "203.0.113.90" not in context, "private context leak/spoof"
        proofs["secrets_and_body_limits"] = True
        snapshot = counts()
        command(["up", "-d", "--force-recreate", "postgres", "api", "web"])
        wait_counts(snapshot)
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            try:
                if client.get("/").status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(1)
        else:
            raise AssertionError("receiver did not restart")
        proofs["force_recreate"] = {"passed": True, "retained": snapshot}
        command(["stop", "postgres"])
        outage_event = event("letter_copy_failed", author_id=author)
        outage = client.post("/api/events", json={"events": [outage_event]}, headers=headers)
        assert outage.status_code == 200, "outage durable buffer did not acknowledge"
        t = time.monotonic()
        failed_db_search = client.post(
            "/api/match",
            json={"query": "история России", "k": 10},
            headers={**headers, "X-SFR-Search-ID": str(uuid4()), "X-Request-ID": str(uuid4())},
        )
        assert failed_db_search.status_code == 200, "analytics outage blocked search"
        proofs["search_during_db_outage_ms"] = round((time.monotonic() - t) * 1000, 2)
        # PostgreSQL already exists but is stopped; --no-deps keeps it stopped during restart.
        command(["up", "-d", "--no-deps", "--force-recreate", "api", "web"])
        command(["start", "postgres"])
        final = wait_counts(
            {"events": snapshot["events"] + 1, "searches": snapshot["searches"] + 1}
        )
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            try:
                if client.get("/").status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(1)
        else:
            raise AssertionError("restart recovery did not become ready")
        # --no-deps lets Next start while FRIDA is still loading. A successful
        # fallback landing is not proof that ISR catalogue data can be rebuilt.
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            try:
                command(["exec", "-T", "api", "curl", "-sf", "http://127.0.0.1:8000/api/health"])
                break
            except RuntimeError:
                time.sleep(1)
        else:
            raise AssertionError("API did not recover before ISR revalidation")
        revalidation = client.post(
            "/api/revalidate", headers={"x-revalidate-secret": os.environ["REVALIDATE_SECRET"]}
        )
        assert revalidation.status_code == 200, "local ISR revalidation failed"
        assert (
            client.post("/api/events", json={"events": [outage_event]}, headers=headers).status_code
            == 200
        )
        time.sleep(3)
        assert counts() == final, "outage replay duplicated data"
        proofs["outage_restart_replay"] = {"passed": True, "retained": final}
    proofs["finished_at"] = datetime.now(UTC).isoformat()
    args.out.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    args.out.write_text(json.dumps(proofs, indent=2))
    args.out.chmod(0o600)
    print(json.dumps({"passed": True, "proofs": sorted(proofs)}))


if __name__ == "__main__":
    main()
