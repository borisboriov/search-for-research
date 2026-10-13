"""Fail-closed live gate for the explicitly authorized SFR merge only."""

from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_handoff import HandoffError, check_handoff, comment_time, fetch_handoff, unique_fields


def validate(snapshot: object, expected: str) -> None:
    base, head = check_handoff(snapshot)
    assert isinstance(snapshot, dict)
    if (
        head != expected
        or snapshot.get("baseRefName") != "main"
        or snapshot.get("isDraft") is not False
    ):
        raise HandoffError("Нужны ожидаемый head, main и non-draft PR")
    comments = snapshot["comments"]
    now = datetime.now(UTC)
    entries = [
        (comment_time(c.get("createdAt"), now), i, c["body"])
        for i, c in enumerate(comments)
        if "sfr-product-review" in c["body"]
    ]
    if not entries:
        raise HandoffError("Нет продуктовой приёмки")
    body = max(entries)[2]
    matches = re.findall(r"<!--\s*sfr-product-review\s+(.+?)\s*-->", body, re.S)
    if len(matches) != 1 or body.count("sfr-product-review") != 1:
        raise HandoffError("Неоднозначная продуктовая приёмка")
    receipt = json.loads(matches[0], object_pairs_hook=unique_fields)
    if receipt != {"base": base, "head": head, "verdict": "ready"}:
        raise HandoffError("Продуктовая приёмка не ready для текущих base/head")


def main() -> int:
    if (
        len(sys.argv) != 3
        or not re.fullmatch(r"[1-9][0-9]*", sys.argv[1])
        or not re.fullmatch(r"[0-9a-f]{40}", sys.argv[2])
    ):
        return 1
    try:
        validate(fetch_handoff(int(sys.argv[1])), sys.argv[2])
    except (HandoffError, ValueError, KeyError, TypeError) as exc:
        print(f"Merge не подтверждён: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
