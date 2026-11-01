"""Claude Code CLI transport for frozen NIR B/C jobs, beside ``codex exec`` (protocol v2).

Однократный ``claude -p`` по существующей подписке: без инструментов и MCP, без
сохранения сессии, в пустом cwd, prompt через stdin, с теми же лимитами времени
и байт потоков, что у codex-транспорта. ``native.py`` и его гарантии не меняются.
Изоляция проверяется событием ``system/init`` в stream-json до задания, с
положительным контролем одного разрешённого инструмента. Неизвестный исход
не повторяется автоматически; сырые ответы неизменяемы.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from sfr_enrichment.batch import encoded, immutable
from sfr_enrichment.common import read, sha
from sfr_enrichment.native import deadline_timeout

TRANSPORT = "claude_cli"
EXECUTABLE = "claude"
EFFORTS = ("low", "medium", "high", "xhigh", "max")
# Каждый флаг должен быть описан в `claude --help` установленной версии.
DOCUMENTED_FLAGS = (
    "--print",
    "--bare",
    "--tools",
    "--strict-mcp-config",
    "--no-session-persistence",
    "--system-prompt",
    "--json-schema",
    "--output-format",
    "--model",
    "--effort",
    "--verbose",
)
# Принят CLI 2.1.316, но не показан в --help; отказ CLI при его отсутствии явный.
HIDDEN_FLAGS = ("--max-turns",)
# Ключ API означает оплачиваемый API, а не существующую подписку.
PAID_KEY_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
PROBE_PROMPT = "Isolation probe: no task. Do not answer."
CONTROL_TOOL = "Read"
PROBE_TIMEOUT_SECONDS = 30
PROBE_STREAM_CAP = 1024 * 1024
DEFERRAL_STATUSES = {429: "rate_limited", 529: "overloaded"}
DEFERRAL_TEXT = re.compile(
    r"rate[ _-]?limit|overloaded|usage limit|limit reached|too many requests", re.IGNORECASE
)
REGISTRY_CONTRACT = (
    "stream-json system/init tools and mcp_servers are the advertised registry; "
    "process terminated after init; not an API interception"
)


class TransportDeferred(ValueError):
    """Rate-limit/overload before any model output: slot is not consumed, run must stop."""

    def __init__(self, reason: str, details: dict[str, Any]) -> None:
        super().__init__(f"Claude CLI transport deferred ({reason}) before model output")
        self.reason = reason
        self.details = details


def checked_value(value: Any, field: str) -> str:
    """Values travel as separate argv items; a leading dash would be parsed as a flag."""
    if not isinstance(value, str) or not value.strip() or value.startswith("-"):
        raise ValueError(f"Неподдерживаемое значение Claude CLI: {field}")
    return value


def task_flags(
    *, system_prompt: str, schema_text: str, model: str, effort: str, tools: str = ""
) -> list[str]:
    """Exact isolation flags shared by the probe, the control and the task."""
    return [
        "--bare",
        "--tools",
        tools,
        "--strict-mcp-config",
        "--no-session-persistence",
        "--system-prompt",
        system_prompt,
        "--json-schema",
        schema_text,
        "--model",
        model,
        "--effort",
        effort,
        "--max-turns",
        "1",
    ]


def command(flags: list[str], output_format: str) -> list[str]:
    stream = ["--verbose"] if output_format == "stream-json" else []
    return [EXECUTABLE, "-p", *flags, "--output-format", output_format, *stream]


def paid_key_guard() -> list[str]:
    """Refuse paid API keys; return names (never values) of inherited client variables."""
    if any(os.environ.get(name) for name in PAID_KEY_ENV):
        raise ValueError("Claude CLI: ключ API означает платный API, не подписку; запуск запрещён")
    return sorted(name for name in os.environ if name.startswith(("CLAUDE", "ANTHROPIC")))


def require_empty_directory(path: Path) -> None:
    if not path.is_dir() or any(path.iterdir()):
        raise ValueError("Изолированный cwd Claude CLI должен существовать и быть пустым")


def installed_cli_version(deadline_epoch: float | None = None) -> str:
    result = subprocess.run(
        [EXECUTABLE, "--version"],
        capture_output=True,
        timeout=deadline_timeout(PROBE_TIMEOUT_SECONDS, deadline_epoch),
        check=False,
    )
    if result.returncode != 0:
        raise ValueError("Claude CLI --version завершился с ошибкой")
    return result.stdout.decode().strip()


def cli_capabilities(
    directory: Path, effort: str, deadline_epoch: float | None = None
) -> dict[str, Any]:
    """Record `claude --version`/`--help` and refuse a CLI lacking any required flag."""
    executable = shutil.which(EXECUTABLE)
    if not executable:
        raise ValueError("Claude CLI не найден в PATH")
    outputs: dict[str, bytes] = {}
    for name in ("version", "help"):
        result = subprocess.run(
            [EXECUTABLE, f"--{name}"],
            capture_output=True,
            timeout=deadline_timeout(PROBE_TIMEOUT_SECONDS, deadline_epoch),
            check=False,
        )
        if result.returncode != 0:
            raise ValueError(f"Claude CLI --{name} завершился с ошибкой")
        outputs[name] = result.stdout
        immutable(directory / f"cli-{name}.txt", result.stdout)
    version = outputs["version"].decode().strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+ \(Claude Code\)", version):
        raise ValueError("Неизвестный формат claude --version")
    text = outputs["help"].decode()
    missing = [flag for flag in DOCUMENTED_FLAGS if not re.search(re.escape(flag) + r"\b", text)]
    if missing:
        raise ValueError("Claude CLI не поддерживает нужные флаги: " + ", ".join(missing))
    levels = re.search(r"--effort <level>[^(]*\(([^)]*)\)", text)
    if levels is None or effort not in [level.strip() for level in levels[1].split(",")]:
        raise ValueError("Claude CLI не поддерживает запрошенный effort")
    binary = Path(executable).resolve()
    return {
        "cli_version": version,
        "cli_version_sha256": sha(directory / "cli-version.txt"),
        "cli_help_sha256": sha(directory / "cli-help.txt"),
        "cli_binary_sha256": sha(binary),
        "documented_flags_checked": list(DOCUMENTED_FLAGS),
        "hidden_flags_unverified_by_help": list(HIDDEN_FLAGS),
    }


def init_event(stdout: bytes) -> tuple[int, dict[str, Any], list[str]]:
    """Strictly parse stream-json up to the first system/init event.

    A missing event, an invalid line before it or model activity before it is an
    error: an empty registry is never inferred from unparsed output.
    """
    kinds: list[str] = []
    for index, line in enumerate(stdout.split(b"\n")):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            raise ValueError("Некорректная строка stream-json до system/init") from None
        if not isinstance(event, dict):
            raise ValueError("Некорректное событие stream-json до system/init")
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            return index, event, kinds
        if kind in ("assistant", "user", "result", "stream_event"):
            raise ValueError("Активность модели до system/init: изоляция не доказана")
        kinds.append(f"{kind}/{event.get('subtype')}" if "subtype" in event else str(kind))
    raise ValueError("Не доказана изоляция Claude CLI: нет события system/init")


def registry_check(init: dict[str, Any], expected_tools: list[str], cwd: Path) -> dict[str, Any]:
    tools, servers = init.get("tools"), init.get("mcp_servers")
    if not isinstance(tools, list) or tools != expected_tools:
        raise ValueError("Claude CLI registry инструментов не совпадает с ожидаемым")
    if not isinstance(servers, list) or servers:
        raise ValueError("Claude CLI объявил MCP-серверы при --strict-mcp-config")
    if init.get("apiKeySource") != "none":
        raise ValueError("Claude CLI использует ключ API: платный API, не подписка")
    if not isinstance(init.get("cwd"), str) or Path(init["cwd"]).resolve() != cwd.resolve():
        raise ValueError("Claude CLI запущен не в изолированном cwd")
    version = init.get("claude_code_version")
    if not isinstance(version, str) or not version:
        raise ValueError("Claude CLI init не сообщил версию")
    listed = {name: init.get(name) for name in ("skills", "agents", "slash_commands", "plugins")}
    return {
        "tools": tools,
        "mcp_servers": servers,
        "apiKeySource": init["apiKeySource"],
        "init_model": init.get("model"),
        "claude_code_version": version,
        "permissionMode": init.get("permissionMode"),
        "listed_not_tools": {
            name: {
                "count": len(value) if isinstance(value, list) else None,
                "sha256": hashlib.sha256(encoded(value)).hexdigest(),
            }
            for name, value in listed.items()
        },
    }


def isolation_probe(
    directory: Path,
    label: str,
    flags: list[str],
    cwd: Path,
    expected_tools: list[str],
    *,
    system_prompt: str,
    schema_text: str,
    deadline_epoch: float | None = None,
) -> dict[str, Any]:
    """Run the exact flags in stream-json, stop at system/init and save the proof.

    The fixed harmless prompt replaces the task; the process is terminated after
    init, before any answer is read. A request may already have started, so usage
    of the probe is unknown rather than zero.
    """
    probe_command = command(flags, "stream-json")
    started_at = time.time()
    timeout = deadline_timeout(PROBE_TIMEOUT_SECONDS, deadline_epoch)
    process = subprocess.Popen(
        probe_command,
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    found = threading.Event()
    chunks: dict[str, list[bytes]] = {"stdout": [], "stderr": []}
    exceeded = threading.Event()

    def lines(stream: Any) -> None:
        size = 0
        for line in iter(stream.readline, b""):
            size += len(line)
            if size > PROBE_STREAM_CAP:
                exceeded.set()
                break
            chunks["stdout"].append(line)
            event = line.strip()
            if event.startswith(b"{") and b'"init"' in event:
                try:
                    value = json.loads(event)
                except json.JSONDecodeError:
                    continue
                if value.get("type") == "system" and value.get("subtype") == "init":
                    break
        found.set()

    def errors(stream: Any) -> None:
        size = 0
        while block := stream.read(65536):
            size += len(block)
            if size > PROBE_STREAM_CAP:
                exceeded.set()
                break
            chunks["stderr"].append(block)

    def feed() -> None:
        assert process.stdin is not None
        try:
            process.stdin.write(PROBE_PROMPT.encode())
            process.stdin.close()
        except BrokenPipeError:
            pass

    workers = [
        threading.Thread(target=lines, args=(process.stdout,), daemon=True),
        threading.Thread(target=errors, args=(process.stderr,), daemon=True),
        threading.Thread(target=feed, daemon=True),
    ]
    for worker in workers:
        worker.start()
    timed_out = not found.wait(timeout)
    process.kill()
    exit_code = process.wait()
    for worker in workers:
        worker.join(timeout=5)
    for stream in (process.stdin, process.stdout, process.stderr):
        if stream is not None:
            stream.close()
    stdout, stderr = b"".join(chunks["stdout"]), b"".join(chunks["stderr"])
    proof: dict[str, Any] = {
        "label": label,
        "transport": TRANSPORT,
        "command_sha256": hashlib.sha256(encoded(probe_command)).hexdigest(),
        "expected_tools": expected_tools,
        "probe_prompt_sha256": hashlib.sha256(PROBE_PROMPT.encode()).hexdigest(),
        "instruction_sha256": hashlib.sha256(system_prompt.encode()).hexdigest(),
        "schema_sha256": hashlib.sha256(schema_text.encode()).hexdigest(),
        "exit_code": exit_code,
        "timed_out": timed_out,
        "stream_cap_exceeded": exceeded.is_set(),
        "terminated_after_init": False,
        "started_at_epoch": started_at,
        "wall_elapsed_seconds": time.time() - started_at,
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        "registry_contract": REGISTRY_CONTRACT,
        "probe_usage": "unknown; terminated after init, a request may have started",
    }
    for stream_name, data in (("stdout", stdout), ("stderr", stderr)):
        name = f"isolation-{label}-{stream_name}-{proof[stream_name + '_sha256']}.bin"
        immutable(directory / name, data)
        (directory / name).chmod(0o600)
        proof[stream_name + "_path"] = name
    try:
        index, init, kinds = init_event(stdout)
        proof.update(init_line_index=index, events_before_init=kinds)
        proof.update(registry_check(init, expected_tools, cwd))
    except ValueError as exc:
        proof["refusal"] = str(exc)
        immutable(
            directory
            / f"isolation-{label}-refused-{hashlib.sha256(encoded(proof)).hexdigest()}.json",
            encoded(proof),
        )
        raise
    proof["terminated_after_init"] = True
    immutable(directory / f"isolation-{label}.json", encoded(proof))
    return proof


def bounded_run(
    command_line: list[str],
    prompt: bytes,
    output: Any,
    errors: Any,
    timeout: float,
    cap: int,
    cwd: Path,
) -> subprocess.CompletedProcess[bytes]:
    """Same stream cap discipline as native.bounded_output_run, with the isolated cwd."""
    process = subprocess.Popen(
        command_line,
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    exceeded = threading.Event()

    def drain(stream: Any, destination: Any) -> None:
        size = 0
        while block := stream.read(65536):
            if size + len(block) > cap:
                exceeded.set()
                process.kill()
                break
            destination.write(block)
            destination.flush()
            size += len(block)

    def feed() -> None:
        assert process.stdin is not None
        try:
            process.stdin.write(prompt)
            process.stdin.close()
        except BrokenPipeError:
            pass

    workers = [
        threading.Thread(target=drain, args=pair, daemon=True)
        for pair in ((process.stdout, output), (process.stderr, errors))
    ] + [threading.Thread(target=feed, daemon=True)]
    for worker in workers:
        worker.start()
    try:
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise
    finally:
        for worker in workers:
            worker.join(timeout=5)
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None:
                stream.close()
    if exceeded.is_set():
        raise ValueError("Claude output stream cap: saved partial; no automatic retry")
    return subprocess.CompletedProcess(command_line, code)


def no_model_output(result: dict[str, Any]) -> bool:
    usage = result.get("usage")
    model_usage = result.get("modelUsage")
    return (
        isinstance(usage, dict)
        and usage.get("output_tokens") in (0, None)
        and (
            model_usage in ({}, None)
            or (
                isinstance(model_usage, dict)
                and all(
                    isinstance(entry, dict) and entry.get("outputTokens") in (0, None)
                    for entry in model_usage.values()
                )
            )
        )
        and result.get("structured_output") is None
    )


def deferral_reason(result: dict[str, Any]) -> str | None:
    """Only a rate-limit/overload API refusal before any model output defers a job."""
    if result.get("is_error") is not True or not no_model_output(result):
        return None
    status = result.get("api_error_status")
    if status in DEFERRAL_STATUSES:
        return DEFERRAL_STATUSES[status]
    text = result.get("result")
    if (
        result.get("terminal_reason") == "api_error"
        and isinstance(text, str)
        and DEFERRAL_TEXT.search(text)
    ):
        return "overloaded" if "overload" in text.lower() else "rate_limited"
    return None


def parsed_result(stdout: bytes) -> dict[str, Any]:
    try:
        result = json.loads(stdout)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("Claude CLI не вернул JSON-результат; нужен разбор") from None
    if not isinstance(result, dict) or result.get("type") != "result":
        raise ValueError("Неизвестный контракт результата Claude CLI")
    return result


def token_usage(result: dict[str, Any]) -> dict[str, Any]:
    usage = result.get("usage")
    if not isinstance(usage, dict):
        raise ValueError("Claude CLI не сообщил usage")
    return {
        key: usage.get(key)
        for key in (
            "input_tokens",
            "output_tokens",
            "cache_read_input_tokens",
            "cache_creation_input_tokens",
        )
    }


def observed_model(result: dict[str, Any]) -> str | None:
    model_usage = result.get("modelUsage")
    if isinstance(model_usage, dict) and len(model_usage) == 1:
        (name,) = model_usage
        return name if isinstance(name, str) and name else None
    return None


def execute(
    directory: Path,
    prompt: str,
    output_schema: dict[str, Any],
    cwd: Path,
    *,
    model: str,
    effort: str,
    system_prompt: str,
    timeout_seconds: int,
    max_output_file_bytes: int,
    deadline_epoch: float | None = None,
    expected_cli_version: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    """One real Claude CLI attempt; a saved receipt is returned without a new call."""
    checked_value(model, "model")
    if effort not in EFFORTS:
        raise ValueError("Неподдерживаемый effort Claude CLI")
    checked_value(system_prompt, "system_prompt")
    for cap in (timeout_seconds, max_output_file_bytes):
        if type(cap) is not int or cap <= 0:
            raise ValueError("Claude CLI caps must be positive integers")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    requested = {"transport": TRANSPORT, "model": model, "effort": effort}
    prompt_bytes = prompt.encode()
    schema_bytes = encoded(output_schema)
    immutable(directory / "requested-config.json", encoded(requested))
    immutable(directory / "prompt.txt", prompt_bytes)
    immutable(directory / "schema.json", schema_bytes)
    immutable(directory / "instructions.txt", system_prompt.encode())
    receipt_path = directory / "receipt.json"
    if receipt_path.exists():
        value = read(receipt_path)
        if (value.get("requested_model"), value.get("requested_effort")) != (model, effort):
            raise ValueError("Сохранённый Claude runtime другого задания")
        if sha(directory / "raw-result.json") != value["raw_result_sha256"]:
            raise ValueError("Сырой ответ изменён")
        return directory / "raw-result.json", value
    started = directory / "started.json"
    finished_path = directory / "finished.json"
    if started.exists() and not finished_path.exists():
        raise ValueError("Исход Claude CLI-попытки неизвестен: автоматический повтор запрещён")
    schema_text = schema_bytes.decode()
    flags = task_flags(
        system_prompt=system_prompt, schema_text=schema_text, model=model, effort=effort
    )
    if not started.exists():
        environment = paid_key_guard()
        require_empty_directory(cwd)
        capabilities = cli_capabilities(directory, effort, deadline_epoch)
        if expected_cli_version is not None and capabilities["cli_version"] != expected_cli_version:
            raise ValueError("Версия Claude CLI отличается от разрешённой")
        probes = {}
        for label, tools in (("probe", ""), ("control", CONTROL_TOOL)):
            probes[label] = isolation_probe(
                directory,
                label,
                task_flags(
                    system_prompt=system_prompt,
                    schema_text=schema_text,
                    model=model,
                    effort=effort,
                    tools=tools,
                ),
                cwd,
                [tools] if tools else [],
                system_prompt=system_prompt,
                schema_text=schema_text,
                deadline_epoch=deadline_epoch,
            )
        if not capabilities["cli_version"].startswith(probes["probe"]["claude_code_version"] + " "):
            raise ValueError("Версия Claude CLI в init не совпадает с claude --version")
        require_empty_directory(cwd)
        task_command = command(flags, "json")
        immutable(directory / "command.json", encoded(task_command))
        immutable(
            started,
            encoded(
                {
                    "started_at_epoch": time.time(),
                    "prompt_sha256": hashlib.sha256(prompt_bytes).hexdigest(),
                    "mode": "claude -p bare no-tools strict-mcp no-session-persistence json",
                    "requested_config": requested,
                    "cli": capabilities,
                    "inherited_client_environment_names": environment,
                    "isolation_probe_sha256": sha(directory / "isolation-probe.json"),
                    "isolation_control_sha256": sha(directory / "isolation-control.json"),
                }
            ),
        )
        with (
            (directory / "stdout.json").open("xb") as output,
            (directory / "stderr.log").open("xb") as errors,
        ):
            try:
                completed = bounded_run(
                    task_command,
                    prompt_bytes,
                    output,
                    errors,
                    deadline_timeout(timeout_seconds, deadline_epoch),
                    max_output_file_bytes,
                    cwd,
                )
            except ValueError as exc:
                immutable(
                    finished_path,
                    encoded(
                        {
                            "exit_code": -9,
                            "finished_at_epoch": time.time(),
                            "output_cap_exceeded": True,
                            "full_job_usage": None,
                        }
                    ),
                )
                raise ValueError(str(exc)) from None
            except subprocess.TimeoutExpired:
                immutable(
                    finished_path,
                    encoded(
                        {
                            "exit_code": -9,
                            "finished_at_epoch": time.time(),
                            "timed_out": True,
                            "full_job_usage": None,
                        }
                    ),
                )
                raise ValueError("Claude CLI timeout: исход сохранён, повтор запрещён") from None
        immutable(
            finished_path,
            encoded({"exit_code": completed.returncode, "finished_at_epoch": time.time()}),
        )
    start = read(started)
    if start.get("requested_config") != requested:
        raise ValueError("Сохранённая Claude CLI попытка другой конфигурации")
    finished = read(finished_path)
    if finished.get("exit_code") == -9 and (
        finished.get("timed_out") or finished.get("output_cap_exceeded")
    ):
        raise ValueError("Claude CLI попытка прервана лимитом; повтор запрещён")
    result = parsed_result((directory / "stdout.json").read_bytes())
    reason = deferral_reason(result)
    if reason is not None:
        raise TransportDeferred(
            reason,
            {
                "api_error_status": result.get("api_error_status"),
                "terminal_reason": result.get("terminal_reason"),
                "result": result.get("result"),
                "exit_code": finished.get("exit_code"),
                "stdout_sha256": sha(directory / "stdout.json"),
                "usage": result.get("usage"),
                "cost_usd": result.get("total_cost_usd"),
            },
        )
    if (
        finished.get("exit_code") != 0
        or result.get("is_error") is not False
        or result.get("subtype") != "success"
    ):
        raise ValueError(
            "Claude CLI не завершил результат: "
            + json.dumps(
                {
                    key: result.get(key)
                    for key in ("subtype", "terminal_reason", "api_error_status", "is_error")
                },
                ensure_ascii=False,
            )
        )
    structured = result.get("structured_output")
    if not isinstance(structured, dict):
        raise ValueError("Claude CLI не вернул structured_output по схеме")
    if result.get("permission_denials") != []:
        raise ValueError("Claude CLI сообщил попытку использования инструмента")
    immutable(directory / "raw-result.json", encoded(structured))
    probe = read(directory / "isolation-probe.json")
    cost = result.get("total_cost_usd")
    value = {
        "transport": TRANSPORT,
        "agent_id": f"claude-cli:{result.get('session_id')}",
        "session_id": result.get("session_id"),
        "runtime_status": "claude_result_json",
        "model": observed_model(result),
        "effort": None,
        "requested_model": model,
        "requested_effort": effort,
        "tokens": token_usage(result),
        "model_usage": result.get("modelUsage"),
        "cost_usd": cost if type(cost) in (int, float) else None,
        "cost_basis": "CLI-reported total_cost_usd; under a subscription this is the client "
        "estimate at API prices, not an invoice",
        "duration_ms": result.get("duration_ms"),
        "duration_api_ms": result.get("duration_api_ms"),
        "num_turns": result.get("num_turns"),
        "is_error": result.get("is_error"),
        "subtype": result.get("subtype"),
        "stop_reason": result.get("stop_reason"),
        "terminal_reason": result.get("terminal_reason"),
        "permission_denials": result.get("permission_denials"),
        "wall_elapsed_seconds": finished["finished_at_epoch"] - start["started_at_epoch"],
        "raw_result_sha256": sha(directory / "raw-result.json"),
        "stdout_sha256": sha(directory / "stdout.json"),
        "stderr_sha256": sha(directory / "stderr.log"),
        "prompt_sha256": sha(directory / "prompt.txt"),
        "schema_sha256": sha(directory / "schema.json"),
        "instructions_sha256": sha(directory / "instructions.txt"),
        "isolation_probe_sha256": sha(directory / "isolation-probe.json"),
        "isolation_control_sha256": sha(directory / "isolation-control.json"),
        "tool_registry": probe["tools"],
        "mcp_servers": probe["mcp_servers"],
        "tool_calls": None,
        "tool_calls_basis": "result JSON does not list tool use; registry empty at init, "
        "permission_denials empty, --max-turns 1",
        "cli_version": start["cli"]["cli_version"],
        "cli_binary_sha256": start["cli"]["cli_binary_sha256"],
        "native_claude_sha256": sha(Path(__file__)),
        "transport_retries": None,
        "automatic_cli_retries": 0,
    }
    immutable(receipt_path, encoded(value))
    return directory / "raw-result.json", value
