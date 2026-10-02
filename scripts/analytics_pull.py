"""Read-only server export to developer machine with SHA-256 manifest.

pg_dump streams directly to Mac. Closed access archives and durable journal are
read via tar inside existing containers; no temporary server files/config changes.
Only explicit host/path arguments, validated before constructing SSH command.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from analytics import private_dir, write_private
from analytics_backup import compose, digest


def pull(host: str | None, remote_path: str, directory: Path) -> dict[str, Any]:
    if host is not None and not re.fullmatch(r"[a-zA-Z0-9_.-]+@[a-zA-Z0-9_.-]+", host):
        raise ValueError("expected user@host")
    if not re.fullmatch(r"/[a-zA-Z0-9_./ -]+", remote_path) or ".." in remote_path.split("/"):
        raise ValueError("expected absolute remote project directory")
    private_dir(directory)
    # Compose itself reads config/environment; these commands never mutate services.
    prefix = (
        f"cd {shlex.quote(remote_path)} && docker compose "
        "--env-file deploy/.env -f deploy/docker-compose.yml "
    )
    commands = {
        "analytics.dump": [
            "exec",
            "-T",
            "postgres",
            "sh",
            "-c",
            'export PGPASSWORD="$POSTGRES_PASSWORD"; exec pg_dump -U "$POSTGRES_USER" '
            '--format=custom --no-owner --no-acl --dbname="$POSTGRES_DB"',
        ],
        "analytics-journal.tar": [
            "exec",
            "-T",
            "api",
            "tar",
            "-C",
            "/analytics",
            "-cf",
            "-",
            "spool",
        ],
        "access-logs.tar": [
            "exec",
            "-T",
            "proxy",
            "sh",
            "-c",
            "cd /data && set --; "
            "for file in access* archive/access*; do "
            '[ ! -f "$file" ] || set -- "$@" "$file"; done; '
            '[ "$#" -gt 0 ] && exec tar -cf - "$@"',
        ],
    }
    files = []
    for name, arguments in commands.items():
        remote = prefix + shlex.join(arguments)
        invocation = (
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", host, remote]
            if host
            else [*compose(), *arguments]
        )
        path = directory / name
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            result = subprocess.run(
                invocation,
                stdout=stream,
                stderr=subprocess.PIPE,
                check=False,
                timeout=600,
            )
            stream.flush()
            os.fsync(stream.fileno())
        if result.returncode:
            raise RuntimeError("read_only_remote_export_failed")
        files.append({"path": name, "bytes": path.stat().st_size, "sha256": digest(path)})
    manifest: dict[str, Any] = {
        "version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "files": files,
        "consistency": "DB pg_dump transaction; active logs/journal may advance while streaming. "
        "This is an observed copy, not a common cross-file snapshot; "
        "rerun after replay for completeness.",
    }
    write_private(directory / "manifest.json", json.dumps(manifest, indent=2))
    return manifest


def main() -> int:
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--host")
    source.add_argument("--local", action="store_true", help="read selected local Compose project")
    parser.add_argument("--remote-path", default="/home/deploy/search-for-research")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = pull(args.host, args.remote_path, args.out)
        print(json.dumps({"ok": True, "files": len(manifest["files"]), "out": str(args.out)}))
    except Exception as exc:
        print(json.dumps({"ok": False, "error_class": type(exc).__name__}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
