"""One entry point; live acquisition requires explicit runner --live authorization."""

import argparse
import json
import sys
from pathlib import Path

from sfr_enrichment import review, runner


def main() -> None:
    if len(sys.argv) == 2 and sys.argv[1] in ("--help", "-h"):
        parser = argparse.ArgumentParser(
            description="Sol-assisted enrichment: explicit agent search, code, native Sol, human",
            epilog="Commands: prepare, dry-run, status, run, saved, human, archive-check. "
            "Search is external; run requires separate --live authorization. "
            "Use COMMAND --help for its options. Historical Pi/GLM runners are excluded.",
        )
        parser.print_help()
    elif len(sys.argv) > 1 and sys.argv[1] == "archive-check":
        parser = argparse.ArgumentParser(description="Read-only historical SHA verification")
        parser.add_argument("--root", required=True, type=Path)
        parser.add_argument("--index", required=True, type=Path)
        parser.add_argument("--index-sha", required=True)
        args = parser.parse_args(sys.argv[2:])
        print(json.dumps(runner.checked_index(args.root, args.index, args.index_sha)))
    elif len(sys.argv) > 1 and sys.argv[1] == "human":
        del sys.argv[1]
        review.main()
    else:
        runner.main()
