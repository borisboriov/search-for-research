import hashlib
import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from sfr_enrichment import batch, contacts, native, replay, runner
from sfr_enrichment.common import read
from sfr_enrichment.config import repository_root


class ModuleBoundaryTests(unittest.TestCase):
    def old_module(self, name: str) -> Any:
        with patch.object(sys, "path", [str(repository_root() / "scripts"), *sys.path]):
            return importlib.import_module(name)

    def test_all_saved_old_patch_targets_resolve_without_invoking_clients(self) -> None:
        fixture = read(Path(__file__).parent / "fixtures/compat-patch-targets.json")
        with patch.object(sys, "path", [str(repository_root() / "scripts"), *sys.path]):
            for target in fixture["targets"]:
                with self.subTest(target=target):
                    original, _ = patch(target).get_original()
                    self.assertIsNotNone(original)

    def test_old_native_patch_targets_reach_runtime_and_restore(self) -> None:
        compat = self.old_module("enrichment_native")
        execute, probe = native.execute, native.isolation_probe
        with patch("enrichment_native.execute") as mocked:
            self.assertIs(native.execute, mocked)
            native.execute(Path("unused"), "fixture", {}, Path("unused"))
            mocked.assert_called_once()
        self.assertIs(native.execute, execute)
        self.assertIs(compat.execute, execute)
        with patch("enrichment_native.isolation_probe") as mocked:
            self.assertIs(execute.__globals__["isolation_probe"], mocked)
        self.assertIs(native.isolation_probe, probe)
        self.assertIs(compat.subprocess, native.__dict__["subprocess"])

    def test_old_batch_patch_targets_reach_actual_globals_and_restore(self) -> None:
        compat = self.old_module("enrichment_batch")
        self.assertIs(compat.os, batch.__dict__["os"])
        immutable = batch.immutable
        with patch("enrichment_batch.immutable") as mocked:
            self.assertIs(batch.immutable, mocked)
        self.assertIs(batch.immutable, immutable)
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch("enrichment_batch.os.link", side_effect=OSError("offline failure")),
                self.assertRaisesRegex(OSError, "offline failure"),
            ):
                batch.immutable(Path(directory) / "output", b"fixture")
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_old_source_and_replay_transport_symbols_remain_patchable(self) -> None:
        contact = self.old_module("enrichment_contact_first")
        compare = self.old_module("enrichment_glm_compare")
        self.assertIs(contact.httpx, contacts.__dict__["httpx"])
        self.assertIs(contact.Budget, contacts.__dict__["Budget"])
        self.assertIs(compare.subprocess, replay.__dict__["subprocess"])
        with patch("enrichment_contact_first.httpx.AsyncClient") as mocked:
            self.assertIs(contacts.Loader.__init__.__globals__["httpx"].AsyncClient, mocked)
        with patch("enrichment_contact_first.Budget.wait") as mocked:
            self.assertIs(contacts.Loader.__init__.__globals__["Budget"].wait, mocked)
        with patch("enrichment_glm_compare.subprocess.run") as mocked:
            self.assertIs(replay.legacy_pdf_text.__globals__["subprocess"].run, mocked)

    def test_distinct_historical_helpers_never_replace_runtime_on_mock_restore(self) -> None:
        compat = self.old_module("enrichment_contact_first")
        for name in ("check_contact_input", "verify_contact_input"):
            with self.subTest(name=name):
                historical, current = getattr(compat, name), getattr(contacts, name)
                self.assertIsNot(historical, current)
                with patch("enrichment_contact_first." + name) as mocked:
                    self.assertIs(getattr(compat, name), mocked)
                    self.assertIs(getattr(contacts, name), current)
                self.assertIs(getattr(compat, name), historical)
                self.assertIs(getattr(contacts, name), current)
                self.assertEqual(current.__module__, "sfr_enrichment.contacts")

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
        self.old_module("enrichment_native")
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

            with patch("enrichment_native.subprocess.run", side_effect=fake_run) as call:
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
