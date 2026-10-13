"""Bounded read-only SFR storage census; contents, credentials and links are not read.

Run from the repository. Output is a private catalogue, never a raw-file listing.
"""

import argparse
import json
import os
import stat
import subprocess
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sfr_enrichment.common import private_root, write_new
from sfr_enrichment.config import repository_root


def category(path: Path) -> str:
    parts = path.parts
    name = path.name
    if ".venv" in parts or "node_modules" in parts:
        return "regenerable_dependencies"
    if any("cache" in p.lower() for p in parts):
        return "regenerable_cache"
    if name.endswith("-session-event.json"):
        return "pi_full_event_snapshots"
    if "human-v3" in parts or "human-v4" in parts or "paired-human" in parts:
        return "human_records_and_packets"
    if name.startswith(("body-", "decoded-", "text-", "source-")) or name.endswith(".pdf"):
        return "source_bodies_and_derivations"
    if name.endswith((".log", ".jsonl")):
        return "stream_logs"
    if "runs" in parts and name.endswith(".json"):
        return "model_outputs_and_run_controls"
    return "other_code_results_seals_and_evidence"


def census(root: Path, seen: set[tuple[int, int]]) -> dict[str, Any]:
    row: dict[str, Any] = {
        "path": str(root),
        "directories": 0,
        "unique_files": 0,
        "logical_bytes": 0,
        "allocated_bytes": 0,
        "symlinks_not_followed": 0,
        "hardlink_aliases": 0,
        "errors": [],
        "categories": defaultdict(lambda: {"files": 0, "logical_bytes": 0, "allocated_bytes": 0}),
    }

    def failure(error: OSError) -> None:
        row["errors"].append({"path": error.filename, "kind": type(error).__name__})

    if not root.exists():
        row["errors"].append({"path": str(root), "kind": "missing"})
        return row
    entries = []
    if root.is_file() or root.is_symlink():
        entries.append(root)
    else:
        for folder, dirs, files in os.walk(root, followlinks=False, onerror=failure):
            row["directories"] += 1
            # Do not inspect credential locations even as census metadata.
            dirs[:] = [d for d in dirs if d not in {".aws", ".ssh", ".gnupg"}]
            entries.extend(
                Path(folder) / name
                for name in files
                if name != ".env" and not name.startswith(".env.")
            )
            for name in list(dirs):
                p = Path(folder) / name
                if p.is_symlink():
                    entries.append(p)
                    dirs.remove(name)
    for p in entries:
        try:
            info = p.lstat()
        except OSError as error:
            failure(error)
            continue
        if stat.S_ISLNK(info.st_mode):
            row["symlinks_not_followed"] += 1
            continue
        if not stat.S_ISREG(info.st_mode):
            continue
        key = (info.st_dev, info.st_ino)
        if key in seen:
            row["hardlink_aliases"] += 1
            continue
        seen.add(key)
        allocated = info.st_blocks * 512
        row["unique_files"] += 1
        row["logical_bytes"] += info.st_size
        row["allocated_bytes"] += allocated
        group = row["categories"][category(p)]
        group["files"] += 1
        group["logical_bytes"] += info.st_size
        group["allocated_bytes"] += allocated
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiments", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    repo = repository_root()
    roots = sorted(
        p for p in args.experiments.iterdir() if p.is_dir() and p.name.startswith("enrichment")
    )
    roots = [p for p in roots if p.resolve() != args.out.resolve().parent]
    experiment_count = len(roots)
    worktrees = subprocess.check_output(
        ["git", "worktree", "list", "--porcelain"], cwd=repo, text=True
    )
    roots += [Path(line[9:]) for line in worktrees.splitlines() if line.startswith("worktree ")]
    top_errors = []
    for folder in [
        Path("/private/tmp"),
        Path(os.environ.get("TMPDIR", "/private/tmp")),
        Path.home(),
        Path.home() / "Downloads",
    ]:
        try:
            for p in folder.iterdir():
                if (
                    p.name.startswith(("sfr-", "sfr189-", "enrichment", "SFR"))
                    and p not in roots
                    and p.resolve() != args.out.resolve().parent
                ):
                    roots.append(p)
        except OSError as error:
            top_errors.append(
                {"path": str(folder), "kind": type(error).__name__, "scope": "top_level_only"}
            )
    seen: set[tuple[int, int]] = set()
    rows = [census(root, seen) for root in dict.fromkeys(roots)]
    catalogue = {
        "schema": "enrichment-storage-catalogue-v1",
        "at": datetime.now(UTC).isoformat(),
        "boundaries": (
            "known enrichment experiment directories, registered SFR worktrees, "
            "matching top-level tmp/home/Downloads entries only; no recursive home survey"
        ),
        "method": (
            "lstat regular files; symlinks not followed; unique dev/inode across roots; "
            "allocated=st_blocks*512; APFS shared clone extents unknown"
        ),
        "experiment_directories": experiment_count,
        "roots": rows,
        "top_level_errors": top_errors,
        "self_generated_catalogue_root_excluded": str(args.out.resolve().parent),
        "key_results": {
            "baseline": str(args.experiments / "enrichment-flexible10-20261010"),
            "real_human_record": str(
                args.experiments
                / "enrichment-human-baseline-contacts-20261011"
                / "human-v3/records/boris-baseline-contacts.json"
            ),
            "final_live3": str(args.experiments / "enrichment-sol-assisted-live3-20261011"),
        },
        "retention": (
            "All existing roots remain references, never moved/deleted/rewritten by this census. "
            "Private sources/raw/human decisions/seals are evidence; deps/cache regenerable; "
            "archiving currently means a logical catalogue, without compression. "
            "Physical consolidation/deletion requires a separately verified plan and authorization."
        ),
    }
    private_root(args.out.parent)
    write_new(args.out, catalogue)
    print(
        json.dumps(
            {
                "catalogue": str(args.out),
                "experiment_directories": experiment_count,
                "roots": len(rows),
                "unique_files": sum(r["unique_files"] for r in rows),
                "logical_bytes": sum(r["logical_bytes"] for r in rows),
                "allocated_bytes": sum(r["allocated_bytes"] for r in rows),
                "top_level_errors": top_errors,
            }
        )
    )


if __name__ == "__main__":
    main()
