"""Hash-bound sequential runner for prepared Claude CLI B/C jobs (protocol v2).

Воспроизводит дисциплину частного ``execute_one_v2.py``: writer.lock, run-clock
с SHA authorization, абсолютный deadline и общий лимит запуска, cap заданий,
строгий порядок prepared manifest без повторов, импорт после каждого задания
и остановку на неразрешённом или техническом исходе. Отказ rate-limit/overload
до вывода модели фиксируется как ``transport_deferred``: слот не расходуется,
runner останавливается, продолжение возможно только новым явным запуском.
Проба изоляции — отдельный шаг ``probe`` до authorization: authorization ссылается
на SHA proof, а runner перед каждой попыткой проверяет сохранённый proof и сам
пробу не запускает. Модуль ничего не запускает при импорте; поиск, повторы и
fallback отсутствуют.
"""

import argparse
import fcntl
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from sfr_enrichment import native, native_claude, nir
from sfr_enrichment.common import ensure_not_stopped, read, sha, write_new

AUTHORIZATION_TRANSPORT = "claude_cli_existing_subscription"
PURPOSES = ("diagnostic_pilot_not_holdout",)
EXIT_TECHNICAL = 2
EXIT_DEFERRED = 3
QUOTA_UNAVAILABLE = {
    "source": "unavailable",
    "reason": "Claude CLI exposes no official quota endpoint; no percentage inferred",
    "ordinary_usage_allowed": None,
    "remaining_percent": None,
    "checked_at_epoch": None,
}


def implementation_hashes() -> dict[str, str]:
    return {
        "native_sha256": sha(Path(native.__file__)),
        "native_claude_sha256": sha(Path(native_claude.__file__)),
        "nir_sha256": sha(Path(nir.__file__)),
        "runner_sha256": sha(Path(__file__)),
    }


def positive(value: Any) -> bool:
    return type(value) is int and value > 0


def validated(root: Path, path: Path) -> tuple[dict[str, Any], dict[str, Any], float]:
    """Static admission checks; any mismatch stops before the ledger is touched."""
    auth = read(path)
    prepared_path = root / "prepared-model" / "manifest.json"
    prepared = read(prepared_path)
    order = prepared.get("order")
    try:
        deadline = datetime.fromisoformat(auth["absolute_deadline"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("Authorization: нужен absolute_deadline ISO с часовым поясом") from None
    checks = [
        (auth.get("purpose") in PURPOSES, "purpose"),
        (auth.get("live_authorized") is True, "live_authorized"),
        (auth.get("transport") == AUTHORIZATION_TRANSPORT, "transport"),
        (auth.get("new_paid_services_authorized") is False, "new_paid_services_authorized"),
        (auth.get("retries") == 0 and type(auth.get("retries")) is int, "retries"),
        (auth.get("parallelism") == 1 and type(auth.get("parallelism")) is int, "parallelism"),
        (deadline.tzinfo is not None, "absolute_deadline timezone"),
        (
            isinstance(auth.get("authorization_reference"), str)
            and bool(auth["authorization_reference"].strip()),
            "authorization_reference",
        ),
        (auth.get("execution_root") == str(root), "execution_root"),
        (
            isinstance(auth.get("cli_version"), str)
            and re.fullmatch(r"\d+\.\d+\.\d+ \(Claude Code\)", auth["cli_version"]) is not None,
            "cli_version",
        ),
        (isinstance(auth.get("model"), str) and bool(auth["model"]), "model"),
        (auth.get("effort") in native_claude.EFFORTS, "effort"),
        *[
            (positive(auth.get(key)), key)
            for key in (
                "run_deadline_seconds",
                "per_call_timeout_seconds",
                "max_output_file_bytes",
                "max_input_bytes_per_case",
                "model_job_cap",
            )
        ],
        *[(auth.get(key) == value, key) for key, value in implementation_hashes().items()],
        (auth.get("frozen_manifest_sha256") == sha(root / "manifest.json"), "frozen manifest"),
        (auth.get("prepared_manifest_sha256") == sha(prepared_path), "prepared manifest"),
        (prepared.get("transport") == native_claude.TRANSPORT, "prepared transport"),
        (
            isinstance(order, list) and bool(order) and len(set(order)) == len(order),
            "prepared order",
        ),
    ]
    proof = auth.get("isolation_proof_path")
    checks.append(
        (
            isinstance(proof, str)
            and Path(proof).name == native_claude.PROOF
            and Path(proof).is_file()
            and sha(Path(proof)) == auth.get("isolation_proof_sha256"),
            "isolation_proof_sha256",
        )
    )
    failed = [name for ok, name in checks if not ok]
    if failed:
        raise ValueError("Authorization precondition failed: " + ", ".join(failed))
    if auth["model_job_cap"] > len(order):
        raise ValueError("Authorization precondition failed: model_job_cap")
    proof_directory(auth)
    return auth, prepared, deadline.timestamp()


def proof_directory(auth: dict[str, Any]) -> Path:
    """Verify the stored proof for the authorized flags and CLI; never launch a probe."""
    directory = Path(auth["isolation_proof_path"]).parent
    verified = native_claude.verify_isolation_proof(
        directory, model=auth["model"], effort=auth["effort"], cli_version=auth["cli_version"]
    )
    if verified["isolation_proof_sha256"] != auth["isolation_proof_sha256"]:
        raise ValueError("Authorization precondition failed: isolation proof changed")
    return directory


def ledger_position(execution: Path, order: list[str]) -> tuple[int, int]:
    """Return (consumed slots, attempt records); stop on any unresolved outcome."""
    attempts = sorted(execution.glob("attempt-*.json"))
    if [p.name for p in attempts] != [f"attempt-{i:03d}.json" for i in range(len(attempts))]:
        raise ValueError("Ledger attempts are not contiguous")
    consumed = 0
    for index, path in enumerate(attempts):
        request_id = read(path)["request_id"]
        if consumed >= len(order) or request_id != order[consumed]:
            raise ValueError("No retry or changed order")
        deferred = execution / f"deferred-{index:03d}-{request_id}.json"
        if deferred.exists():
            if read(deferred).get("status") != "transport_deferred":
                raise ValueError("Ledger deferred outcome is invalid")
            continue
        outcome = execution / f"outcome-{request_id}.json"
        if not outcome.exists():
            raise ValueError("Previous attempt outcome unresolved")
        if read(outcome).get("status") != "imported":
            raise ValueError(
                "Previous technical failure requires inspection; continuation forbidden"
            )
        consumed += 1
    return consumed, len(attempts)


def run_job(
    root: Path,
    execution: Path,
    auth: dict[str, Any],
    authorization_sha256: str,
    prepared: dict[str, Any],
    request_id: str,
    attempt_index: int,
    deadline: float,
) -> int:
    request = nir.prepared_request(root, request_id)
    kwargs = request.get("claude_kwargs")
    if (
        request.get("transport") != native_claude.TRANSPORT
        or not isinstance(kwargs, dict)
        or (kwargs.get("model"), kwargs.get("effort")) != (auth["model"], auth["effort"])
        or kwargs.get("timeout_seconds") != auth["per_call_timeout_seconds"]
        or kwargs.get("max_output_file_bytes") != auth["max_output_file_bytes"]
    ):
        raise ValueError("Prepared request differs from authorization")
    cwd = root / "isolated-cwd"
    cwd.mkdir(mode=0o700, exist_ok=True)
    native_claude.require_empty_directory(cwd)
    prompt = (root / request["prompt_path"]).read_bytes().decode("utf-8")
    system = (root / request["system_prompt_path"]).read_bytes().decode("utf-8")
    if len(prompt.encode()) + len(system.encode()) > auth["max_input_bytes_per_case"]:
        raise ValueError("Prepared request exceeds authorized input bytes; no truncation")
    # Cheap admission checks before a slot is recorded; execute repeats them with evidence.
    native_claude.paid_key_guard()
    if native_claude.installed_cli_version(deadline) != auth["cli_version"]:
        raise ValueError("Installed Claude CLI differs from authorization")
    proof = proof_directory(auth)
    write_new(
        execution / f"attempt-{attempt_index:03d}.json",
        {
            "request_id": request_id,
            "authorization_sha256": authorization_sha256,
            "request_sha256": prepared["requests"][request_id]["sha256"],
            "quota_observation": QUOTA_UNAVAILABLE,
            "started_at_epoch": time.time(),
            "attempt_counts_against_cap": True,
            "transport": native_claude.TRANSPORT,
        },
    )
    output = root / "native" / f"{request_id}-attempt-{attempt_index:03d}"
    outcome: dict[str, Any] = {
        "request_id": request_id,
        "attempt_counts_against_cap": True,
        "retries": 0,
        "raw_usage_unknown_until_receipt": True,
    }
    try:
        raw, _ = native_claude.execute(
            output,
            prompt,
            read(root / request["output_schema_path"]),
            cwd,
            system_prompt=system,
            isolation_proof_dir=proof,
            deadline_epoch=deadline,
            expected_cli_version=auth["cli_version"],
            **kwargs,
        )
        native_claude.require_empty_directory(cwd)
        imported = nir.import_native(root, request_id, output, "native-" + request_id)
        outcome.update(
            status="imported",
            receipt_sha256=sha(output / "receipt.json"),
            imported_path=str(imported),
            raw_result_sha256=sha(raw),
        )
    except native_claude.TransportDeferred as exc:
        deferred = {
            "request_id": request_id,
            "attempt_index": attempt_index,
            "status": "transport_deferred",
            "reason": exc.reason,
            "attempt_counts_against_cap": False,
            "slot_consumed": False,
            "retries": 0,
            "error": str(exc),
            "details": exc.details,
            "native_dir": str(output),
            "continuation": "new explicit launch only; same request is next in order",
            "finished_at_epoch": time.time(),
        }
        write_new(execution / f"deferred-{attempt_index:03d}-{request_id}.json", deferred)
        print(json.dumps(deferred, ensure_ascii=False))
        return EXIT_DEFERRED
    except Exception as exc:
        outcome.update(
            status="technical_failure",
            error_type=type(exc).__name__,
            error=str(exc),
            requires_inspection_before_next_job=True,
        )
    outcome["finished_at_epoch"] = time.time()
    write_new(execution / f"outcome-{request_id}.json", outcome)
    print(json.dumps(outcome, ensure_ascii=False))
    return 0 if outcome["status"] == "imported" else EXIT_TECHNICAL


def execute(
    root: Path, authorization: Path, *, single: bool = False, request_id: str | None = None
) -> int:
    """Run the next job(s) in frozen order; return 0, EXIT_TECHNICAL or EXIT_DEFERRED."""
    root = root.resolve()
    ensure_not_stopped(root)
    auth, prepared, deadline = validated(root, authorization)
    order: list[str] = prepared["order"]
    authorization_sha256 = sha(authorization)
    execution = root / "execution"
    execution.mkdir(mode=0o700, exist_ok=True)
    with (execution / "writer.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Другой writer уже держит ledger") from None
        clock_path = execution / "run-clock.json"
        if not clock_path.exists():
            write_new(
                clock_path,
                {"started_at_epoch": time.time(), "authorization_sha256": authorization_sha256},
            )
        clock = read(clock_path)
        if clock.get("authorization_sha256") != authorization_sha256:
            raise ValueError("Run clock belongs to another authorization")
        deadline = min(deadline, clock["started_at_epoch"] + auth["run_deadline_seconds"])
        while True:
            consumed, attempts = ledger_position(execution, order)
            cap = auth["model_job_cap"]
            if consumed >= min(cap, len(order)):
                print(json.dumps({"status": "complete", "consumed": consumed, "cap": cap}))
                return 0
            next_id = order[consumed]
            if request_id is not None and request_id != next_id:
                raise ValueError("No retry or changed order")
            if time.time() >= deadline:
                raise ValueError("Authorized run deadline passed")
            ensure_not_stopped(root)
            code = run_job(
                root,
                execution,
                auth,
                authorization_sha256,
                prepared,
                next_id,
                attempts,
                deadline,
            )
            if code or single or request_id is not None:
                return code


def probe(root: Path, request_id: str, out: Path) -> Path:
    """Separate isolation step before authorization; never touches the ledger.

    Each probe is a real CLI launch terminated at system/init and needs its own
    permission; the resulting ``isolation-proof.json`` SHA goes into authorization.
    """
    root = root.resolve()
    request = nir.prepared_request(root, request_id)
    if request.get("transport") != native_claude.TRANSPORT:
        raise ValueError("Probe applies only to claude_cli prepared requests")
    out = out.resolve()
    if out.exists():
        raise FileExistsError(out)
    kwargs = request["claude_kwargs"]
    return native_claude.run_isolation_check(
        out,
        system_prompt=(root / request["system_prompt_path"]).read_bytes().decode("utf-8"),
        schema_text=(root / request["output_schema_path"]).read_text(),
        model=kwargs["model"],
        effort=kwargs["effort"],
        context={
            "request_id": request_id,
            "request_sha256": read(root / "prepared-model" / "manifest.json")["requests"][
                request_id
            ]["sha256"],
            "implementation": implementation_hashes(),
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m sfr_enrichment.nir_execute")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("execute", help="Run authorized prepared Claude jobs in order")
    run.add_argument("--root", required=True, type=Path)
    run.add_argument("--authorization", required=True, type=Path)
    which = run.add_mutually_exclusive_group()
    which.add_argument("--next", action="store_true", help="Run exactly the next job")
    which.add_argument("--request-id", help="Run exactly this job; it must be next")
    check = commands.add_parser("probe", help="Isolation proof before authorization")
    check.add_argument("--root", required=True, type=Path)
    check.add_argument("--request-id", required=True)
    check.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.command == "probe":
        summary = probe(args.root, args.request_id, args.out)
        print(
            json.dumps(
                {"isolation_proof_path": str(summary), "isolation_proof_sha256": sha(summary)}
            )
        )
        return 0
    return execute(args.root, args.authorization, single=args.next, request_id=args.request_id)


if __name__ == "__main__":
    sys.exit(main())
