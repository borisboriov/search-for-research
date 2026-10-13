"""Export only non-contact aggregates from a sealed component replay."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


def load(path: Path) -> Any:
    return json.loads(path.read_text())


def export(root: Path, output: Path) -> None:
    replay = load(root / "replay.json")
    evaluation = load(root / "evaluation.json")
    if (
        evaluation["replay_sha256"]
        != hashlib.sha256((root / "replay.json").read_bytes()).hexdigest()
    ):
        raise ValueError("Replay changed after evaluation")
    tools = []
    for tool in sorted({r["tool"] for r in replay["rows"]}):
        rows = [r for r in replay["rows"] if r["tool"] == tool]
        ev = [r for r in evaluation["rows"] if r["tool"] == tool]
        tools.append(
            {
                "tool": tool,
                "source_count": len(rows),
                "errors": sum(r["status"] != "ok" for r in rows),
                "candidate_profile_pairs": sum(r["candidate_count"] for r in ev),
                "human8_recovered": sum(r["known_human8_recovered"] for r in ev),
                "wall_seconds_including_first_import": sum(r["seconds"] for r in rows),
                "cpu_seconds_including_first_import": sum(r["cpu_seconds"] for r in rows),
            }
        )
    summary = {
        "manifest_sha256": replay["manifest_sha256"],
        "replay_sha256": evaluation["replay_sha256"],
        "evaluation_sha256": hashlib.sha256((root / "evaluation.json").read_bytes()).hexdigest(),
        "source_formats": dict(
            Counter(s["source_kind"] for s in load(root / "manifest.json")["sources"])
        ),
        "tools": tools,
        "profiles": evaluation["rows"],
        "resources": {k: v for k, v in replay.items() if k not in ("rows", "manifest_sha256")},
        "attribution_scope": (
            "Human8 overlap is reference recovery; automatic acceptance 0; "
            "unmatched is not false-positive gold"
        ),
    }
    with output.open("x") as file:
        json.dump(summary, file, ensure_ascii=False, indent=2)
        file.write("\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    export(args.root, args.output)
