"""Offline merge gate regressions; never invoke GitHub or a real merge."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from check_guarded_merge import main, validate
from check_handoff import HandoffError
from test_check_handoff import BASE, HEAD, fixture


def ready() -> dict[str, Any]:
    data = fixture()
    data["isDraft"] = False
    data["comments"].append(
        {
            "createdAt": "2026-10-02T11:01:00Z",
            "body": "<!-- sfr-product-review "
            + json.dumps({"base": BASE, "head": HEAD, "verdict": "ready"})
            + " -->",
        }
    )
    return data


class GuardTests(unittest.TestCase):
    def test_ready(self) -> None:
        validate(ready(), HEAD)

    def test_not_ready(self) -> None:
        for key, value in [
            ("state", "CLOSED"),
            ("isDraft", True),
            ("baseRefName", "other"),
            ("headRefOid", "d" * 40),
            ("baseBranchOid", "d" * 40),
        ]:
            data = ready()
            data[key] = value
            with self.subTest(key=key), self.assertRaises(HandoffError):
                validate(data, HEAD)

    def test_pending_or_missing(self) -> None:
        for checks in [[], [dict(c, conclusion="FAILURE") for c in ready()["statusCheckRollup"]]]:
            data = ready()
            data["statusCheckRollup"] = checks
            with self.assertRaises(HandoffError):
                validate(data, HEAD)

    def test_newer_blocked_product_overrides(self) -> None:
        data = ready()
        data["comments"].append(
            dict(
                data["comments"][-1],
                createdAt="2026-10-02T11:02:00Z",
                body=data["comments"][-1]["body"].replace("ready", "blocked"),
            )
        )
        with self.assertRaises(HandoffError):
            validate(data, HEAD)

    def test_missing_stale_product(self) -> None:
        for replacement in ["", ready()["comments"][-1]["body"].replace(BASE, "d" * 40)]:
            data = ready()
            data["comments"][-1]["body"] = replacement
            with self.assertRaises(HandoffError):
                validate(data, HEAD)

    def test_network_error(self) -> None:
        with (
            patch.object(sys, "argv", ["gate", "200", HEAD]),
            patch("check_guarded_merge.fetch_handoff", side_effect=HandoffError("offline")),
        ):
            self.assertEqual(main(), 1)

    def test_system_python_isolated_gate(self) -> None:
        root = Path(__file__).resolve().parent
        executable = Path("/usr/bin/python3")
        if not executable.exists():
            self.skipTest("No system Python")
        program = (
            "import sys,json; sys.path.insert(0, sys.argv[1]); "
            "from check_guarded_merge import validate; "
            "validate(json.load(sys.stdin), sys.argv[2])"
        )
        result = subprocess.run(
            [str(executable), "-I", "-c", program, str(root), HEAD],
            input=json.dumps(ready()),
            text=True,
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_hook_dispatch(self) -> None:
        # Evaluate the embedded parser with subprocess mocked, no executable shims.
        root = Path(__file__).resolve().parents[1]
        for hook in [".codex/hooks/block-push.sh", ".claude/hooks/block-push.sh"]:
            script = (root / hook).read_text().split("<<'PY' || true\n", 1)[1].split("\nPY\n", 1)[0]
            script = script.replace("sys.exit(main())", "")
            scope: dict[str, Any] = {}
            exec(compile(script, hook, "exec"), scope)
            cmd = (
                "gh pr merge --repo borisboriov/search-for-research 200 "
                f"--merge --match-head-commit {HEAD}"
            )
            import io

            for returncode in [0, 1]:
                with (
                    patch.object(
                        sys, "stdin", io.StringIO(json.dumps({"tool_input": {"command": cmd}}))
                    ),
                    patch.object(sys, "argv", ["hook", str(root)]),
                    patch(
                        "subprocess.run",
                        return_value=subprocess.CompletedProcess([], returncode, "", ""),
                    ),
                ):
                    self.assertEqual(scope["main"](), 0 if returncode == 0 else 2)
            for command in [
                cmd + " --admin",
                cmd + " --auto",
                cmd + " --delete-branch",
                "env " + cmd,
                cmd + " && true",
                "X=1 " + cmd,
                cmd.replace("search-for-research", "other"),
            ]:
                with (
                    patch.object(
                        sys, "stdin", io.StringIO(json.dumps({"tool_input": {"command": command}}))
                    ),
                    patch("subprocess.run") as run,
                ):
                    self.assertEqual(scope["main"](), 2, command)
                    run.assert_not_called()
            with (
                patch.object(
                    sys, "stdin", io.StringIO(json.dumps({"tool_input": {"command": cmd}}))
                ),
                patch.object(sys, "argv", ["hook", str(root)]),
                patch("subprocess.run", side_effect=subprocess.TimeoutExpired("gate", 180)),
            ):
                self.assertEqual(scope["main"](), 2)


if __name__ == "__main__":
    unittest.main()
