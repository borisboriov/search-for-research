"""Claude CLI transport regressions with mocked subprocess; no real CLI or model call."""

import json
import subprocess
import tempfile
import threading
import time
import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

from sfr_enrichment import native_claude
from sfr_enrichment.common import read, sha
from sfr_enrichment.native_claude import TransportDeferred, deferral_reason, execute, init_event

FIXTURES = Path(__file__).parent / "fixtures" / "claude-cli-2.1.316"
PLACEHOLDER_CWD = "/private/isolated-cwd"
HELP = (
    "Usage: claude [options]\n"
    + "".join(f"  {flag} <x>\n" for flag in native_claude.DOCUMENTED_FLAGS if flag != "--effort")
    + "  --effort <level>   Effort level (low, medium, high, xhigh, max)\n"
).encode()
SCHEMA = {
    "type": "object",
    "properties": {"label": {"type": "string"}},
    "required": ["label"],
    "additionalProperties": False,
}


def fixture_result(name: str, **changes: Any) -> bytes:
    value = json.loads((FIXTURES / name).read_text())
    value.update(changes)
    return json.dumps(value).encode()


def probe_stream(tool_flag: str, cwd: Path, spec: dict[str, Any]) -> bytes:
    """Real 2.1.316 stream with the test cwd; `drop_init` ends the stream before init."""
    kind = "read" if tool_flag else "empty"
    name = f"real-probe-safe-mode-no-chrome-tools-{kind}.jsonl"
    changes = dict(spec)
    drop_init = changes.pop("drop_init", False)
    lines = []
    for line in (FIXTURES / name).read_text().splitlines():
        event = json.loads(line.replace(PLACEHOLDER_CWD, str(cwd.resolve())))
        if event.get("subtype") == "init":
            if drop_init:
                break
            event.update(changes)
        lines.append(json.dumps(event))
    return ("\n".join(lines) + "\n").encode()


class FakeProcess:
    def __init__(self, stdout: bytes, stderr: bytes = b"", code: int = 0, hang: bool = False):
        self.stdout = _Reader(stdout)
        self.stderr = _Reader(stderr)
        self.stdin = _Writer()
        self.code, self.hang, self.killed = code, hang, False

    def wait(self, timeout: float | None = None) -> int:
        if self.hang and not self.killed:
            raise subprocess.TimeoutExpired("claude", timeout or 0)
        return -9 if self.killed else self.code

    def kill(self) -> None:
        self.killed = True


class _Reader:
    def __init__(self, data: bytes) -> None:
        self.data, self.position, self.lock = data, 0, threading.Lock()

    def read(self, size: int = -1) -> bytes:
        with self.lock:
            end = len(self.data) if size < 0 else self.position + size
            block = self.data[self.position : end]
            self.position += len(block)
            return block

    def readline(self) -> bytes:
        with self.lock:
            end = self.data.find(b"\n", self.position)
            end = len(self.data) if end < 0 else end + 1
            block = self.data[self.position : end]
            self.position = end
            return block

    def close(self) -> None:
        pass


class _Writer:
    def __init__(self) -> None:
        self.data = b""

    def write(self, data: bytes) -> int:
        self.data += data
        return len(data)

    def close(self) -> None:
        pass


class ClaudeFakes:
    """Scripted CLI: probe/control return stream-json, the task returns one result."""

    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd
        self.results: list[Any] = []
        self.probe: dict[str, Any] = {}
        self.control: dict[str, Any] = {}
        self.streams: dict[str, str] = {}
        self.version = b"2.1.316 (Claude Code)\n"
        self.help = HELP
        self.calls: list[list[str]] = []
        self.processes: list[FakeProcess] = []
        self.popen_kwargs: list[dict[str, Any]] = []

    def run(self, command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        self.calls.append(command)
        output = self.version if command[1] == "--version" else self.help
        return subprocess.CompletedProcess(command, 0, stdout=output, stderr=b"")

    def popen(self, command: list[str], **kwargs: Any) -> FakeProcess:
        self.calls.append(command)
        self.popen_kwargs.append(kwargs)
        output_format = command[command.index("--output-format") + 1]
        tools = command[command.index("--tools") + 1]
        if output_format == "stream-json":
            label = "control" if tools else "probe"
            if label in self.streams:
                text = (FIXTURES / self.streams[label]).read_text()
                stream = text.replace(PLACEHOLDER_CWD, str(Path(kwargs["cwd"]).resolve())).encode()
            else:
                spec = self.control if tools else self.probe
                stream = probe_stream(tools, Path(kwargs["cwd"]), spec)
            process = FakeProcess(stream)
        else:
            item = self.results.pop(0)
            process = item if isinstance(item, FakeProcess) else FakeProcess(item)
        self.processes.append(process)
        return process

    @contextmanager
    def active(self, executable: Path) -> Iterator["ClaudeFakes"]:
        with (
            patch("sfr_enrichment.native_claude.shutil.which", return_value=str(executable)),
            patch("sfr_enrichment.native_claude.subprocess.run", side_effect=self.run),
            patch("sfr_enrichment.native_claude.subprocess.Popen", side_effect=self.popen),
            patch.dict("os.environ", {}, clear=False) as environment,
        ):
            for name in native_claude.PAID_KEY_ENV:
                environment.pop(name, None)
            yield self


class ClaudeTransportTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)
        self.cwd = self.tmp / "empty-cwd"
        self.cwd.mkdir()
        self.binary = self.tmp / "claude-binary"
        self.binary.write_bytes(b"fixture executable")
        self.fakes = ClaudeFakes(self.cwd)

    def make_proof(self, name: str = "proof", **changes: Any) -> Path:
        arguments: dict[str, Any] = {
            "system_prompt": "Synthetic shared rubric",
            "schema_text": json.dumps(SCHEMA),
            "model": "claude-haiku-5-5",
            "effort": "high",
            "context": {"synthetic": True},
        } | changes
        with self.fakes.active(self.binary):
            return native_claude.run_isolation_check(self.tmp / name, **arguments)

    def run_execute(self, directory: Path | None = None, **changes: Any) -> tuple[Path, Any]:
        if not (self.tmp / "proof" / native_claude.PROOF).exists():
            self.make_proof()
        arguments: dict[str, Any] = {
            "isolation_proof_dir": self.tmp / "proof",
            "model": "claude-haiku-5-5",
            "effort": "high",
            "system_prompt": "Synthetic shared rubric",
            "timeout_seconds": 300,
            "max_output_file_bytes": 65536,
            "deadline_epoch": time.time() + 3600,
        } | changes
        with self.fakes.active(self.binary):
            return execute(
                directory or self.tmp / "job",
                "Synthetic task prompt",
                SCHEMA,
                self.cwd,
                **arguments,
            )

    def test_success_records_requested_observed_usage_cost_and_exact_flags(self) -> None:
        self.fakes.results.append(fixture_result("synthetic-result-success.json"))
        raw, receipt = self.run_execute(expected_cli_version="2.1.316 (Claude Code)")
        self.assertEqual(read(raw)["label"], "supported")
        self.assertEqual(receipt["transport"], "claude_cli")
        self.assertEqual(
            (receipt["requested_model"], receipt["requested_effort"]), ("claude-haiku-5-5", "high")
        )
        self.assertEqual(receipt["model"], "claude-haiku-5-5")
        self.assertIsNone(receipt["effort"])
        self.assertEqual(receipt["cost_usd"], 0.0123)
        self.assertEqual(
            receipt["tokens"],
            {
                "input_tokens": 1200,
                "output_tokens": 85,
                "cache_read_input_tokens": 300,
                "cache_creation_input_tokens": 40,
            },
        )
        self.assertEqual((receipt["num_turns"], receipt["is_error"]), (1, False))
        self.assertEqual(receipt["cli_version"], "2.1.316 (Claude Code)")
        self.assertEqual(receipt["tool_registry"], ["StructuredOutput"])
        task = self.fakes.calls[-1]
        self.assertEqual(task[:2], ["claude", "-p"])
        for flag in ("--safe-mode", "--strict-mcp-config", "--no-session-persistence"):
            self.assertIn(flag, task)
        self.assertNotIn("--bare", task)
        self.assertEqual(task[task.index("--setting-sources") + 1], "")
        self.assertEqual(task[task.index("--tools") + 1], "")
        self.assertEqual(task[task.index("--output-format") + 1], "json")
        self.assertEqual(task[task.index("--max-turns") + 1], "1")
        self.assertEqual(task[task.index("--model") + 1], "claude-haiku-5-5")
        self.assertEqual(task[task.index("--effort") + 1], "high")
        self.assertEqual(task[task.index("--system-prompt") + 1], "Synthetic shared rubric")
        self.assertEqual(json.loads(task[task.index("--json-schema") + 1]), SCHEMA)
        self.assertNotIn("Synthetic task prompt", task)
        self.assertEqual(self.fakes.processes[-1].stdin.data, b"Synthetic task prompt")
        self.assertEqual(self.fakes.popen_kwargs[-1]["cwd"], self.cwd)
        self.assertEqual(sum("json" in c[-2:] for c in self.fakes.calls), 1)
        probes = [c for c in self.fakes.calls if "stream-json" in c]
        self.assertEqual([c[c.index("--tools") + 1] for c in probes], ["", "Read"])
        job = self.tmp / "job"
        self.assertEqual(
            read(job / "isolation-control.json")["tools"], ["Read", "StructuredOutput"]
        )
        self.assertEqual(sha(job / "isolation-probe.json"), receipt["isolation_probe_sha256"])
        self.assertEqual(
            sha(self.tmp / "proof" / native_claude.PROOF), receipt["isolation_proof_sha256"]
        )
        launches = len(self.fakes.calls)
        _, again = self.run_execute()
        self.assertEqual((len(self.fakes.calls), again), (launches, receipt))

    def test_real_error_form_is_technical_failure_not_deferral(self) -> None:
        self.fakes.results.append(
            FakeProcess(fixture_result("real-result-bare-auth-error.json"), code=1)
        )
        with self.assertRaisesRegex(ValueError, "не завершил") as caught:
            self.run_execute()
        self.assertNotIsInstance(caught.exception, TransportDeferred)
        self.assertFalse((self.tmp / "job" / "receipt.json").exists())
        self.assertEqual(read(self.tmp / "job" / "finished.json")["exit_code"], 1)
        with self.assertRaisesRegex(ValueError, "не завершил"):
            self.run_execute()

    def test_rate_limit_and_overload_before_output_are_deferred(self) -> None:
        cases = (
            (fixture_result("synthetic-result-rate-limit.json"), "rate_limited"),
            (
                fixture_result("synthetic-result-rate-limit.json", api_error_status=529),
                "overloaded",
            ),
            (
                fixture_result(
                    "synthetic-result-rate-limit.json",
                    api_error_status=None,
                    result="Claude usage limit reached; synthetic",
                ),
                "rate_limited",
            ),
        )
        for index, (stdout, reason) in enumerate(cases):
            with self.subTest(reason=reason, index=index):
                self.fakes.results.append(FakeProcess(stdout, code=1))
                with self.assertRaises(TransportDeferred) as caught:
                    self.run_execute(self.tmp / f"deferred-{index}")
                self.assertEqual(caught.exception.reason, reason)
                self.assertIn("stdout_sha256", caught.exception.details)

    def test_deferral_requires_no_model_output(self) -> None:
        value = json.loads(fixture_result("synthetic-result-rate-limit.json"))
        self.assertEqual(deferral_reason(value), "rate_limited")
        produced = value | {"usage": value["usage"] | {"output_tokens": 7}}
        self.assertIsNone(deferral_reason(produced))
        auth = json.loads((FIXTURES / "real-result-bare-auth-error.json").read_text())
        self.assertIsNone(deferral_reason(auth))
        self.assertIsNone(deferral_reason(value | {"is_error": False}))

    def test_output_byte_cap_and_timeout_are_saved_without_retry(self) -> None:
        self.fakes.results.append(FakeProcess(b"x" * 70000))
        with self.assertRaisesRegex(ValueError, "stream cap"):
            self.run_execute(self.tmp / "cap")
        self.assertTrue(read(self.tmp / "cap" / "finished.json")["output_cap_exceeded"])
        self.fakes.results.append(FakeProcess(b"", hang=True))
        with self.assertRaisesRegex(ValueError, "timeout"):
            self.run_execute(self.tmp / "timeout")
        self.assertTrue(read(self.tmp / "timeout" / "finished.json")["timed_out"])
        launches = len(self.fakes.calls)
        with self.assertRaisesRegex(ValueError, "прервана"):
            self.run_execute(self.tmp / "timeout")
        self.assertEqual(len(self.fakes.calls), launches)

    def test_missing_init_or_wrong_registry_refuses_the_proof(self) -> None:
        refusals: tuple[tuple[dict[str, Any], dict[str, Any], str], ...] = (
            ({"drop_init": True}, {}, "нет события system/init"),
            ({"tools": ["Bash"]}, {}, "лишние: Bash"),
            ({"tools": []}, {}, "отсутствуют: StructuredOutput"),
            ({"tools": ["StructuredOutput", "StructuredOutput"]}, {}, "registry"),
            ({"mcp_servers": [{"name": "x", "status": "connected"}]}, {}, "MCP-серверы.*: x"),
            ({"apiKeySource": "ANTHROPIC_API_KEY"}, {}, "платный API"),
            ({"cwd": "/elsewhere"}, {}, "изолированном cwd"),
            ({}, {"tools": []}, "отсутствуют: Read"),
        )
        for index, (probe, control, message) in enumerate(refusals):
            with self.subTest(message=message, index=index):
                self.fakes.probe, self.fakes.control = probe, control
                directory = self.tmp / f"refused-{index}"
                with self.assertRaisesRegex(ValueError, message):
                    self.make_proof(directory.name)
                self.assertFalse((directory / native_claude.PROOF).exists())
                self.assertTrue(list(directory.glob("isolation-*-refused-*.json")))
        self.assertFalse(any(c[-2:] == ["--output-format", "json"] for c in self.fakes.calls))

    def test_real_safe_mode_registry_is_refused_by_exact_tool_names(self) -> None:
        self.fakes.streams = {
            "probe": "real-probe-safe-mode-tools-empty.jsonl",
            "control": "real-probe-safe-mode-tools-read.jsonl",
        }
        with self.assertRaisesRegex(ValueError, "лишние: mcp__claude-in-chrome__browser_batch"):
            self.make_proof("safe-mode")
        refused = read(next((self.tmp / "safe-mode").glob("isolation-probe-refused-*.json")))
        self.assertNotIn("StructuredOutput", refused["refusal"].split("лишние:")[1])
        self.assertIn("--safe-mode", self.fakes.calls[-1])
        self.assertEqual(
            self.fakes.calls[-1][self.fakes.calls[-1].index("--setting-sources") + 1], ""
        )
        _, init, _ = init_event((FIXTURES / "real-probe-safe-mode-tools-empty.jsonl").read_bytes())
        self.assertEqual(init["apiKeySource"], "none")
        self.assertEqual(init["mcp_servers"][0]["name"], "claude-in-chrome")

    def test_real_no_chrome_registry_passes_with_only_the_output_channel(self) -> None:
        self.fakes.streams = {
            "probe": "real-probe-safe-mode-no-chrome-tools-empty.jsonl",
            "control": "real-probe-safe-mode-no-chrome-tools-read.jsonl",
        }
        summary = read(self.make_proof("no-chrome"))
        self.assertEqual(summary["probe_tools"], ["StructuredOutput"])
        self.assertEqual(summary["control_tools"], ["Read", "StructuredOutput"])
        command = [c for c in self.fakes.calls if "stream-json" in c][-1]
        self.assertIn("--no-chrome", command)
        self.assertNotIn("--bare", command)

    def test_stored_proof_is_rechecked_and_bound_to_flags_and_cli(self) -> None:
        proof = self.make_proof()
        verified = native_claude.verify_isolation_proof(
            proof.parent,
            model="claude-haiku-5-5",
            effort="high",
            cli_version="2.1.316 (Claude Code)",
        )
        self.assertEqual(verified["isolation_proof_sha256"], sha(proof))
        for changes, message in (
            ({"model": "claude-other"}, "другим флагам"),
            ({"effort": "low"}, "другим флагам"),
            ({"cli_version": "2.1.317 (Claude Code)"}, "другим флагам"),
        ):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, message):
                native_claude.verify_isolation_proof(
                    proof.parent,
                    **{
                        "model": "claude-haiku-5-5",
                        "effort": "high",
                        "cli_version": "2.1.316 (Claude Code)",
                    }
                    | changes,
                )
        self.fakes.version = b"2.1.317 (Claude Code)\n"
        with self.assertRaisesRegex(ValueError, "другим флагам"):
            self.run_execute(self.tmp / "newer-cli")
        self.assertFalse((self.tmp / "newer-cli" / "started.json").exists())
        self.fakes.version = b"2.1.316 (Claude Code)\n"
        saved = proof.parent / read(proof.parent / "isolation-probe.json")["stdout_path"]
        saved.write_bytes(
            saved.read_bytes().replace(b'"tools": ["StructuredOutput"]', b'"tools": ["Bash"]')
        )
        with self.assertRaisesRegex(ValueError, "файлы изменены"):
            self.run_execute(self.tmp / "tampered")

    def test_init_parser_reads_real_stream_and_rejects_ambiguous_output(self) -> None:
        for name, tools in (
            ("tools-empty", []),
            ("tools-read", ["Read"]),
            ("safe-mode-no-chrome-tools-empty", ["StructuredOutput"]),
            ("safe-mode-no-chrome-tools-read", ["Read", "StructuredOutput"]),
        ):
            _, init, before = init_event((FIXTURES / f"real-probe-{name}.jsonl").read_bytes())
            self.assertEqual((init["tools"], init["mcp_servers"]), (tools, []))
            self.assertEqual(init["claude_code_version"], "2.1.316")
            self.assertIn("system/ui_invalidate", before)
        with self.assertRaisesRegex(ValueError, "нет события"):
            init_event(b"")
        with self.assertRaisesRegex(ValueError, "Некорректная строка"):
            init_event(b"not json\n" + (FIXTURES / "real-probe-tools-empty.jsonl").read_bytes())
        assistant = json.dumps({"type": "assistant", "message": {}}).encode() + b"\n"
        with self.assertRaisesRegex(ValueError, "Активность модели"):
            init_event(assistant + (FIXTURES / "real-probe-tools-empty.jsonl").read_bytes())

    def test_unsupported_configuration_is_rejected_explicitly(self) -> None:
        self.make_proof()
        self.fakes.calls.clear()
        with self.assertRaisesRegex(ValueError, "effort"):
            self.run_execute(effort="ultra")
        with self.assertRaisesRegex(ValueError, "model"):
            self.run_execute(model="--dangerously-skip-permissions")
        self.assertEqual(self.fakes.calls, [])
        self.fakes.help = HELP.replace(b"--safe-mode", b"--other")
        with self.assertRaisesRegex(ValueError, "--safe-mode"):
            self.run_execute(self.tmp / "no-safe-mode")
        self.fakes.help = HELP
        with self.assertRaisesRegex(ValueError, "Версия Claude CLI"):
            self.run_execute(self.tmp / "version", expected_cli_version="9.9.9 (Claude Code)")
        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "x"}),
            patch("sfr_enrichment.native_claude.subprocess.Popen") as launch,
        ):
            with self.assertRaisesRegex(ValueError, "платный API"):
                execute(
                    self.tmp / "paid",
                    "p",
                    SCHEMA,
                    self.cwd,
                    model="claude-haiku-5-5",
                    effort="high",
                    system_prompt="s",
                    timeout_seconds=1,
                    max_output_file_bytes=1,
                    isolation_proof_dir=self.tmp / "proof",
                )
            launch.assert_not_called()
        (self.cwd / "leftover").write_text("x")
        with self.assertRaisesRegex(ValueError, "пустым"):
            self.run_execute(self.tmp / "dirty")

    def test_fixture_provenance_marks_synthetic_forms_and_hashes(self) -> None:
        provenance = read(FIXTURES / "provenance.json")
        files = provenance["files"]
        self.assertEqual(set(files), {p.name for p in FIXTURES.iterdir()} - {"provenance.json"})
        for name, entry in files.items():
            self.assertEqual(sha(FIXTURES / name), entry["sha256"])
            self.assertEqual(entry["kind"], "synthetic" if name.startswith("synthetic") else "real")
            text = (FIXTURES / name).read_text()
            self.assertNotIn("/tmp/", text)
            self.assertNotIn("/Users/", text)

    def test_unknown_outcome_of_started_attempt_is_not_retried(self) -> None:
        self.make_proof()
        self.fakes.calls.clear()
        directory = self.tmp / "unknown"
        directory.mkdir()
        (directory / "started.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "неизвестен"):
            self.run_execute(directory)
        self.assertEqual(self.fakes.calls, [])


if __name__ == "__main__":
    unittest.main()
