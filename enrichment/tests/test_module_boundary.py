import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from sfr_enrichment import native, runner
from sfr_enrichment.common import read
from sfr_enrichment.config import repository_root


class ModuleBoundaryTests(unittest.TestCase):
    def test_supported_cli_has_no_historical_imports_or_pi_entry(self) -> None:
        script = (
            "import sys; import sfr_enrichment.cli; "
            "assert not any(n.startswith('sfr_enrichment_legacy') for n in sys.modules)"
        )
        subprocess.run([sys.executable, "-I", "-c", script], check=True, capture_output=True)
        help_result = subprocess.run(
            [sys.executable, "-m", "sfr_enrichment", "--help"], check=True, capture_output=True
        )
        self.assertIn(b"archive-check", help_result.stdout)
        rejected = subprocess.run(
            [sys.executable, "-m", "sfr_enrichment", "pi"], capture_output=True
        )
        self.assertNotEqual(rejected.returncode, 0)

    def test_compatibility_wrapper_keeps_module_identity(self) -> None:
        script = (
            "import sys; sys.path.insert(0,sys.argv[1]); "
            "import enrichment_assisted; import sfr_enrichment.runner; "
            "assert enrichment_assisted is sfr_enrichment.runner"
        )
        subprocess.run(
            [sys.executable, "-I", "-c", script, str(repository_root() / "scripts")],
            check=True,
            capture_output=True,
        )

    def test_freeze_covers_actual_implementation_and_rejects_old_layout(self) -> None:
        hashes = runner.code_hashes()
        package = repository_root() / "enrichment/src/sfr_enrichment"
        self.assertTrue(
            all(str(p.relative_to(repository_root())) in hashes for p in package.glob("*.py"))
        )
        self.assertIn("enrichment/src/sfr_enrichment/http_policy.py", hashes)
        self.assertIn("enrichment/pyproject.toml", hashes)
        self.assertFalse(any(p.startswith("scripts/") for p in hashes))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "manifest.json").write_text(
                json.dumps(
                    {"method": runner.METHOD, "code_sha256": {"enrichment_assisted.py": "old"}}
                )
            )
            with self.assertRaisesRegex(ValueError, "Frozen"):
                runner.frozen(root)

    def test_native_stream_preserves_raw_usage_and_exact_bytes_without_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            output = {"status": "fixture"}
            events: list[dict[str, Any]] = [
                {"type": "thread.started", "thread_id": "offline-fixture"},
                {"type": "turn.started"},
            ]
            events += [
                {"type": "item.completed", "item": {"type": "reasoning", "text": "a" * i}}
                for i in range(1, 101)
            ]
            events += [
                {
                    "type": "turn.completed",
                    "usage": {"input_tokens": 42, "output_tokens": 17, "cached_input_tokens": 0},
                }
            ]
            stream = "".join(json.dumps(e) + "\n" for e in events).encode()

            def fake_run(
                command: list[str], **kwargs: object
            ) -> subprocess.CompletedProcess[bytes]:
                kwargs["stdout"].write(stream)  # type: ignore[attr-defined]
                (root / "job/raw-result.json").write_text(json.dumps(output))
                return subprocess.CompletedProcess(command, 0)

            with patch("sfr_enrichment.native.subprocess.run", side_effect=fake_run) as call:
                path, receipt = native.execute(
                    root / "job", "fixture", {}, root, model="gpt-6.1-sol", effort="high"
                )
                self.assertEqual(read(path), output)
                self.assertEqual(receipt["tokens"]["output_tokens"], 17)
                self.assertEqual(receipt["events_sha256"], hashlib.sha256(stream).hexdigest())
                self.assertEqual((root / "job/events.jsonl").read_bytes(), stream)
                native.execute(
                    root / "job", "fixture", {}, root, model="gpt-6.1-sol", effort="high"
                )
                self.assertEqual(call.call_count, 1)
            self.assertEqual(len(list(root.rglob("events.jsonl"))), 1)
            self.assertEqual(list(root.rglob("*-session-event.json")), [])

    def test_timeout_preserves_stream_errors_and_forbids_retry(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)

            def timed_out(command: list[str], **kwargs: object) -> None:
                kwargs["stdout"].write(b'{"type":"turn.started"}\n')  # type: ignore[attr-defined]
                kwargs["stderr"].write(b"offline timeout detail")  # type: ignore[attr-defined]
                raise subprocess.TimeoutExpired(command, 1)

            with patch("sfr_enrichment.native.subprocess.run", side_effect=timed_out) as call:
                for _ in range(2):
                    with self.assertRaises(ValueError):
                        native.execute(root / "job", "fixture", {}, root)
                self.assertEqual(call.call_count, 1)
            self.assertEqual(read(root / "job/finished.json")["exit_code"], -9)
            self.assertEqual((root / "job/stderr.log").read_bytes(), b"offline timeout detail")
            self.assertIn(b"turn.started", (root / "job/events.jsonl").read_bytes())
