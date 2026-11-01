"""Synthetic claude_cli protocol, import and ledger regressions; no real CLI or model."""

import fcntl
import json
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any

from test_native_claude import FIXTURES, ClaudeFakes, FakeProcess, fixture_result

from sfr_enrichment import native_claude, nir_execute
from sfr_enrichment.common import read, sha, write_new
from sfr_enrichment.nir import freeze, import_native, prepare_model, prepared_request


class Responder(ClaudeFakes):
    """Answer each task with a schema-valid synthetic result for its arm, or a queued one."""

    def popen(self, command: list[str], **kwargs: Any) -> FakeProcess:
        if command[command.index("--output-format") + 1] == "json" and not self.results:
            schema = json.loads(command[command.index("--json-schema") + 1])
            answer = (
                {"label": "supported"}
                if "label" in schema["properties"]
                else {"identity": "supported", "object_relation": "supported"}
            )
            self.results.append(
                fixture_result(
                    "synthetic-result-success.json",
                    structured_output=answer
                    | {"reason": "Synthetic fixture only", "source_ids": ["s1"]},
                )
            )
        return super().popen(command, **kwargs)


class NirClaudeTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name).resolve()
        source = self.tmp / "source.txt"
        source.write_text("Synthetic Researcher, example@institute.invalid. Laboratory office.")
        self.selection = self.tmp / "selection.json"
        write_new(
            self.selection,
            [
                {
                    "case_id": f"c{i}",
                    "group_id": f"g{i}",
                    "pair_id": f"p{i}",
                    "example_ids": [f"e{i}"],
                    "profile": {"name": "Synthetic Researcher"},
                    "email": f"example{i}@institute.invalid",
                    "evidence": [
                        {
                            "source_id": "s1",
                            "url": "https://institute.invalid/source",
                            "captured_at": "2026-11-01T10:00:00+03:00",
                            "content_date": None,
                            "source_path": str(source),
                            "excerpt": "Laboratory office.",
                        }
                    ],
                }
                for i in range(1, 4)
            ],
        )
        inventory = self.tmp / "previous-inventory.json"
        write_new(inventory, {"warning": "Synthetic previous-use inventory only"})
        self.exclusions = self.tmp / "exclusions.json"
        write_new(
            self.exclusions,
            {
                "complete_prior_use_inventory": True,
                "inventory_sources": [{"path": str(inventory), "sha256": sha(inventory)}],
                "group_ids": [],
                "pair_ids": [],
                "example_ids": [],
            },
        )
        self.protocol = {
            "rubric": "Synthetic neutral rubric; supported/refuted/insufficient",
            "common_examples": "Only synthetic examples.",
            "instructions_B": "Strong verdict: label/reason/source_ids.",
            "instructions_C": "identity/object_relation/reason/source_ids.",
            "transport": "claude_cli",
            "model": "claude-haiku-5-5",
            "effort": "high",
            "generation": {},
            "code_revision": "synthetic-revision",
            "runtime_version": "synthetic-runtime",
            "limits": {"proposed_timeout_seconds_per_call": 300},
        }
        self.root = self.freeze_root("private", self.protocol)
        prepare_model(self.root)
        self.binary = self.tmp / "claude-binary"
        self.binary.write_bytes(b"fixture executable")
        self.fakes = Responder(self.root / "isolated-cwd")

    def freeze_root(self, name: str, protocol: dict[str, Any]) -> Path:
        path = self.tmp / f"{name}-protocol.json"
        write_new(path, protocol)
        root = self.tmp / name
        freeze(root, self.selection, self.exclusions, path, development_only=True)
        return root

    def use_root(self, name: str) -> None:
        self.root = self.freeze_root(name, self.protocol)
        prepare_model(self.root)
        self.fakes = Responder(self.root / "isolated-cwd")

    def authorization(self, **changes: Any) -> Path:
        value = {
            "purpose": "diagnostic_pilot_not_holdout",
            "live_authorized": True,
            "transport": "claude_cli_existing_subscription",
            "new_paid_services_authorized": False,
            "retries": 0,
            "parallelism": 1,
            "absolute_deadline": "2099-01-01T00:00:00+03:00",
            "run_deadline_seconds": 7200,
            "per_call_timeout_seconds": 300,
            "max_output_file_bytes": 65536,
            "max_input_bytes_per_case": 1000000,
            "model_job_cap": 6,
            "model": "claude-haiku-5-5",
            "effort": "high",
            "cli_version": "2.1.316 (Claude Code)",
            "authorization_reference": "synthetic test only",
            "execution_root": str(self.root),
            "frozen_manifest_sha256": sha(self.root / "manifest.json"),
            "prepared_manifest_sha256": sha(self.root / "prepared-model" / "manifest.json"),
            **nir_execute.implementation_hashes(),
        } | changes
        path = self.tmp / f"authorization-{len(list(self.tmp.glob('authorization-*')))}.json"
        write_new(path, value)
        return path

    def run_ledger(self, authorization: Path, **options: Any) -> int:
        with self.fakes.active(self.binary):
            return nir_execute.execute(self.root, authorization, **options)

    def order(self) -> list[str]:
        return list(read(self.root / "prepared-model" / "manifest.json")["order"])

    def test_prepared_claude_request_carries_transport_and_codex_stays_legacy(self) -> None:
        prepared = read(self.root / "prepared-model" / "manifest.json")
        self.assertEqual(prepared["transport"], "claude_cli")
        request = prepared_request(self.root, "c1-B")
        self.assertEqual(
            (request["schema"], request["transport"]), ("nir_native_request_v2", "claude_cli")
        )
        self.assertEqual(
            request["claude_kwargs"],
            {
                "model": "claude-haiku-5-5",
                "effort": "high",
                "timeout_seconds": 300,
                "max_output_file_bytes": 65536,
            },
        )
        self.assertNotIn("native_kwargs", request)
        self.assertFalse(request["launch_authorized"])
        codex = {k: v for k, v in self.protocol.items() if k != "transport"}
        codex_root = self.freeze_root("codex", codex | {"model": "gpt-6.1-sol"})
        prepare_model(codex_root)
        legacy = prepared_request(codex_root, "c1-B")
        self.assertNotIn("transport", legacy)
        self.assertNotIn("transport", read(codex_root / "prepared-model" / "manifest.json"))
        self.assertEqual(legacy["schema"], "nir_native_request_v1")
        self.assertTrue(legacy["native_kwargs"]["disable_mcp"])

    def test_transport_mismatch_and_unsupported_protocol_are_rejected(self) -> None:
        manifest_path = self.root / "prepared-model" / "manifest.json"
        prepared = read(manifest_path)
        entry = prepared["requests"]["c1-B"]
        request_path = self.root / entry["path"]
        request = read(request_path)
        request_path.unlink()
        write_new(request_path, request | {"transport": "codex_cli"})
        prepared["requests"]["c1-B"]["sha256"] = sha(request_path)
        manifest_path.unlink()
        write_new(manifest_path, prepared)
        with self.assertRaisesRegex(ValueError, "Транспорт"):
            prepared_request(self.root, "c1-B")
        for name, change in (
            ("bad-transport", {"transport": "pi"}),
            ("bad-effort", {"effort": "x"}),
        ):
            with (
                self.subTest(name=name),
                self.assertRaisesRegex(ValueError, "транспорт|effort"),
            ):
                self.freeze_root(name, self.protocol | change)

    def test_import_rechecks_saved_init_and_normalizes_claude_usage(self) -> None:
        request = prepared_request(self.root, "c1-C")
        directory = self.tmp / "native-c1-C"
        cwd = self.root / "isolated-cwd"
        cwd.mkdir()
        with self.fakes.active(self.binary):
            native_claude.execute(
                directory,
                (self.root / request["prompt_path"]).read_text(),
                read(self.root / request["output_schema_path"]),
                cwd,
                system_prompt=(self.root / request["system_prompt_path"]).read_text(),
                deadline_epoch=time.time() + 3600,
                **request["claude_kwargs"],
            )
        proof = read(directory / "isolation-control.json")
        saved = directory / proof["stdout_path"]
        original = saved.read_bytes()
        saved.chmod(0o600)
        saved.write_bytes(original.replace(b'"tools": ["Read"]', b'"tools": []'))
        with self.assertRaisesRegex(ValueError, "isolation stdout"):
            import_native(self.root, "c1-C", directory, "tampered")
        saved.write_bytes(original)
        result = read(import_native(self.root, "c1-C", directory, "native-c1-C"))["results"][0]
        self.assertEqual(result["label"], "supported")
        self.assertEqual((result["input_tokens"], result["output_tokens"]), (1540, 85))
        self.assertEqual(result["cost_usd"], 0.0123)
        self.assertEqual(result["observed_model"], "claude-haiku-5-5")
        self.assertIsNone(result["observed_effort"])
        self.assertEqual(result["receipt"]["transport"], "claude_cli")

    def test_runner_follows_order_imports_each_job_and_honours_cap(self) -> None:
        authorization = self.authorization(model_job_cap=3)
        self.assertEqual(self.run_ledger(authorization, single=True), 0)
        execution = self.root / "execution"
        attempt = read(execution / "attempt-000.json")
        self.assertEqual(attempt["request_id"], self.order()[0])
        self.assertEqual(attempt["quota_observation"]["source"], "unavailable")
        self.assertIsNone(attempt["quota_observation"]["remaining_percent"])
        self.assertEqual(
            read(execution / "run-clock.json")["authorization_sha256"], sha(authorization)
        )
        self.assertEqual(self.run_ledger(authorization), 0)
        outcomes = sorted(p.name for p in execution.glob("outcome-*.json"))
        self.assertEqual(outcomes, sorted(f"outcome-{r}.json" for r in self.order()[:3]))
        self.assertTrue(all(read(execution / n)["status"] == "imported" for n in outcomes))
        launches = len(self.fakes.calls)
        self.assertEqual(self.run_ledger(authorization), 0)
        self.assertEqual(len(self.fakes.calls), launches)
        self.assertEqual(len(list((self.root / "model-records").rglob("*.json"))), 3)

    def test_deferred_rate_limit_keeps_slot_and_stops_until_new_launch(self) -> None:
        authorization = self.authorization()
        self.fakes.results.append(
            FakeProcess(fixture_result("synthetic-result-rate-limit.json"), code=1)
        )
        self.assertEqual(self.run_ledger(authorization), nir_execute.EXIT_DEFERRED)
        execution = self.root / "execution"
        first = self.order()[0]
        deferred = read(execution / f"deferred-000-{first}.json")
        self.assertEqual(deferred["status"], "transport_deferred")
        self.assertFalse(deferred["slot_consumed"])
        self.assertFalse((execution / f"outcome-{first}.json").exists())
        self.assertEqual(self.run_ledger(authorization, request_id=first), 0)
        self.assertEqual(read(execution / "attempt-001.json")["request_id"], first)
        self.assertEqual(read(execution / f"outcome-{first}.json")["status"], "imported")
        self.assertEqual(nir_execute.ledger_position(execution, self.order()), (1, 2))

    def test_technical_failure_or_unresolved_attempt_blocks_continuation(self) -> None:
        authorization = self.authorization()
        self.fakes.results.append(
            FakeProcess((FIXTURES / "real-result-bare-auth-error.json").read_bytes(), code=1)
        )
        self.assertEqual(self.run_ledger(authorization), nir_execute.EXIT_TECHNICAL)
        first = self.order()[0]
        outcome = read(self.root / "execution" / f"outcome-{first}.json")
        self.assertEqual(outcome["status"], "technical_failure")
        self.assertTrue(outcome["requires_inspection_before_next_job"])
        with self.assertRaisesRegex(ValueError, "inspection"):
            self.run_ledger(authorization)
        (self.root / "execution" / f"outcome-{first}.json").unlink()
        with self.assertRaisesRegex(ValueError, "unresolved"):
            self.run_ledger(authorization)

    def test_admission_rejects_changed_authorization_order_clock_and_lock(self) -> None:
        for change, field in (
            ({"transport": "codex_cli_existing_chatgpt_subscription"}, "transport"),
            ({"new_paid_services_authorized": True}, "new_paid_services_authorized"),
            ({"nir_sha256": "0" * 64}, "nir_sha256"),
            ({"runner_sha256": "0" * 64}, "runner_sha256"),
            ({"native_claude_sha256": "0" * 64}, "native_claude_sha256"),
            ({"prepared_manifest_sha256": "0" * 64}, "prepared manifest"),
            ({"retries": 1}, "retries"),
            ({"model_job_cap": 99}, "model_job_cap"),
            ({"execution_root": "/elsewhere"}, "execution_root"),
        ):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, field):
                self.run_ledger(self.authorization(**change))
        self.assertFalse((self.root / "execution").exists())
        for name, change, message in (
            ("other-model", {"model": "claude-other"}, "differs from authorization"),
            ("other-cli", {"cli_version": "9.9.9 (Claude Code)"}, "Installed Claude CLI"),
        ):
            with self.subTest(name=name):
                self.use_root(name)
                with self.assertRaisesRegex(ValueError, message):
                    self.run_ledger(self.authorization(**change))
                self.assertFalse(list((self.root / "execution").glob("attempt-*")))
        self.use_root("order-clock-lock")
        authorization = self.authorization()
        with self.assertRaisesRegex(ValueError, "changed order"):
            self.run_ledger(authorization, request_id=self.order()[1])
        with self.assertRaisesRegex(ValueError, "another authorization"):
            self.run_ledger(self.authorization(authorization_reference="other"))
        with (self.root / "execution" / "writer.lock").open("a") as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(ValueError, "writer"):
                self.run_ledger(authorization)
        self.assertFalse(list((self.root / "execution").glob("attempt-*")))

    def test_expired_deadline_stops_before_any_attempt(self) -> None:
        authorization = self.authorization(absolute_deadline="2020-01-01T00:00:00+03:00")
        with self.assertRaisesRegex(ValueError, "deadline"):
            self.run_ledger(authorization)
        self.assertFalse(list((self.root / "execution").glob("attempt-*")))


if __name__ == "__main__":
    unittest.main()
