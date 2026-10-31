"""Run the Stop hint in isolated repositories; never exercise merge or deletion."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOKS = [ROOT / client / "hooks/review-reminder.sh" for client in (".codex", ".claude")]


class ReviewReminder(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True, capture_output=True)

    def run_hint(self, hook: Path, *, active: bool = False, outside: bool = False) -> str:
        result = subprocess.run(
            ["bash", str(hook)],
            cwd=self.root if outside else self.repo,
            input=json.dumps({"session_id": "fixture", "stop_hook_active": active}),
            text=True,
            capture_output=True,
            env={**os.environ, "TMPDIR": str(self.root)},
            timeout=10,
            check=True,
        )
        self.assertEqual(result.stderr, "")
        return result.stdout

    def test_clean_discussion_and_non_repository_are_silent(self) -> None:
        for hook in HOOKS:
            with self.subTest(hook=hook):
                self.assertEqual(self.run_hint(hook), "")
                self.assertEqual(self.run_hint(hook, outside=True), "")

    def test_changes_get_a_conditional_hint_without_state_files(self) -> None:
        report = self.repo / "SFR_old_REPORT.md"
        report.write_text("# Ревью\nold\nold\nold\n")
        before = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*"))
        for hook in HOOKS:
            with self.subTest(hook=hook):
                output = json.loads(self.run_hint(hook))
                self.assertIn("Если сейчас передаёте свой результат", output["systemMessage"])
                self.assertNotIn("независимого ревью нет", output["systemMessage"])
                self.assertEqual(self.run_hint(hook, active=True), "")
        after = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*"))
        self.assertEqual(before, after)

    def test_client_scripts_do_not_diverge(self) -> None:
        self.assertEqual(HOOKS[0].read_bytes(), HOOKS[1].read_bytes())


if __name__ == "__main__":
    unittest.main()
