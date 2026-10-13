"""Поддерживаемый codex exec для cache-only партии, без веба и постоянного сервиса.

Использует установленный CLI и его существующий доступ. Не переопределяет модель,
не отключает sandbox/hooks. Каждый запуск ephemeral; неизвестный исход после
прерывания не запускается повторно автоматически. Сырые ответы неизменяемы.
"""

import hashlib
import json
import os
import re
import subprocess
import threading
import time
import tomllib
from pathlib import Path
from typing import Any

from sfr_enrichment.batch import encoded, immutable
from sfr_enrichment.common import FIELDS, read, sha
from sfr_enrichment.evidence import OBJECTS
from sfr_enrichment.semantics import (
    APPLICABILITY,
    DATE_BASES,
    EXTRA_FIELDS,
    FACT_KINDS,
    FIELD_VERDICTS,
    LEVELS,
    RULES_VERSION,
    VERDICTS,
)


def obj(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def string(values: list[str] | tuple[str, ...] | None = None) -> dict[str, Any]:
    return {"type": "string", **({"enum": list(values)} if values is not None else {})}


def array(item: dict[str, Any]) -> dict[str, Any]:
    return {"type": "array", "items": item}


def schema(stage: str, *, strict_levels: bool = False) -> dict[str, Any]:
    nullable = {"type": ["string", "null"]}
    common = {"author_id": string(), "batch_ticket_id": string(), "batch_input_sha256": string()}
    if stage == "collect":
        return obj(
            common
            | {
                "items": array(
                    obj(
                        {
                            "item_id": string(),
                            "field": string((*FIELDS, *EXTRA_FIELDS)),
                            "value": string(),
                            "evidence_refs": array(string()),
                        }
                    )
                ),
                "field_statuses": obj(
                    {field: string(("found", "not_established_from_cache")) for field in FIELDS}
                ),
                "profile_evidence": obj(
                    {name: array(string()) for name in ("identity", "current_affiliation")}
                ),
            }
        )
    profile = {
        "verdict": string(VERDICTS),
        "evidence_refs": array(string()),
        "information_date": nullable,
        "date_basis": string(DATE_BASES),
        "explanation": string(),
    }
    item = {
        "item_id": string(),
        "text_verdict": string(VERDICTS),
        "identity_verdict": string(VERDICTS),
        "field_verdict": string(FIELD_VERDICTS),
        "corrected_field": {"type": ["string", "null"], "enum": [None, *FIELDS, *EXTRA_FIELDS]},
        "fact_kind": string(FACT_KINDS),
        "object_type": string(OBJECTS),
        "object_relation": string(("supported", "insufficient", "conflicting")),
        "student_level": array(string(LEVELS)) | ({"minItems": 1} if strict_levels else {}),
        "information_date": nullable,
        "date_basis": string(DATE_BASES),
        "current_applicability": string(APPLICABILITY),
        "evidence_refs": array(string()),
        "explanation": string(),
        "question": string(),
    }
    return obj(
        common
        | {
            "input_sha256": string(),
            "rules_version": string((RULES_VERSION,)),
            "items": array(obj(item)),
            "profile_assessments": obj(
                {
                    "identity": obj(profile),
                    "current_affiliation": obj(profile),
                    "activity": obj(
                        profile | {"status": string(("active", "deceased", "ceased", "unknown"))}
                    ),
                }
            ),
            "summary": obj(
                {name: string() for name in ("known", "unknown", "identity", "current_opportunity")}
            ),
        }
    )


def isolation_options(directory: Path) -> list[str]:
    """Session-only options shared by the offline renderer and isolated inference."""
    options = [
        'model_provider="openai"',
        "developer_instructions=" + json.dumps((directory / "instructions.txt").read_text()),
        "project_doc_max_bytes=0",
        'web_search="disabled"',
        'sandbox_mode="read-only"',
        "features.unbounded_connection_retries=false",
    ]
    options += [
        f"features.{feature}=false"
        for feature in (
            "hooks",
            "shell_tool",
            "unified_exec",
            "browser_use",
            "browser_use_external",
            "computer_use",
            "apps",
            "plugins",
            "multi_agent",
            "code_mode_host",
            "image_generation",
            "view_image",
            "sleep_tool",
            "skill_search",
            "tool_suggest",
        )
    ]
    config_path = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "config.toml"
    config = tomllib.loads(config_path.read_text()) if config_path.exists() else {}
    for name in config.get("mcp_servers", {}):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise ValueError("Имя MCP не поддерживает безопасное CLI-переопределение")
        options.append(f"mcp_servers.{name}.enabled=false")
    return options


def isolation_probe(
    directory: Path,
    prompt: str,
    system_prompt: str,
    cwd: Path,
    model: str,
    isolation_config: list[str],
    deadline_epoch: float | None = None,
) -> dict[str, Any]:
    """Render task delivery, without treating unrendered API fields as absent.

    Mandatory client messages may coexist with the task. A new ephemeral exec,
    rather than message-list equality with Pi, supplies the history boundary.
    """

    command = [
        "codex",
        "debug",
        "prompt-input",
        *[a for c in isolation_config for a in ("-c", c)],
        "-c",
        f"model={json.dumps(model)}",
        prompt,
    ]
    started_at = time.time()
    timed_out = False
    try:
        probe = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            timeout=deadline_timeout(30, deadline_epoch),
            check=False,
        )
        stdout, stderr, exit_code = probe.stdout, probe.stderr, probe.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout, stderr, exit_code = exc.stdout or b"", exc.stderr or b"", -9
    if isinstance(stdout, str):
        stdout = stdout.encode()
    if isinstance(stderr, str):
        stderr = stderr.encode()
    proof: dict[str, Any] = {
        "exit_code": exit_code,
        "timed_out": timed_out,
        "started_at_epoch": started_at,
        "wall_elapsed_seconds": time.time() - started_at,
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        "instruction_sha256": hashlib.sha256(system_prompt.encode()).hexdigest(),
        "requested_instruction_file": str(directory / "instructions.txt"),
        "instruction_delivery": "unverified",
        "user_prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "available_tool_inventory": None,
        "tool_inventory_contract": "prompt-input renders messages, not separate API tools",
    }
    for stream, data in (("stdout", stdout), ("stderr", stderr)):
        name = "isolation-" + stream + "-" + proof[stream + "_sha256"] + ".bin"
        immutable(directory / name, data)
        (directory / name).chmod(0o600)
        proof[stream + "_path"] = str(directory / name)
    immutable(
        directory / ("isolation-render-" + hashlib.sha256(encoded(proof)).hexdigest() + ".json"),
        encoded(proof),
    )
    if exit_code:
        raise ValueError("Не доказана изоляция native prompt: offline render отказал")
    rendered = json.loads(stdout)
    if not isinstance(rendered, list):
        raise ValueError("Неизвестный контракт offline native prompt")
    texts = []
    for message in rendered:
        if message.get("type") != "message" or message.get("role") not in (
            "user",
            "developer",
            "system",
        ):
            raise ValueError("Посторонний элемент native prompt")
        content = message.get("content")
        if not isinstance(content, list) or any(
            c.get("type") not in ("input_text", "text") for c in content
        ):
            raise ValueError("Постороннее содержимое native prompt")
        texts.append("".join(c["text"] for c in content))
    instruction_messages = [
        text
        for message, text in zip(rendered, texts, strict=True)
        if message["role"] in ("developer", "system") and system_prompt in text
    ]
    if (
        not system_prompt
        or len(instruction_messages) != 1
        or texts[-1:] != [prompt]
        or rendered[-1]["role"] != "user"
    ):
        raise ValueError("Не доказана доставка общей native инструкции или точного конечного входа")
    proof["instruction_delivery"] = "rendered_instruction_and_exact_final_user"
    proof["rendered_messages"] = [
        {
            "role": message["role"],
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "characters": len(text),
            "contains_shared_instruction": system_prompt in text,
            "is_exact_user_prompt": text == prompt,
        }
        for message, text in zip(rendered, texts, strict=True)
    ]
    proof["additional_client_messages"] = len(rendered) - 2
    proof["api_system_instructions"] = "not rendered; presence/absence not inferred"
    immutable(directory / "isolation-probe.json", encoded(proof))
    return proof


def deadline_timeout(seconds: int, deadline_epoch: float | None) -> float:
    remaining = (
        float(seconds) if deadline_epoch is None else min(seconds, deadline_epoch - time.time())
    )
    if remaining <= 0:
        raise ValueError("Native process deadline: новая попытка запрещена")
    return remaining


def bounded_output_run(
    command: list[str], prompt: bytes, output: Any, errors: Any, timeout: float, cap: int
) -> subprocess.CompletedProcess[bytes]:
    """Limit only task-owned streams, never the client's existing files."""
    process = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
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
        raise ValueError("Native output stream cap: saved partial; no automatic retry")
    return subprocess.CompletedProcess(command, code)


def execute(
    directory: Path,
    prompt: str,
    output_schema: dict[str, Any],
    cwd: Path,
    *,
    model: str | None = None,
    effort: str | None = None,
    timeout_seconds: int = 1200,
    skip_git_repo_check: bool = False,
    disable_mcp: bool = False,
    required_config: dict[str, str] | None = None,
    system_prompt: str | None = None,
    deadline_epoch: float | None = None,
    max_output_file_bytes: int | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Однократная реальная попытка, recover готового вывода без повторного CLI."""
    if required_config is not None:
        expected = {"provider": "openai", "model": "gpt-6.1-sol", "effort": "high"}
        if system_prompt is not None and model == "gpt-6-astra" and effort == "xhigh":
            expected = {"provider": "openai", "model": model, "effort": effort}
        if (
            required_config != expected
            or model != expected["model"]
            or effort != expected["effort"]
        ):
            raise ValueError("Отсутствует или неверна явная конфигурация native high-v1")
    if max_output_file_bytes is not None and (
        type(max_output_file_bytes) is not int or max_output_file_bytes <= 0
    ):
        raise ValueError("Invalid native output file cap")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if required_config is not None:
        immutable(directory / "requested-config.json", encoded(required_config))
    prompt_bytes = prompt.encode()
    immutable(directory / "prompt.txt", prompt_bytes)
    immutable(directory / "schema.json", encoded(output_schema))
    if system_prompt is not None:
        immutable(directory / "instructions.txt", system_prompt.encode())
    receipt = directory / "receipt.json"
    if receipt.exists():
        value = read(receipt)
        if required_config and (value.get("requested_model"), value.get("requested_effort")) != (
            model,
            effort,
        ):
            raise ValueError("Сохранённый native runtime другого задания")
        if sha(directory / "raw-result.json") != value["raw_result_sha256"]:
            raise ValueError("Сырой ответ изменён")
        return directory / "raw-result.json", value
    started = directory / "started.json"
    if started.exists() and not (directory / "finished.json").exists():
        raise ValueError("Исход CLI-попытки неизвестен: автоматический повтор запрещён")
    if not started.exists():
        isolation_config: list[str] = []
        if system_prompt is not None:
            isolation_config = isolation_options(directory)
            isolation_probe(
                directory,
                prompt,
                system_prompt,
                cwd,
                model or "",
                isolation_config,
                deadline_epoch=deadline_epoch,
            )
        immutable(
            started,
            encoded(
                {
                    "started_at_epoch": time.time(),
                    "prompt_sha256": hashlib.sha256(prompt_bytes).hexdigest(),
                    "mode": "codex exec ephemeral read-only cache-only",
                    **({"requested_config": required_config} if required_config else {}),
                }
            ),
        )
        command = [
            "codex",
            "exec",
            "--ephemeral",
            "--json",
            "--strict-config",
            "-c",
            'web_search="disabled"',
            "--sandbox",
            "read-only",
            "--output-schema",
            str(directory / "schema.json"),
            "--output-last-message",
            str(directory / "raw-result.json"),
            "-C",
            str(cwd),
            "-",
        ]
        if required_config is not None:
            command[2:2] = ["-c", 'model_provider="openai"']
        if model:
            command[2:2] = ["-m", model]
        if effort:
            command[2:2] = ["-c", f'model_reasoning_effort="{effort}"']
        if system_prompt is not None:
            command[2:2] = [option for config in isolation_config for option in ("-c", config)]
        if skip_git_repo_check:
            command.insert(2, "--skip-git-repo-check")
        if disable_mcp:
            command[2:2] = [
                option
                for feature in (
                    "shell_tool",
                    "unified_exec",
                    "browser_use",
                    "browser_use_external",
                    "computer_use",
                    "apps",
                    "plugins",
                    "multi_agent",
                    "code_mode_host",
                    "image_generation",
                    "view_image",
                    "sleep_tool",
                    "skill_search",
                    "tool_suggest",
                )
                for option in ("-c", f"features.{feature}=false")
            ]
            config_path = (
                Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "config.toml"
            )
            config = tomllib.loads(config_path.read_text()) if config_path.exists() else {}
            for name in config.get("mcp_servers", {}):
                if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
                    raise ValueError("Имя MCP не поддерживает безопасное CLI-переопределение")
                command[2:2] = ["-c", f"mcp_servers.{name}.enabled=false"]
        if required_config is not None:
            immutable(directory / "command.json", encoded(command))

        with (
            (directory / "events.jsonl").open("xb") as event_stream,
            (directory / "stderr.log").open("xb") as errors,
        ):
            try:
                if max_output_file_bytes is not None:
                    result = bounded_output_run(
                        command,
                        prompt_bytes,
                        event_stream,
                        errors,
                        deadline_timeout(timeout_seconds, deadline_epoch),
                        max_output_file_bytes,
                    )
                else:
                    result = subprocess.run(
                        command,
                        input=prompt_bytes,
                        stdout=event_stream,
                        stderr=errors,
                        timeout=deadline_timeout(timeout_seconds, deadline_epoch),
                        check=False,
                    )
            except ValueError as exc:
                immutable(
                    directory / "finished.json",
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
                    directory / "finished.json",
                    encoded(
                        {
                            "exit_code": -9,
                            "finished_at_epoch": time.time(),
                            "timed_out": True,
                            "full_job_usage": None,
                        }
                    ),
                )
                raise ValueError("Native timeout: исход сохранён, повтор запрещён") from None
        immutable(
            directory / "finished.json",
            encoded({"exit_code": result.returncode, "finished_at_epoch": time.time()}),
        )
    if required_config and read(started).get("requested_config") != required_config:
        raise ValueError("Сохранённая native попытка другой конфигурации")
    finished = read(directory / "finished.json")
    if finished["exit_code"] != 0 or not (directory / "raw-result.json").exists():
        raise ValueError("CLI не завершил результат; доказательства сохранены, нужен разбор")
    events = [
        json.loads(line)
        for line in (directory / "events.jsonl").read_text().splitlines()
        if line.strip()
    ]
    turn_start = next(
        (index for index, event in enumerate(events) if event.get("type") == "turn.started"), 0
    )
    # The client emits this diagnostic when its command host is intentionally disabled.
    # It is not model activity. Accept only the known pre-turn warning, retaining its raw event.
    client_diagnostics = [
        event
        for event in events[:turn_start]
        if event.get("type") == "item.completed"
        and event.get("item", {}).get("type") == "error"
        and event["item"].get("message")
        == "Code Mode is unavailable because code-mode host is disabled. "
        "Code mode will fail closed; enable `features.code_mode_host` "
        "and install `codex-code-mode-host`."
    ]
    if any(
        event.get("item", {}).get("type") in ("web_search", "command_execution", "mcp_tool_call")
        or (
            system_prompt is not None
            and "item" in event
            and event["item"].get("type") not in ("agent_message", "reasoning")
        )
        for index, event in enumerate(events)
        if index >= turn_start or event not in client_diagnostics
    ):
        raise ValueError(
            "Cache-only запуск использовал инструмент: нужна отдельная "
            "проверка, результат не принят"
        )
    thread = next((e["thread_id"] for e in events if e.get("type") == "thread.started"), None)
    usage = next(
        (e.get("usage") for e in reversed(events) if e.get("type") == "turn.completed"), None
    )
    if not thread or usage is None:
        raise ValueError("Нет доказательства фактического завершения независимого агента")
    value = {
        "agent_id": f"codex-ephemeral:{thread}",
        "runtime_status": "runtime_not_exposed",
        "model": None,
        "effort": None,
        "tokens": usage,
        "cost_usd": None,
        "wall_elapsed_seconds": finished["finished_at_epoch"] - read(started)["started_at_epoch"],
        "raw_result_sha256": sha(directory / "raw-result.json"),
        "events_sha256": sha(directory / "events.jsonl"),
        "prompt_sha256": sha(directory / "prompt.txt"),
        "tool_calls": 0,
        "client_diagnostics": client_diagnostics,
        "requested_model": model,
        "requested_effort": effort,
        "transport_retries": None,
        **({"automatic_cli_retries": 0, "requested_provider": "openai"} if required_config else {}),
    }
    immutable(receipt, encoded(value))
    return directory / "raw-result.json", value


def normalized_provenance(receipt: dict[str, Any], stage: str) -> dict[str, Any]:
    """Фактический usage сохраняется; cached/reasoning не прибавляются дважды."""
    provenance = receipt | {"stage": stage}
    usage = receipt.get("tokens")
    if isinstance(usage, dict):
        provenance["token_usage"] = usage
        counts = (usage.get("input_tokens"), usage.get("output_tokens"))
        provenance["tokens"] = (
            sum(counts) if all(type(count) is int and count >= 0 for count in counts) else None
        )
    return provenance
