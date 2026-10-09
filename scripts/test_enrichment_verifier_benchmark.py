"""Офлайн конвейер: общие байты, gate, blinding, empty и отказ без повторов."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from enrichment_batch import encoded, immutable
from enrichment_experiment import read, sha
from enrichment_verifier_benchmark import (
    AXES,
    aggregate,
    check_schema,
    checkpoint,
    freeze,
    packets,
    preflight,
    run,
    stage_usage,
    validate_judge,
)
from enrichment_verifier_inputs import CASES
from test_enrichment_semantics import assessment, fixture
from test_enrichment_verifier_inputs import source


class BenchmarkTests(unittest.TestCase):
    def test_freeze_guards_before_any_write_and_allows_only_explicit_preparation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            old = base / "enrichment100-20261008"
            sibling = base / "enrichment-pi12-20261009"
            high = base / "enrichment-pi12-high-20261009"
            for author, ids, _ in CASES:
                immutable(
                    old / "semantics/semantic-v3/inputs" / f"{author}.json",
                    encoded(source(author, ids)),
                )
            for path in (sibling, high, base / "foreign", base / "frozen"):
                immutable(path / "evidence.json", b"unchanged")
            immutable(base / "frozen/manifest.json", b"{}")
            alias = base / "alias"
            alias.symlink_to(old, target_is_directory=True)
            before = {str(p): sha(p) for p in base.rglob("*") if p.is_file()}
            for target in (
                old,
                sibling,
                high,
                old / "nested",
                sibling / "nested",
                alias / "nested",
                base,
                base / "foreign",
                base / "frozen",
            ):
                with self.subTest(target=target), self.assertRaises(ValueError):
                    freeze(target, old, allow_existing_preparation=True)
                self.assertEqual(before, {str(p): sha(p) for p in base.rglob("*") if p.is_file()})
            self.assertFalse((old / "nested").exists())
            new = base / "new"
            immutable(new / "preflight/baseline.json", b"baseline")
            immutable(new / "diagnosis/timeline.json", b"timeline")
            with self.assertRaises(ValueError):
                freeze(new, old)
            freeze(new, old, allow_existing_preparation=True)
            self.assertEqual((new / "preflight/baseline.json").read_bytes(), b"baseline")
            frozen = {str(p): sha(p) for p in new.rglob("*") if p.is_file()}
            with self.assertRaises(ValueError):
                freeze(new, old, allow_existing_preparation=True)
            self.assertEqual(frozen, {str(p): sha(p) for p in new.rglob("*") if p.is_file()})

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

    def test_aggregate_keeps_models_axes_judge_usage_and_real_denominators(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.setup_root(temporary)
            with (
                patch("enrichment_verifier_benchmark.run_pi", side_effect=self.pi),
                patch("enrichment_verifier_benchmark.execute", side_effect=self.native),
            ):
                run(root, 3)
            path = packets(root)[0]
            packet = read(path)
            rows: dict[str, list[dict[str, Any]]] = {
                "atom_evaluations": [],
                "profile_evaluations": [],
            }
            for profile in packet["profiles"]:
                for slot in ("A", "B"):
                    for key, suffix, values in (
                        ("atom_evaluations", "item_id", [i["item_id"] for i in profile["items"]]),
                        ("profile_evaluations", "axis", AXES),
                    ):
                        for value in values:
                            rows[key].append(
                                {
                                    "author_id": profile["author_id"],
                                    "response": slot,
                                    suffix: value,
                                    "grade": "incorrect",
                                    "error_types": ["field" if slot == "A" else "identity"],
                                    "severity": "medium" if slot == "A" else "high",
                                    "evidence_refs": ["E1"],
                                    "basis": "Основание из источника",
                                }
                            )
            result = {"input_sha256": sha(path), **rows}
            directory = root / "judges" / packet["packet_id"]
            immutable(directory / "raw-result.json", encoded(result))
            receipt = {
                "raw_result_sha256": sha(directory / "raw-result.json"),
                "tokens": {"input_tokens": 10, "cached_input_tokens": 7, "output_tokens": 4},
                "wall_elapsed_seconds": 5,
            }
            immutable(directory / "receipt.json", encoded(receipt))
            immutable(directory / "started.json", encoded({"started_at_epoch": 1}))
            immutable(directory / "validated.json", encoded({"result": result, "receipt": receipt}))
            for name, usage in (
                (
                    "pi_verifier",
                    {
                        "input": 10,
                        "output": 3,
                        "cacheRead": 5,
                        "cacheWrite": 0,
                        "reasoning": 2,
                        "totalTokens": 18,
                    },
                ),
                ("native_verifier", receipt["tokens"]),
            ):
                stage = root / "runs" / "meter-only" / name
                immutable(
                    stage / "receipt.json",
                    encoded({"token_usage": usage, "wall_elapsed_seconds": 2}),
                )
                immutable(stage / "started.json", encoded({"started_at_epoch": 1}))
            value = aggregate(root)
            self.assertEqual(value["atoms_compared_per_model"], 12)
            self.assertEqual(
                value["judge_evaluated_per_model"],
                {name: {"atoms": 12, "profile_axes": 9} for name in ("pi", "native")},
            )
            mapping = read(root / "paired-human/unblinding" / (packet["packet_id"] + ".json"))
            expected: dict[str, dict[str, dict[str, int]]] = {
                name: {"atoms": {}, "profile_axes": {}} for name in ("pi", "native")
            }
            for profile in mapping["profiles"]:
                for slot, info in profile["responses"].items():
                    error = "field" if slot == "A" else "identity"
                    for axis, count in (("atoms", 4), ("profile_axes", 3)):
                        counts = expected[info["executor"]][axis]
                        counts[error] = counts.get(error, 0) + count
            self.assertEqual(value["error_types"], expected)
            for name in ("pi", "native"):
                for axis in ("atoms", "profile_axes"):
                    self.assertEqual(
                        value["severities"][name][axis],
                        {
                            "medium" if error == "field" else "high": count
                            for error, count in expected[name][axis].items()
                        },
                    )
            self.assertEqual(value["usage"]["pi"]["completed_usage"]["totalTokens"], 18)
            self.assertEqual(value["usage"]["native"]["completed_usage"], receipt["tokens"])
            self.assertEqual(value["usage"]["judge"]["completed_usage"], receipt["tokens"])
            self.assertEqual(value["usage"]["judge"]["wall_elapsed_seconds"], 5)
            self.assertIsNone(value["usage"]["native"]["transport_retries"])
            self.assertIsNone(value["usage"]["judge"]["cost_usd"])

    def test_failed_partial_usage_and_wall_are_not_full_or_completed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            immutable(directory / "started.json", encoded({"started_at_epoch": 10}))
            immutable(
                directory / "finished.json", encoded({"finished_at_epoch": 610, "exit_code": -9})
            )
            immutable(
                directory / "events.jsonl",
                b'{"type":"turn.completed","usage":{"input_tokens":10,"cached_input_tokens":7,"output_tokens":4}}\n{"type":',
            )
            value = stage_usage([directory])
            self.assertEqual(value["attempts"], 1)
            self.assertEqual(value["completed_receipts"], 0)
            self.assertIsNone(value["completed_usage"])
            self.assertEqual(value["unfinished_observed_usage"]["input_tokens"], 10)
            self.assertIsNone(value["unfinished_full_usage"])
            self.assertEqual(value["wall_elapsed_seconds"], 600)
            self.assertEqual(value["incomplete_event_records"], 1)


class NativeIsolationTests(unittest.TestCase):
    def test_user_only_render_cannot_prove_common_instruction(self) -> None:
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
            with (
                patch(
                    "enrichment_native.subprocess.run",
                    return_value=subprocess.CompletedProcess(
                        [], 0, json.dumps(rendered).encode(), b""
                    ),
                ) as launch,
                self.assertRaisesRegex(ValueError, "доставка"),
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
            self.assertEqual(launch.call_count, 1)
            self.assertFalse((root / "started.json").exists())
            proof = read(next(root.glob("isolation-render-*.json")))
            self.assertEqual(proof["instruction_delivery"], "unverified")
            self.assertFalse((root / "isolation-probe.json").exists())

    def test_supported_options_and_failed_probe_preserve_raw_without_starting_model(self) -> None:
        import subprocess

        from enrichment_native import execute, isolation_options

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "instructions.txt").write_text("rules")
            options = isolation_options(root)
            self.assertNotIn("model_providers.openai.request_max_retries=0", options)
            self.assertNotIn("model_providers.openai.stream_max_retries=0", options)
            self.assertIn('model_provider="openai"', options)
            self.assertIn('developer_instructions="rules"', options)
            self.assertFalse(any(c.startswith("model_instructions_file=") for c in options))
            raw_error = b"reserved built-in provider diagnostic\n"
            with (
                patch(
                    "enrichment_native.subprocess.run",
                    return_value=subprocess.CompletedProcess([], 1, b"partial stdout", raw_error),
                ) as launch,
                self.assertRaises(ValueError),
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
            self.assertEqual(launch.call_count, 1)
            self.assertFalse((root / "started.json").exists())
            proof = read(next(root.glob("isolation-render-*.json")))
            self.assertEqual(Path(proof["stderr_path"]).read_bytes(), raw_error)
            self.assertEqual(sha(Path(proof["stderr_path"])), proof["stderr_sha256"])
            self.assertEqual(Path(proof["stdout_path"]).read_bytes(), b"partial stdout")
            self.assertEqual(Path(proof["stderr_path"]).stat().st_mode & 0o777, 0o600)
            self.assertIsNone(proof["available_tool_inventory"])

    def test_offline_probe_timeout_preserves_partial_raw(self) -> None:
        import subprocess

        from enrichment_native import isolation_probe

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with (
                patch(
                    "enrichment_native.subprocess.run",
                    side_effect=subprocess.TimeoutExpired(
                        "codex", 30, output=b"partial", stderr=b"timeout diagnostic"
                    ),
                ),
                self.assertRaises(ValueError),
            ):
                isolation_probe(root, "task", "rules", root, "gpt-6.1-sol", [])
            proof = read(next(root.glob("isolation-render-*.json")))
            self.assertTrue(proof["timed_out"])
            self.assertEqual(Path(proof["stdout_path"]).read_bytes(), b"partial")
            self.assertEqual(Path(proof["stderr_path"]).read_bytes(), b"timeout diagnostic")

    def test_client_messages_do_not_block_exact_task_delivery(self) -> None:
        import subprocess

        from enrichment_native import isolation_probe

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rendered: list[dict[str, Any]] = [
                {
                    "type": "message",
                    "role": role,
                    "content": [{"type": "input_text", "text": text}],
                }
                for role, text in (
                    ("developer", "mandatory client instructions"),
                    ("developer", "rules"),
                    ("user", "# AGENTS.md instructions: git conventions"),
                    ("user", "task"),
                )
            ]
            with patch(
                "enrichment_native.subprocess.run",
                return_value=subprocess.CompletedProcess([], 0, json.dumps(rendered).encode(), b""),
            ):
                proof = isolation_probe(root, "task", "rules", root, "gpt-6.1-sol", [])
            self.assertEqual(proof["additional_client_messages"], 2)
            self.assertTrue(proof["rendered_messages"][-1]["is_exact_user_prompt"])
            self.assertIsNone(proof["available_tool_inventory"])
            # Extra client messages must not hide a changed final task.
            for changed in ("other task", "rules"):
                rendered[-1]["content"][0]["text"] = changed
                with (
                    patch(
                        "enrichment_native.subprocess.run",
                        return_value=subprocess.CompletedProcess(
                            [], 0, json.dumps(rendered).encode(), b""
                        ),
                    ),
                    self.assertRaises(ValueError),
                ):
                    isolation_probe(root, "task", "rules", root, "gpt-6.1-sol", [])

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
                    "role": "developer",
                    "content": [{"type": "input_text", "text": "rules"}],
                },
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "task"}],
                },
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

    def test_disabled_host_diagnostic_recovery_never_repeats_inference(self) -> None:
        from enrichment_native import execute

        warning = (
            "Code Mode is unavailable because code-mode host is disabled. "
            "Code mode will fail closed; enable `features.code_mode_host` "
            "and install `codex-code-mode-host`."
        )
        for pre_turn, message, repeat in (
            (True, warning, False),
            (False, warning, False),
            (True, "other error", False),
            (True, warning, True),
        ):
            with (
                self.subTest(pre_turn=pre_turn, message=message),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary)
                immutable(root / "started.json", encoded({"started_at_epoch": 1}))
                immutable(root / "finished.json", encoded({"exit_code": 0, "finished_at_epoch": 2}))
                immutable(root / "raw-result.json", b"{}")
                diagnostic = {
                    "type": "item.completed",
                    "item": {"type": "error", "message": message},
                }
                turn = {"type": "turn.started"}
                events = [
                    {"type": "thread.started", "thread_id": "test"},
                    *([diagnostic, turn] if pre_turn else [turn, diagnostic]),
                    *([diagnostic] if repeat else []),
                    {
                        "type": "turn.completed",
                        "usage": {"input_tokens": 1, "output_tokens": 1},
                    },
                ]
                immutable(
                    root / "events.jsonl",
                    b"".join((json.dumps(row) + "\n").encode() for row in events),
                )
                before = sha(root / "events.jsonl"), sha(root / "raw-result.json")
                with patch("enrichment_native.subprocess.run") as launch:
                    if pre_turn and message == warning and not repeat:
                        _, receipt = execute(root, "task", {}, root, system_prompt="rules")
                        self.assertEqual(receipt["tool_calls"], 0)
                        self.assertEqual(receipt["client_diagnostics"], [diagnostic])
                    else:
                        with self.assertRaisesRegex(ValueError, "инструмент"):
                            execute(root, "task", {}, root, system_prompt="rules")
                    launch.assert_not_called()
                self.assertEqual(
                    before, (sha(root / "events.jsonl"), sha(root / "raw-result.json"))
                )

    def test_any_native_tool_item_is_rejected(self) -> None:
        import subprocess

        from enrichment_native import execute

        for kind in ("file_change", "sleep", "collab_agent_tool_call"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                rendered = [
                    {
                        "type": "message",
                        "role": "developer",
                        "content": [{"type": "input_text", "text": "rules"}],
                    },
                    {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": "task"}],
                    },
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
                    kwargs["stdout"].write(
                        b"".join((json.dumps(row) + "\n").encode() for row in events)
                    )
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
