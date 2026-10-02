"""Read-only handoff gate: current PR review receipt and required CI checks.

Reads PR snapshots, Actions job logs, and tested commit parents via ``gh``.
A receipt is a PR comment:
<!-- sfr-review {"base":"<40 hex>","head":"<40 hex>","reviewer":"sfr-reviewer",
"verdict":"pass","blocking_findings":0} -->

The newest receipt supersedes earlier ones, including a stale or malformed one.
This validates a recorded result, not review quality, reviewer identity, or
independence. It does not modify the PR, grant merge permission, or configure
branch protection. Re-run after any change to the PR or its base.
Each required job must have tested a merge whose parents are the current
base/head. Missing or ambiguous checkout logs block handoff.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

REPO = "borisboriov/search-for-research"
FIELDS = "headRefOid,baseRefOid,baseRefName,state,statusCheckRollup,comments"
REQUIRED_CHECKS = ("checks", "web", "audit")
SHA = re.compile(r"[0-9a-f]{40}")
MARKER_START = re.compile(r"<!--\s*sfr-review\b")
MARKER = re.compile(r"<!--\s*sfr-review\s+(.+?)\s*-->", re.DOTALL)
RECEIPT_FIELDS = {"base", "head", "reviewer", "verdict", "blocking_findings"}
JOB_URL = re.compile(
    rf"https://github\.com/{re.escape(REPO)}/actions/runs/([1-9][0-9]*)/job/([1-9][0-9]*)"
)
LOG_TIME = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z "
CHECKOUT_COMMAND = re.compile(LOG_TIME + r"\[command\]/\S*/git log -1 --format=%H")
CHECKOUT_SHA = re.compile(LOG_TIME + r"([0-9a-f]{40})")


class HandoffError(ValueError):
    """The available evidence does not permit handoff."""


def valid_sha(value: object) -> bool:
    return isinstance(value, str) and bool(SHA.fullmatch(value)) and value != "0" * 40


def unique_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise HandoffError("Повторяющиеся поля в JSON подтверждения ревью")
        result[key] = value
    return result


def comment_time(value: object, now: datetime) -> datetime:
    if not isinstance(value, str):
        raise HandoffError("У комментария ревью нет createdAt")
    try:
        created = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HandoffError("Некорректная дата комментария ревью") from exc
    if created.tzinfo is None or created.utcoffset() is None:
        raise HandoffError("Дата комментария ревью без часового пояса")
    if created > now:
        raise HandoffError("Комментарий ревью датирован будущим")
    return created


def latest_receipt(comments: object, now: datetime) -> dict[str, Any]:
    if not isinstance(comments, list):
        raise HandoffError("GitHub не вернул список комментариев PR")
    candidates: list[tuple[datetime, int, str]] = []
    for order, comment in enumerate(comments):
        if not isinstance(comment, dict) or not isinstance(comment.get("body"), str):
            raise HandoffError("Некорректные данные комментария PR")
        body = comment["body"]
        if MARKER_START.search(body):
            candidates.append((comment_time(comment.get("createdAt"), now), order, body))
    if not candidates:
        raise HandoffError("Нет комментария с подтверждением sfr-review")
    body = max(candidates)[2]
    matches = list(MARKER.finditer(body))
    if len(matches) != 1 or len(MARKER_START.findall(body)) != 1:
        raise HandoffError("Последний комментарий sfr-review имеет неверный формат")
    try:
        receipt = json.loads(matches[0].group(1), object_pairs_hook=unique_fields)
    except json.JSONDecodeError as exc:
        raise HandoffError("В последнем комментарии sfr-review некорректный JSON") from exc
    if not isinstance(receipt, dict) or set(receipt) != RECEIPT_FIELDS:
        raise HandoffError("В подтверждении ревью отсутствуют или неизвестны поля")
    if not valid_sha(receipt["base"]) or not valid_sha(receipt["head"]):
        raise HandoffError("Подтверждение ревью не содержит полные base/head SHA")
    if receipt["reviewer"] != "sfr-reviewer":
        raise HandoffError("В подтверждении не указан reviewer sfr-reviewer")
    if receipt["verdict"] != "pass":
        raise HandoffError("Последний вердикт ревью не pass")
    if type(receipt["blocking_findings"]) is not int or receipt["blocking_findings"] != 0:
        raise HandoffError("Ревью не подтверждает отсутствие блокирующих находок")
    return receipt


def check_pr(snapshot: object, *, now: datetime | None = None) -> tuple[str, str]:
    """Validate the PR receipt and rollup before fetching CI evidence."""
    if not isinstance(snapshot, dict):
        raise HandoffError("GitHub не вернул данные PR")
    if snapshot.get("state") != "OPEN":
        raise HandoffError("Передача требует открытого PR (state OPEN)")
    # PR.baseRefOid can lag behind the target branch; fetch its live ref separately.
    base, head = snapshot.get("baseBranchOid"), snapshot.get("headRefOid")
    if not valid_sha(base) or not valid_sha(head):
        raise HandoffError("Неизвестна текущая версия PR: нужны полные live base/head SHA")
    receipt = latest_receipt(snapshot.get("comments"), now or datetime.now(UTC))
    if receipt["base"] != base or receipt["head"] != head:
        raise HandoffError("Последнее ревью устарело: base/head не совпадают с текущим PR")
    checks = snapshot.get("statusCheckRollup")
    if not isinstance(checks, list):
        raise HandoffError("GitHub не вернул текущий statusCheckRollup")
    for name in REQUIRED_CHECKS:
        matches = [
            check for check in checks if isinstance(check, dict) and check.get("name") == name
        ]
        if not matches:
            raise HandoffError(f"В текущем PR отсутствует CI-проверка {name}")
        if len(matches) != 1:
            raise HandoffError(f"Неоднозначный statusCheckRollup: несколько проверок {name}")
        check = matches[0]
        if (
            check.get("__typename") != "CheckRun"
            or check.get("status") != "COMPLETED"
            or check.get("conclusion") != "SUCCESS"
        ):
            raise HandoffError(f"CI-проверка {name} не завершилась успешно на текущей версии PR")
    # valid_sha above rejects non-strings; narrow for type checkers without coercion.
    assert isinstance(base, str) and isinstance(head, str)
    return base, head


def job_ids(check: dict[str, Any]) -> tuple[int, int]:
    url = check.get("detailsUrl")
    match = JOB_URL.fullmatch(url) if isinstance(url, str) else None
    if not match:
        raise HandoffError("CI: нет однозначной ссылки на job GitHub Actions этого репозитория")
    return int(match[1]), int(match[2])


def checkout_sha(log: str) -> str:
    """Read checkout@v4's final git log output, never echoing raw job logs."""
    lines = log.splitlines()
    commands = [i for i, line in enumerate(lines) if CHECKOUT_COMMAND.fullmatch(line)]
    if len(commands) != 1 or commands[0] + 1 >= len(lines):
        raise HandoffError("CI: нет единственного SHA checkout в журнале job")
    match = CHECKOUT_SHA.fullmatch(lines[commands[0] + 1])
    if not match or not valid_sha(match[1]):
        raise HandoffError("CI: журнал checkout не содержит полный SHA проверенного коммита")
    return match[1]


def check_handoff(snapshot: object, *, now: datetime | None = None) -> tuple[str, str]:
    """Validate captured evidence; no filesystem or network operations."""
    base, head = check_pr(snapshot, now=now)
    assert isinstance(snapshot, dict)
    evidence = snapshot.get("ciEvidence")
    if not isinstance(evidence, dict) or set(evidence) != set(REQUIRED_CHECKS):
        raise HandoffError("CI: нет доказательств проверенного merge для checks/web/audit")
    for check in snapshot["statusCheckRollup"]:
        if not isinstance(check, dict) or check.get("name") not in REQUIRED_CHECKS:
            continue
        name = check["name"]
        run_id, job_id = job_ids(check)
        item = evidence[name]
        if not isinstance(item, dict):
            raise HandoffError(f"CI {name}: некорректное доказательство checkout")
        job, commit, tested = item.get("job"), item.get("commit"), item.get("checkoutSha")
        if (
            not isinstance(job, dict)
            or job.get("id") != job_id
            or job.get("run_id") != run_id
            or job.get("name") != name
            or job.get("html_url") != check["detailsUrl"]
            or job.get("head_sha") != head
            or job.get("status") != "completed"
            or job.get("conclusion") != "success"
        ):
            raise HandoffError(f"CI {name}: job не подтверждает успешную проверку текущего head")
        if (
            not valid_sha(tested)
            or not isinstance(commit, dict)
            or commit.get("sha") != tested
            or not isinstance(commit.get("parents"), list)
            or [p.get("sha") if isinstance(p, dict) else None for p in commit["parents"]]
            != [base, head]
        ):
            raise HandoffError(f"CI {name}: проверенный merge не соответствует текущим base/head")
    return base, head


def positive_pr(value: str) -> int:
    if not re.fullmatch(r"[1-9][0-9]*", value):
        raise argparse.ArgumentTypeError("нужен положительный номер PR, например --pr 123")
    return int(value)


def gh_text(args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["gh", *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HandoffError("Не удалось прочитать доказательства через gh") from exc
    if result.returncode:
        raise HandoffError(f"gh завершился кодом {result.returncode}; доказательства не проверены")
    return result.stdout


def gh_json(args: list[str]) -> object:
    try:
        return json.loads(gh_text(args))
    except json.JSONDecodeError as exc:
        raise HandoffError("gh вернул некорректный JSON; PR не проверен") from exc


def fetch_pr(pr: int) -> object:
    snapshot = gh_json(["pr", "view", "--repo", REPO, str(pr), "--json", FIELDS])
    if not isinstance(snapshot, dict):
        raise HandoffError("GitHub не вернул данные PR")
    branch = snapshot.get("baseRefName")
    if not isinstance(branch, str) or not branch or any(ord(c) < 32 for c in branch):
        raise HandoffError("GitHub не вернул имя целевой ветки PR")
    ref = gh_json(
        ["api", "--method", "GET", f"repos/{REPO}/git/ref/heads/{quote(branch, safe='')}"]
    )
    if (
        not isinstance(ref, dict)
        or ref.get("ref") != f"refs/heads/{branch}"
        or not isinstance(ref.get("object"), dict)
        or ref["object"].get("type") != "commit"
        or not valid_sha(ref["object"].get("sha"))
    ):
        raise HandoffError("GitHub не подтвердил живую вершину целевой ветки PR")
    return {**snapshot, "baseBranchOid": ref["object"]["sha"]}


def fetch_handoff(pr: int) -> object:
    snapshot = fetch_pr(pr)
    check_pr(snapshot)
    assert isinstance(snapshot, dict)
    evidence: dict[str, Any] = {}
    commits: dict[str, object] = {}
    for check in snapshot["statusCheckRollup"]:
        if not isinstance(check, dict) or check.get("name") not in REQUIRED_CHECKS:
            continue
        _, job_id = job_ids(check)
        endpoint = f"repos/{REPO}/actions/jobs/{job_id}"
        job = gh_json(["api", "--method", "GET", endpoint])
        # New gh versions reject control characters in job logs by default.
        # Capture them in memory only; never print logs or signed redirect URLs.
        log = gh_text(["api", "--method", "GET", "--allow-escape-sequences", endpoint + "/logs"])
        tested = checkout_sha(log)
        if tested not in commits:
            commits[tested] = gh_json(["api", "--method", "GET", f"repos/{REPO}/commits/{tested}"])
        evidence[check["name"]] = {"job": job, "checkoutSha": tested, "commit": commits[tested]}
    # A push, new receipt, or changed check during collection invalidates the snapshot.
    if fetch_pr(pr) != snapshot:
        raise HandoffError("PR или его доказательства изменились во время проверки; повторите её")
    return {**snapshot, "ciEvidence": evidence}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr", required=True, type=positive_pr, help="номер PR в репозитории SFR")
    args = parser.parse_args(argv)
    try:
        base, head = check_handoff(fetch_handoff(args.pr))
    except HandoffError as exc:
        print(f"Передача не подтверждена: {exc}", file=sys.stderr)
        return 1
    print(
        f"PR #{args.pr}: ревью {base}..{head}; "
        "checks/web/audit на merge этих base/head подтверждены"
    )
    print(
        "Это проверка записанного результата, "
        "не доказательство независимости и не разрешение merge."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
