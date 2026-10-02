"""Private logical PostgreSQL backup and verification in a NEW test database.

Docker Compose connection stays inside the selected project; no published PG port.
A verify run creates a uniquely named database and intentionally keeps it for audit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from analytics import private_dir, write_private


def compose() -> list[str]:
    command = ["docker", "compose"]
    env_file = os.environ.get("SFR_COMPOSE_ENV_FILE", "deploy/.env")
    if Path(env_file).is_file():
        command.extend(["--env-file", env_file])
    elif "SFR_COMPOSE_ENV_FILE" in os.environ:
        raise ValueError("explicit Compose env file does not exist")
    if project := os.environ.get("SFR_COMPOSE_PROJECT"):
        command.extend(["-p", project])
    command.extend(["-f", "deploy/docker-compose.yml"])
    if local := os.environ.get("SFR_COMPOSE_OVERRIDE"):
        command.extend(["-f", local])
    return command


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def command(script: str, *args: str, source: Any = None, destination: Any = None) -> bytes:
    # Scripts are internal literals; user arguments are positional argv, never shell fragments.
    result = subprocess.run(
        [*compose(), "exec", "-T", "postgres", "sh", "-c", script, "operator", *args],
        stdin=source,
        stdout=destination or subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=300,
    )
    if result.returncode:
        # PostgreSQL error output may contain private parameters. Keep it off terminal/PR.
        raise RuntimeError("postgres_operator_command_failed")
    return result.stdout or b""


def backup(directory: Path) -> dict[str, Any]:
    private_dir(directory)
    path = directory / "analytics.dump"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        command(
            'export PGPASSWORD="$POSTGRES_PASSWORD"; exec pg_dump -U "$POSTGRES_USER" '
            '--format=custom --no-owner --no-acl --dbname="$POSTGRES_DB"',
            destination=stream,
        )
        stream.flush()
        os.fsync(stream.fileno())
    manifest = {
        "version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "method": "pg_dump custom; transaction-consistent logical snapshot",
        "files": [{"path": path.name, "bytes": path.stat().st_size, "sha256": digest(path)}],
    }
    write_private(directory / "manifest.json", json.dumps(manifest, indent=2))
    return manifest


def verify(directory: Path, database: str) -> dict[str, Any]:
    if not re.fullmatch(r"sfr_restore_[a-z0-9_]{1,40}", database):
        raise ValueError(
            "test database name must begin sfr_restore_ with lowercase alphanumeric suffix"
        )
    manifest = json.loads((directory / "manifest.json").read_text())
    path = directory / "analytics.dump"
    if manifest["version"] != 1 or digest(path) != manifest["files"][0]["sha256"]:
        raise ValueError("backup checksum mismatch")
    # createdb must fail if the name already exists. Never --clean/drop/reuse a DB.
    command(
        'export PGPASSWORD="$POSTGRES_PASSWORD"; exec createdb -U "$POSTGRES_USER" "$1"', database
    )
    with path.open("rb") as stream:
        command(
            'export PGPASSWORD="$POSTGRES_PASSWORD"; exec pg_restore -U "$POSTGRES_USER" '
            '--exit-on-error --no-owner --no-acl --dbname="$1"',
            database,
            source=stream,
        )
    # Canonical aggregate and row hashes contain no raw fields. Repeated restoration
    # from one dump can compare these fingerprints, including all sensitive context.
    sql = """SELECT json_build_object(
    'migration',(SELECT version_num FROM analytics_alembic_version),
    'searches',(SELECT count(*) FROM analytics_searches),
    'events',(SELECT count(*) FROM analytics_events),
    'context',(SELECT count(*) FROM analytics_context),
    'event_context',(SELECT count(*) FROM analytics_event_context),
    'search_sha',(SELECT md5(coalesce(string_agg(row_to_json(t)::text,
    E'\\n' ORDER BY search_id),'')) FROM analytics_searches t),
    'event_sha',(SELECT md5(coalesce(string_agg(row_to_json(t)::text,
    E'\\n' ORDER BY event_id),'')) FROM analytics_events t),
    'context_sha',(SELECT md5(coalesce(string_agg(row_to_json(t)::text,
    E'\\n' ORDER BY search_id),'')) FROM analytics_context t),
    'event_context_sha',(SELECT md5(coalesce(string_agg(row_to_json(t)::text,
    E'\\n' ORDER BY event_id),'')) FROM analytics_event_context t));"""
    output = command(
        'export PGPASSWORD="$POSTGRES_PASSWORD"; exec psql -U "$POSTGRES_USER" '
        '-d "$1" -v ON_ERROR_STOP=1 -Atc "$2"',
        database,
        sql,
    )
    result = {
        "verified_at": datetime.now(UTC).isoformat(),
        "database": database,
        "restored": json.loads(output),
        "dump_sha256": digest(path),
    }
    write_private(directory / f"restore-{database}.json", json.dumps(result, indent=2))
    return result


def main() -> int:
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["backup", "verify"])
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--database", help="NEW test database; retained after verification")
    args = parser.parse_args()
    try:
        if args.command == "backup":
            result = backup(args.directory)
            print(json.dumps({"ok": True, "files": len(result["files"])}))
        elif args.database:
            result = verify(args.directory, args.database)
            print(
                json.dumps(
                    {"ok": True, "database": result["database"], "restored": result["restored"]}
                )
            )
        else:
            raise ValueError("--database is required for verify")
    except Exception as exc:
        print(json.dumps({"ok": False, "error_class": type(exc).__name__}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
