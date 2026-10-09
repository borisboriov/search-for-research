"""Офлайн конвейер: общие байты, gate, blinding, empty и отказ без повторов."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from enrichment_batch import encoded, immutable
from enrichment_experiment import read
from enrichment_verifier_benchmark import (
    AXES,
    aggregate,
    check_schema,
    checkpoint,
    freeze,
    packets,
    preflight,
    run,
    validate_judge,
)
from enrichment_verifier_inputs import CASES
from test_enrichment_semantics import assessment, fixture
from test_enrichment_verifier_inputs import source


class BenchmarkTests(unittest.TestCase):
    def setup_root(self, temporary: str) -> Path:
        base = Path(temporary)
        old = base / "old"
        root = base / "new"
        for author, ids, _ in CASES:
            immutable(
                old / "semantics/semantic-v3/inputs" / f"{author}.json",
                encoded(source(author, ids)),
            )
        freeze(root, old)
        with patch("enrichment_verifier_benchmark.isolation_probe", return_value={"exit_code": 0}):
            preflight(root)
        return root

    def answer(self, task: dict[str, Any]) -> dict[str, Any]:
        _, result = fixture()
        result.pop("provenance")
        result.update(
            {
                k: task[k]
                for k in ("author_id", "batch_ticket_id", "batch_input_sha256", "input_sha256")
            }
        )
        result["items"] = [
            assessment(i["item_id"], evidence_refs=["E1"], student_level=["unknown"])
            for i in task["semantic_input"]["items"]
        ]
        return result

    def pi(
        self,
        root: Path,
        batch: Any,
        author: str,
        stage: str,
        task: dict[str, Any],
        instruction: str,
        contract: dict[str, Any],
        **kwargs: Any,
    ) -> tuple[Path, dict[str, Any]]:
        directory = root / "runs" / author / stage
        path = directory / "result.json"
        immutable(path, encoded(self.answer(task)))
        immutable(
            directory / "request.json",
            encoded({"task": task, "system_prompt": instruction, "output_schema": contract}),
        )
        return path, {
            "agent_id": "pi-" + author,
            "runtime_status": "recorded",
            "model": "zai/glm-5.3-flash",
            "effort": "high",
            "tokens": 10,
            "cost_usd": None,
            "effective_sdk_config": {"provider": "zai", "model": "glm-5.3-flash", "effort": "high"},
            "tool_inventory": [],
        }

    def native(
        self, directory: Path, prompt: str, contract: dict[str, Any], cwd: Path, **kwargs: Any
    ) -> tuple[Path, dict[str, Any]]:
        task = json.loads(prompt)["task"]
        pi_request = read(directory.parent / "pi_verifier/request.json")
        expected = json.dumps(
            {"task": pi_request["task"], "output_json_schema": pi_request["output_schema"]},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        self.assertEqual(prompt, expected)
        self.assertEqual(kwargs["system_prompt"], pi_request["system_prompt"])
        path = directory / "raw-result.json"
        immutable(path, encoded(self.answer(task)))
        return path, {
            "agent_id": "native-" + task["author_id"],
            "runtime_status": "runtime_not_exposed",
            "model": None,
            "effort": None,
            "tokens": {"input_tokens": 10, "output_tokens": 4},
            "cost_usd": None,
            "requested_model": "gpt-6.1-sol",
            "requested_effort": "high",
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        }

    def test_gate_resume_blinding_and_all37(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.setup_root(temporary)
            initial = aggregate(root)
            self.assertEqual(initial["atoms_frozen_per_model"], 37)
            self.assertEqual(initial["atoms_compared_per_model"], 0)
            self.assertIsNone(initial["error_types"])
            with (
                patch("enrichment_verifier_benchmark.run_pi", side_effect=self.pi) as pi,
                patch("enrichment_verifier_benchmark.execute", side_effect=self.native) as native,
            ):
                with self.assertRaises(FileNotFoundError):
                    run(root, 12)
                self.assertEqual(pi.call_count, 0)
                run(root, 3)
                self.assertEqual(aggregate(root)["atoms_compared_per_model"], 12)
                checkpoint(root)
                run(root, 12)
                run(root, 12)
                self.assertEqual(pi.call_count, 12)
                self.assertEqual(native.call_count, 12)
            paths = packets(root)
            self.assertEqual(len(paths), 4)
            self.assertEqual(
                sum(len(p["items"]) for path in paths for p in read(path)["profiles"]), 37
            )
            for path in paths:
                text = path.read_text()
                for forbidden in (
                    "agent_id",
                    "provenance",
                    "result_path",
                    "blind_seed",
                    "validation",
                    "secret-model",
                    "old-model",
                ):
                    self.assertNotIn(forbidden, text)

    def test_technical_failure_stops_before_next(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.setup_root(temporary)
            with (
                patch(
                    "enrichment_verifier_benchmark.run_pi", side_effect=ValueError("invalid")
                ) as pi,
                patch("enrichment_verifier_benchmark.execute") as native,
            ):
                with self.assertRaises(ValueError):
                    run(root, 3)
                with self.assertRaises(ValueError):
                    run(root, 3)
                self.assertEqual(pi.call_count, 1)
                native.assert_not_called()

    def test_schema_and_judge_both_unknown_empty_refs(self) -> None:
        packet = {"profiles": [{"author_id": "A1", "items": [], "evidence_pool": {}}]}
        rows: list[dict[str, Any]] = [
            {
                "author_id": "A1",
                "response": s,
                "axis": a,
                "grade": "correct",
                "error_types": [],
                "severity": "none",
                "evidence_refs": [],
                "basis": "Неизвестность сохранена корректно",
            }
            for s in ("A", "B")
            for a in AXES
        ]
        result = {"input_sha256": "x", "atom_evaluations": [], "profile_evaluations": rows}
        validate_judge(packet, result, "x")
        result["profile_evaluations"] = rows[:3]
        with self.assertRaises(ValueError):
            validate_judge(packet, result, "x")
        result["profile_evaluations"] = rows
        rows[0]["evidence_refs"] = ["missing"]
        with self.assertRaises(ValueError):
            validate_judge(packet, result, "x")
        with self.assertRaises(ValueError):
            check_schema({"extra": "x"}, {"type": "object", "properties": {}})


class NativeIsolationTests(unittest.TestCase):
    def test_leaked_render_fails_before_inference(self) -> None:
        import subprocess

        from enrichment_native import execute

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            leaked = [
                {
                    "type": "message",
                    "role": "developer",
                    "content": [{"type": "input_text", "text": "HOME SECRET"}],
                }
            ]
            with patch(
                "enrichment_native.subprocess.run",
                return_value=subprocess.CompletedProcess([], 0, json.dumps(leaked).encode(), b""),
            ) as launch:
                with self.assertRaises(ValueError):
                    execute(
                        root,
                        "task",
                        {},
                        root,
                        model="gpt-6.1-sol",
                        effort="high",
                        system_prompt="rules",
                        disable_mcp=True,
                    )
                self.assertEqual(launch.call_count, 1)
                self.assertFalse((root / "started.json").exists())

    def test_timeout_is_finished_unknown_and_never_retried(self) -> None:
        import subprocess

        from enrichment_native import execute

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rendered = [
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "task"}],
                }
            ]
            with patch(
                "enrichment_native.subprocess.run",
                side_effect=[
                    subprocess.CompletedProcess([], 0, json.dumps(rendered).encode(), b""),
                    subprocess.TimeoutExpired("codex", 600),
                ],
            ) as launch:
                with self.assertRaises(ValueError):
                    execute(
                        root,
                        "task",
                        {},
                        root,
                        model="gpt-6.1-sol",
                        effort="high",
                        system_prompt="rules",
                        disable_mcp=True,
                    )
                with self.assertRaises(ValueError):
                    execute(
                        root,
                        "task",
                        {},
                        root,
                        model="gpt-6.1-sol",
                        effort="high",
                        system_prompt="rules",
                        disable_mcp=True,
                    )
                self.assertEqual(launch.call_count, 2)
                self.assertIsNone(read(root / "finished.json")["full_job_usage"])
                command = read(root / "command.json") if (root / "command.json").exists() else []
                self.assertNotIn("--dangerously-bypass-hook-trust", command)

    def test_any_native_tool_item_is_rejected(self) -> None:
        import subprocess

        from enrichment_native import execute

        for kind in ("file_change", "sleep", "collab_agent_tool_call"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                rendered = [
                    {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": "task"}],
                    }
                ]

                def call(
                    command: list[str],
                    kind: str = kind,
                    rendered: list[dict[str, Any]] = rendered,
                    **kwargs: Any,
                ) -> Any:
                    if command[1] == "debug":
                        return subprocess.CompletedProcess(
                            command, 0, json.dumps(rendered).encode(), b""
                        )
                    Path(command[command.index("--output-last-message") + 1]).write_text("{}")
                    events = [
                        {"type": "thread.started", "thread_id": "test"},
                        {"type": "item.completed", "item": {"type": kind}},
                        {
                            "type": "turn.completed",
                            "usage": {"input_tokens": 1, "output_tokens": 1},
                        },
                    ]
                    kwargs["stdout"].write(b"".join(encoded(row) for row in events))
                    return subprocess.CompletedProcess(command, 0)

                with (
                    patch("enrichment_native.subprocess.run", side_effect=call),
                    self.assertRaisesRegex(ValueError, "инструмент"),
                ):
                    execute(
                        root,
                        "task",
                        {},
                        root,
                        model="gpt-6.1-sol",
                        effort="high",
                        system_prompt="rules",
                        disable_mcp=True,
                    )
