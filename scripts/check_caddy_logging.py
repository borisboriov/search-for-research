"""Actual Caddy regression: preserve URI paths, exclude query/header secrets.

Uses an isolated container of the project's existing proxy image, no host ports,
no external network, and a synthetic loopback backend. Existing services/data are
not touched. The stopped container and private test log volume remain for review.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
MARKER = "SYNTHETIC_CADDY_SECRET_MARKER"


def docker(*arguments: str, check: bool = True) -> str:
    result = subprocess.run(
        ["docker", *arguments], capture_output=True, text=True, timeout=60, check=False
    )
    if check and result.returncode:
        raise RuntimeError("isolated_caddy_command_failed")
    return result.stdout + (result.stderr if arguments and arguments[0] == "logs" else "")


def check_logging(image: str) -> dict[str, Any]:
    name = "sfr-caddy-log-test-" + uuid4().hex[:12]
    volume = name + "-logs"
    config = (
        (ROOT / "deploy/proxy/Caddyfile")
        .read_text()
        .replace("reverse_proxy web:3000 {", "reverse_proxy 127.0.0.1:8082 {")
    )
    config += (
        f'\nhttp://localhost:8082 {{\n header Set-Cookie "{MARKER}"\n respond "synthetic" 200\n}}\n'
    )
    with tempfile.TemporaryDirectory(prefix="sfr-caddy-log-test-") as directory:
        fixture = Path(directory) / "Caddyfile"
        fixture.write_text(config)
        fixture.chmod(0o644)  # Public test config, readable by image's caddy uid.
        started = False
        try:
            docker(
                "run",
                "-d",
                "--name",
                name,
                "--network",
                "none",
                "--mount",
                f"type=volume,src={volume},dst=/data",
                "--mount",
                f"type=bind,src={fixture},dst=/etc/caddy/Caddyfile,readonly",
                "-e",
                "SITE_ADDRESS=http://localhost:8080",
                image,
            )
            started = True
            for _ in range(40):
                if docker(
                    "exec", name, "wget", "-qO-", "http://127.0.0.1:2019/config/", check=False
                ):
                    break
                time.sleep(0.25)
            else:
                raise RuntimeError("isolated_caddy_not_ready")
            for path in ("/api/match", "/results", "/supervisor/A123"):
                docker(
                    "exec",
                    name,
                    "wget",
                    "-qO-",
                    "--header",
                    f"Authorization: Bearer {MARKER}",
                    "--header",
                    f"Cookie: synthetic={MARKER}",
                    "--header",
                    f"X-Revalidate-Secret: {MARKER}",
                    "--header",
                    f"X-Unlisted-Secret: {MARKER}",
                    f"http://localhost:8080{path}?arbitrary_secret={MARKER}",
                )
            raw = docker("exec", name, "cat", "/data/access.log")
            records = [json.loads(line) for line in raw.splitlines()]
            runtime = docker("logs", name)
            paths = [record["request"]["uri"] for record in records]
            result = {
                "passed": True,
                "rows": len(records),
                "paths_preserved": paths == ["/api/match", "/results", "/supervisor/A123"],
                "query_secrets_excluded": MARKER not in raw and MARKER not in runtime,
                "headers_excluded": all(
                    "headers" not in row["request"] and "resp_headers" not in row for row in records
                ),
                "container": name,
                "retained_volume": volume,
            }
            result["passed"] = all(
                result[key]
                for key in ("paths_preserved", "query_secrets_excluded", "headers_excluded")
            )
            return result
        finally:
            if started:
                docker("stop", name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--image", default=os.environ.get("SFR_CADDY_IMAGE", "sfr-deploy-proxy:latest")
    )
    args = parser.parse_args()
    try:
        result = check_logging(args.image)
        print(json.dumps(result))
        return 0 if result["passed"] else 1
    except Exception as exc:
        print(json.dumps({"passed": False, "error_class": type(exc).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
