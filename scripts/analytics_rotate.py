"""Operator-invoked access log archival with no history deletion.

Briefly restarts ONLY the selected project's proxy to close the renamed inode.
Prepared for operator use after deployment; never called automatically by report.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime

from analytics_backup import compose


def rotate(stamp: str) -> None:
    # Rename is atomic on the same volume. Caddy keeps writing to the retained
    # old inode until restart gracefully closes it. Compress only AFTER restart.
    path = f"/data/archive/access-{stamp}.log"
    result = subprocess.run(
        [
            *compose(),
            "exec",
            "-T",
            "proxy",
            "sh",
            "-c",
            "mkdir -p /data/archive && chmod 700 /data/archive && "
            'test ! -e "$1" && mv /data/access.log "$1"',
            "operator",
            path,
        ],
        capture_output=True,
        check=False,
        timeout=120,
    )
    if result.returncode:
        raise RuntimeError("archive_rename_failed")
    result = subprocess.run(
        [*compose(), "restart", "proxy"], capture_output=True, check=False, timeout=120
    )
    if result.returncode:
        raise RuntimeError("proxy_restart_failed_archive_retained")
    result = subprocess.run(
        [*compose(), "exec", "-T", "proxy", "gzip", path], capture_output=True, check=False
    )
    if result.returncode:
        raise RuntimeError("gzip_failed_uncompressed_archive_retained")


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        rotate(datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ"))
        print(json.dumps({"ok": True, "archive_retained": True}))
    except Exception as exc:
        print(json.dumps({"ok": False, "error_class": type(exc).__name__}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
