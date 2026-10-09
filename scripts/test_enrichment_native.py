"""Регрессии фактического CLI-транспорта: без повторов и подмены выполнения."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from enrichment_batch import Batch, digest, encoded, immutable
from enrichment_experiment import sha
from enrichment_native import (
    control_namespace,
    control_paths,
    execute,
    normalized_provenance,
    run,
    schema,
)
from enrichment_semantics import import_result, prepare_control
from test_enrichment_semantics import fixture


class NativeTests(unittest.TestCase):
    def fake_execution(self, tool: bool = False) -> Any:
        def call(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
            self.assertIn("--ephemeral", command)
            self.assertIn("read-only", command)
            self.assertIn('web_search="disabled"', command)
            self.assertNotIn("--model", command)
            self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", command)
            output = Path(command[command.index("--output-last-message") + 1])
            output.write_text('{"author_id":"A1"}')
            events: list[dict[str, Any]] = [{"type": "thread.started", "thread_id": "test-context"}]
            if tool:
                events.append({"type": "item.completed", "item": {"type": "web_search"}})
            events.append(
                {"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 3}}
            )
            kwargs["stdout"].write(b"".join((json.dumps(row) + "\n").encode() for row in events))
            return subprocess.CompletedProcess(command, 0)

        return call

    def test_high_requires_explicit_model_effort_and_preserves_requested(self) -> None:
        config = {"provider": "openai", "model": "gpt-6.1-sol", "effort": "high"}
        for model, effort in ((None, None), ("other", "high"), ("gpt-6.1-sol", "low")):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                with patch("enrichment_native.subprocess.run") as launch:
                    with self.assertRaisesRegex(ValueError, "конфигурация"):
                        execute(
                            root,
                            "input",
                            schema("verify", strict_levels=True),
                            root,
                            model=model,
                            effort=effort,
                            required_config=config,
                        )
                    launch.assert_not_called()
                    self.assertFalse((root / "started.json").exists())
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch(
                "enrichment_native.subprocess.run", side_effect=self.fake_execution()
            ) as launch:
                path, receipt = execute(
                    root,
                    "input",
                    schema("verify", strict_levels=True),
                    root,
                    model=config["model"],
                    effort=config["effort"],
                    required_config=config,
                    disable_mcp=True,
                )
                self.assertIn("features.shell_tool=false", launch.call_args.args[0])
                self.assertIn("features.unified_exec=false", launch.call_args.args[0])
                self.assertIn("features.browser_use=false", launch.call_args.args[0])
                self.assertEqual(receipt["requested_model"], config["model"])
                self.assertEqual(receipt["requested_effort"], config["effort"])
                command = launch.call_args.args[0]
                self.assertIn("-c", command)
                self.assertIn('model_provider="openai"', command)
                self.assertIn('model_reasoning_effort="high"', command)
                self.assertEqual(command[command.index("-m") + 1], config["model"])
                self.assertIsNone(receipt["model"])
                execute(
                    root,
                    "input",
                    schema("verify", strict_levels=True),
                    root,
                    model=config["model"],
                    effort=config["effort"],
                    required_config=config,
                )
                self.assertEqual(launch.call_count, 1)
                self.assertTrue(path.exists())

    def test_high_schema_only_requires_nonempty_level(self) -> None:
        def levels(strict: bool) -> dict[str, Any]:
            return cast(
                dict[str, Any],
                schema("verify", strict_levels=strict)["properties"]["items"]["items"][
                    "properties"
                ]["student_level"],
            )

        self.assertEqual(levels(True)["minItems"], 1)
        self.assertNotIn("minItems", levels(False))
        self.assertEqual(schema("verify")["properties"]["rules_version"]["enum"], ["semantic-v3"])

    def test_usage_normalization_preserves_receipt_without_double_count(self) -> None:
        receipt = {
            "tokens": {
                "input_tokens": 10,
                "output_tokens": 3,
                "cached_input_tokens": 5,
                "reasoning_tokens": 2,
            },
            "model": None,
        }
        normalized = normalized_provenance(receipt, "verify")
        self.assertEqual(normalized["tokens"], 13)
        self.assertEqual(normalized["token_usage"], receipt["tokens"])
        self.assertIsInstance(receipt["tokens"], dict)
        self.assertIsNone(
            normalized_provenance({"tokens": {"input_tokens": True, "output_tokens": 1}}, "verify")[
                "tokens"
            ]
        )
        self.assertIsNone(
            normalized_provenance({"tokens": {"input_tokens": 1}}, "verify")["tokens"]
        )

    def make_batch(self, root: Path, name: str, ids: list[str]) -> Batch:
        frozen = root / "frozen"
        frozen.mkdir(exist_ok=True)
        sample = encoded([{"id": aid} for aid in ids])
        immutable(frozen / "sample.json", sample)
        immutable(frozen / "manifest.json", encoded({"sample_sha256": digest(sample)}))
        rules = root / "rules.md"
        immutable(rules, b"Rules")
        return Batch.create(root / name, frozen, ids, rules)

    def test_all_concurrent_failures_are_durable_before_raise(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            batch = self.make_batch(root, "batch", ["A1", "A2"])
            with (
                patch("enrichment_native.run_stage", side_effect=ValueError("schema failure")),
                self.assertRaisesRegex(ValueError, "schema failure"),
            ):
                run(batch, root / "frozen", root, root / "rules.md", root)
            self.assertEqual(batch.status()["adapter_errors"], 2)
            self.assertEqual(batch.status()["network_reservations"], 0)
            self.assertEqual(batch.status()["automatic_retries"], 0)

    def test_new_batches_same_profile_isolate_inputs_and_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            batches = [self.make_batch(root, name, ["A1"]) for name in ("one", "two")]
            preserved: list[tuple[Path, bytes]] = []
            paths = []
            for index, batch in enumerate(batches):
                ticket = batch.ticket("A1", "collect")
                collector = root / f"collector-{index}.json"
                collector.write_bytes(
                    encoded(
                        {
                            "author_id": "A1",
                            "batch_ticket_id": "A1-collect",
                            "batch_input_sha256": ticket.name,
                            "items": [],
                            "provenance": {"agent_id": f"collector-{index}"},
                        }
                    )
                )
                batch.submit(
                    "A1-collect",
                    collector,
                    {
                        "agent_id": f"collector-{index}",
                        "stage": "collect",
                        "model": None,
                        "effort": None,
                    },
                )
                frozen = root / "frozen"
                source = prepare_control(
                    frozen,
                    {"id": "A1"},
                    collector,
                    {},
                    root / "rules.md",
                    sha(frozen / "sample.json"),
                    namespace=control_namespace(batch, frozen, "A1"),
                )
                _, result = fixture()
                result.update(input_sha256=sha(source), items=[])
                result_path = root / f"result-{index}.json"
                result_path.write_bytes(encoded(result))
                wrapper = import_result(frozen, source, result_path, "native-control-v3")
                self.assertEqual(control_paths(batch, frozen, "A1"), (source, wrapper))
                paths.append((source, wrapper))
                preserved.extend((path, path.read_bytes()) for path in (source, wrapper))
            self.assertNotEqual(paths[0], paths[1])
            for path, original in preserved:
                self.assertEqual(path.read_bytes(), original)

    def test_resume_after_verify_submission_before_wrapper_has_no_agent_call(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            batch = self.make_batch(root, "batch", ["A1"])
            ticket = batch.ticket("A1", "collect")
            collector = root / "collector.json"
            collector.write_bytes(
                encoded(
                    {
                        "author_id": "A1",
                        "batch_ticket_id": "A1-collect",
                        "batch_input_sha256": ticket.name,
                        "items": [],
                        "provenance": {"agent_id": "collector"},
                    }
                )
            )
            batch.submit(
                "A1-collect",
                collector,
                {"agent_id": "collector", "stage": "collect", "model": None, "effort": None},
            )
            evidence_root = root / "frozen"
            source = prepare_control(
                evidence_root,
                {"id": "A1"},
                collector,
                {},
                root / "rules.md",
                sha(evidence_root / "sample.json"),
                namespace=control_namespace(batch, evidence_root, "A1"),
            )
            ticket = batch.ticket("A1", "verify")
            _, result = fixture()
            result.update(
                input_sha256=sha(source),
                items=[],
                batch_ticket_id="A1-verify",
                batch_input_sha256=ticket.name,
            )
            result["provenance"]["stage"] = "verify"
            result_path = root / "verified.json"
            result_path.write_bytes(encoded(result))
            # Точная прежняя граница прерывания: submitted durable, import ещё нет.
            submitted_sha = batch.submit("A1-verify", result_path, result["provenance"])
            _, wrapper = control_paths(batch, evidence_root, "A1")
            self.assertFalse(wrapper.exists())
            with patch("enrichment_native.execute") as agent:
                status = run(
                    Batch(batch.root),
                    evidence_root,
                    root / "missing-cache",
                    root / "rules.md",
                    root,
                )
                agent.assert_not_called()
            self.assertTrue(wrapper.exists())
            self.assertTrue(all(status["stages"]["A1"].values()))
            self.assertEqual(status["network_reservations"], 0)
            self.assertEqual(sha(batch.root / "blobs" / submitted_sha), submitted_sha)
            old_wrapper = wrapper.read_bytes()
            old_events = status["event_count"]
            with patch("enrichment_native.execute") as agent:
                resumed = run(
                    Batch(batch.root),
                    evidence_root,
                    root / "missing-cache",
                    root / "rules.md",
                    root,
                )
                agent.assert_not_called()
            self.assertEqual(resumed["event_count"], old_events)
            self.assertEqual(wrapper.read_bytes(), old_wrapper)

    def test_actual_execution_receipt_resume_and_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch(
                "enrichment_native.subprocess.run", side_effect=self.fake_execution()
            ) as mock:
                path, receipt = execute(root, "input", schema("collect"), root)
                self.assertEqual(receipt["agent_id"], "codex-ephemeral:test-context")
                self.assertEqual(receipt["tokens"]["input_tokens"], 10)
                self.assertIsNone(receipt["cost_usd"])
                self.assertIsNone(receipt["model"])
                self.assertEqual(execute(root, "input", schema("collect"), root), (path, receipt))
                self.assertEqual(mock.call_count, 1)
                with self.assertRaises(ValueError):
                    execute(root, "changed", schema("collect"), root)
                path.write_text('{"changed":true}')
                with self.assertRaises(ValueError):
                    execute(root, "input", schema("collect"), root)

    def test_unknown_attempt_never_relaunches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            immutable(root / "started.json", encoded({"started_at_epoch": 1}))
            with patch("enrichment_native.subprocess.run") as mock:
                with self.assertRaisesRegex(ValueError, "неизвестен"):
                    execute(root, "input", schema("collect"), root)
                mock.assert_not_called()

    def test_completed_cli_recovers_receipt_without_second_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch(
                "enrichment_native.subprocess.run", side_effect=self.fake_execution()
            ) as mock:
                path, receipt = execute(root, "input", schema("collect"), root)
                (root / "receipt.json").unlink()  # Controlled crash after output, before receipt.
                recovered_path, recovered = execute(root, "input", schema("collect"), root)
                self.assertEqual((recovered_path, recovered), (path, receipt))
                self.assertEqual(mock.call_count, 1)

    def test_tool_use_rejected_without_silent_free_network(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with (
                patch(
                    "enrichment_native.subprocess.run", side_effect=self.fake_execution(tool=True)
                ),
                self.assertRaisesRegex(ValueError, "использовал инструмент"),
            ):
                execute(root, "input", schema("verify"), root)
            self.assertFalse((root / "receipt.json").exists())
            self.assertTrue((root / "raw-result.json").exists())
            json.loads((root / "finished.json").read_text())


if __name__ == "__main__":
    unittest.main()
