"""Handoff regressions on fixtures: no GitHub, credentials, or repo mutations."""

from __future__ import annotations

import io
import json
import subprocess
import unittest
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from unittest.mock import Mock, patch

from check_handoff import FIELDS, REPO, HandoffError, check_handoff, checkout_sha, main

BASE = "a" * 40
HEAD = "b" * 40
MERGE = "c" * 40
NOW = datetime(2026, 10, 2, 12, tzinfo=UTC)
CHECKOUT_LOG = (
    "2026-10-02T08:48:07.2082148Z [command]/usr/bin/git log -1 --format=%H\n"
    f"2026-10-02T08:48:07.2108279Z {MERGE}\n"
)


def comment(*, created: str = "2026-10-02T11:00:00Z", **overrides: object) -> dict[str, Any]:
    receipt: dict[str, object] = {
        "base": BASE,
        "head": HEAD,
        "reviewer": "sfr-reviewer",
        "verdict": "pass",
    }
    receipt["blocking_findings"] = 0
    receipt.update(overrides)
    return {"body": "<!-- sfr-review " + json.dumps(receipt) + " -->", "createdAt": created}


def fixture() -> dict[str, Any]:
    checks = [
        {
            "__typename": "CheckRun",
            "name": name,
            "status": "COMPLETED",
            "conclusion": "SUCCESS",
            "detailsUrl": f"https://github.com/{REPO}/actions/runs/500/job/{job_id}",
        }
        for job_id, name in enumerate(("checks", "web", "audit"), 100)
    ]
    return {
        "state": "OPEN",
        "baseRefOid": BASE,
        "baseRefName": "main",
        "baseBranchOid": BASE,
        "headRefOid": HEAD,
        "comments": [comment()],
        "statusCheckRollup": checks,
        "ciEvidence": {
            check["name"]: {
                "job": {
                    "id": job_id,
                    "run_id": 500,
                    "name": check["name"],
                    "html_url": check["detailsUrl"],
                    "head_sha": HEAD,
                    "status": "completed",
                    "conclusion": "success",
                },
                "checkoutSha": MERGE,
                "commit": {"sha": MERGE, "parents": [{"sha": BASE}, {"sha": HEAD}]},
            }
            for job_id, check in enumerate(checks, 100)
        },
    }


def api_responses(data: dict[str, Any]) -> list[subprocess.CompletedProcess[str]]:
    raw = {key: value for key, value in data.items() if key not in {"ciEvidence", "baseBranchOid"}}
    ref = {"ref": "refs/heads/main", "object": {"type": "commit", "sha": data["baseBranchOid"]}}
    result = [json.dumps(raw), json.dumps(ref)]
    for number, name in enumerate(("checks", "web", "audit")):
        item = data["ciEvidence"][name]
        result.extend([json.dumps(item["job"]), CHECKOUT_LOG])
        if number == 0:
            result.append(json.dumps(item["commit"]))
    result.extend([json.dumps(raw), json.dumps(ref)])
    return [subprocess.CompletedProcess([], 0, output, "") for output in result]


class HandoffTests(unittest.TestCase):
    def test_current_review_and_ci_pass(self) -> None:
        self.assertEqual(check_handoff(fixture(), now=NOW), (BASE, HEAD))

    def test_stale_head_or_base_fails(self) -> None:
        for field in ("headRefOid", "baseBranchOid"):
            with self.subTest(field=field):
                data = fixture()
                data[field] = "c" * 40
                with self.assertRaisesRegex(HandoffError, "устарело"):
                    check_handoff(data, now=NOW)

    def test_unknown_current_sha_cannot_use_review_sha(self) -> None:
        for field in ("headRefOid", "baseBranchOid"):
            for value in (None, "", "abc", "0" * 40, 42):
                with self.subTest(field=field, value=value):
                    data = fixture()
                    data[field] = value
                    with self.assertRaisesRegex(HandoffError, "Неизвестна"):
                        check_handoff(data, now=NOW)

    def test_missing_and_closed_pr_fail(self) -> None:
        for state in (None, "CLOSED", "MERGED"):
            data = fixture()
            data["state"] = state
            with self.subTest(state=state), self.assertRaises(HandoffError):
                check_handoff(data, now=NOW)
        with self.assertRaises(HandoffError):
            check_handoff(None, now=NOW)

    def test_each_required_check_must_exist(self) -> None:
        for name in ("checks", "web", "audit"):
            data = fixture()
            data["statusCheckRollup"] = [c for c in data["statusCheckRollup"] if c["name"] != name]
            with self.subTest(name=name), self.assertRaisesRegex(HandoffError, name):
                check_handoff(data, now=NOW)

    def test_unfinished_failed_or_skipped_check_is_not_green(self) -> None:
        for status, conclusion in (
            ("QUEUED", ""),
            ("IN_PROGRESS", "SUCCESS"),
            ("COMPLETED", "FAILURE"),
            ("COMPLETED", "CANCELLED"),
            ("COMPLETED", "SKIPPED"),
            ("COMPLETED", "NEUTRAL"),
        ):
            data = fixture()
            data["statusCheckRollup"][1].update(status=status, conclusion=conclusion)
            with (
                self.subTest(status=status, conclusion=conclusion),
                self.assertRaisesRegex(HandoffError, "web"),
            ):
                check_handoff(data, now=NOW)

    def test_ambiguous_check_cannot_hide_failure_behind_success(self) -> None:
        data = fixture()
        data["statusCheckRollup"].append(dict(data["statusCheckRollup"][0], conclusion="FAILURE"))
        with self.assertRaisesRegex(HandoffError, "Неоднозначный"):
            check_handoff(data, now=NOW)

    def test_later_fail_revokes_pass_even_with_reversed_api_order(self) -> None:
        data = fixture()
        data["comments"].insert(0, comment(created="2026-10-02T11:30:00Z", verdict="fail"))
        with self.assertRaisesRegex(HandoffError, "не pass"):
            check_handoff(data, now=NOW)

    def test_new_pass_supersedes_old_fail_but_unrelated_comment_does_not(self) -> None:
        data = fixture()
        data["comments"].insert(0, comment(created="2026-10-02T10:00:00Z", verdict="fail"))
        data["comments"].append({"body": "CI looks green", "createdAt": "2026-10-02T11:50:00Z"})
        self.assertEqual(check_handoff(data, now=NOW), (BASE, HEAD))

    def test_new_stale_receipt_cannot_fall_back_to_earlier_current_pass(self) -> None:
        data = fixture()
        data["comments"].append(comment(created="2026-10-02T11:30:00Z", head="c" * 40))
        with self.assertRaisesRegex(HandoffError, "устарело"):
            check_handoff(data, now=NOW)

    def test_missing_malformed_and_future_receipts_fail(self) -> None:
        bad_comments = [
            [],
            [comment(created="2026-10-03T10:00:00Z")],
            [comment(created="not a date")],
            [comment(created="2026-10-02T10:00:00")],
            [dict(comment(), body="<!-- sfr-review {broken} -->")],
            [dict(comment(), body="<!-- sfr-review {}")],
            [dict(comment(), body="<!-- sfr-review [] -->")],
            [dict(comment(), body=comment()["body"] * 2)],
            [comment(blocking_findings=1)],
            [comment(blocking_findings=False)],
            [comment(head="abc")],
            [comment(reviewer="author")],
            [comment(future_schema=2)],
        ]
        for comments in bad_comments:
            with self.subTest(comments=comments):
                data = fixture()
                data["comments"] = comments
                with self.assertRaises(HandoffError):
                    check_handoff(data, now=NOW)

    def test_later_malformed_json_revokes_previous_pass(self) -> None:
        data = fixture()
        data["comments"].append(
            {"body": "<!-- sfr-review {not json} -->", "createdAt": "2026-10-02T11:30:00Z"}
        )
        with self.assertRaisesRegex(HandoffError, "JSON"):
            check_handoff(data, now=NOW)

    def test_duplicated_json_verdict_is_rejected(self) -> None:
        data = fixture()
        data["comments"][0]["body"] = comment()["body"].replace(
            '"verdict": "pass"', '"verdict": "fail", "verdict": "pass"'
        )
        with self.assertRaisesRegex(HandoffError, "Повторяющиеся"):
            check_handoff(data, now=NOW)

    def test_refreshed_review_cannot_accept_ci_from_old_base(self) -> None:
        data = fixture()
        # GraphQL baseRefOid can still report BASE after the live branch advances.
        data["baseBranchOid"] = "d" * 40
        data["comments"] = [comment(base="d" * 40)]
        with self.assertRaisesRegex(HandoffError, "merge.*base/head"):
            check_handoff(data, now=NOW)

    def test_missing_ci_evidence_and_wrong_merge_fail(self) -> None:
        for change in (
            {"checkoutSha": HEAD},
            {"checkoutSha": "0" * 40},
            {"commit": {"sha": MERGE, "parents": [{"sha": HEAD}, {"sha": BASE}]}},
            {"commit": {"sha": MERGE, "parents": [{"sha": BASE}]}},
            {"commit": None},
        ):
            data = fixture()
            data["ciEvidence"]["audit"].update(change)
            with self.subTest(change=change), self.assertRaises(HandoffError):
                check_handoff(data, now=NOW)
        data = fixture()
        del data["ciEvidence"]
        with self.assertRaisesRegex(HandoffError, "нет доказательств"):
            check_handoff(data, now=NOW)

    def test_wrong_or_changed_job_cannot_borrow_checkout_evidence(self) -> None:
        for key, value in (
            ("id", 999),
            ("run_id", 501),
            ("name", "other"),
            ("html_url", "other"),
            ("head_sha", "d" * 40),
            ("status", "in_progress"),
            ("conclusion", "failure"),
        ):
            data = fixture()
            data["ciEvidence"]["web"]["job"][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(HandoffError, "job"):
                check_handoff(data, now=NOW)

    def test_checkout_log_must_have_one_complete_unambiguous_sha(self) -> None:
        self.assertEqual(checkout_sha(CHECKOUT_LOG), MERGE)
        for log in (
            "",
            CHECKOUT_LOG * 2,
            CHECKOUT_LOG.splitlines()[0],
            CHECKOUT_LOG.replace(MERGE, "abc"),
            CHECKOUT_LOG.replace(MERGE, "0" * 40),
            CHECKOUT_LOG.replace("git log -1 --format=%H", "echo git log -1 --format=%H"),
        ):
            with self.subTest(log=log), self.assertRaises(HandoffError):
                checkout_sha(log)

    def test_job_url_must_belong_to_this_repo_and_have_exact_ids(self) -> None:
        for url in (
            None,
            "https://example.com/job/100",
            "https://github.com/other/repo/actions/runs/500/job/100",
        ):
            data = fixture()
            data["statusCheckRollup"][0]["detailsUrl"] = url
            with self.subTest(url=url), self.assertRaisesRegex(HandoffError, "ссылки"):
                check_handoff(data, now=NOW)

    @patch("check_handoff.subprocess.run")
    def test_cli_only_reads_explicit_repo_and_pr(self, run: Mock) -> None:
        data = fixture()
        data["comments"][0]["createdAt"] = "2000-01-01T00:00:00Z"
        run.side_effect = api_responses(data)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--pr", "176"]), 0)
        self.assertEqual(
            run.call_args_list[0].args[0],
            ["gh", "pr", "view", "--repo", REPO, "176", "--json", FIELDS],
        )
        self.assertEqual(run.call_count, 11)
        self.assertEqual(run.call_args_list[-2].args[0], run.call_args_list[0].args[0])
        for call in run.call_args_list[1:-2] + run.call_args_list[-1:]:
            self.assertEqual(call.args[0][:4], ["gh", "api", "--method", "GET"])
            self.assertTrue(call.args[0][-1].startswith(f"repos/{REPO}/"))

    @patch("check_handoff.subprocess.run")
    def test_cli_rejects_pr_changes_during_evidence_collection(self, run: Mock) -> None:
        data = fixture()
        data["comments"][0]["createdAt"] = "2000-01-01T00:00:00Z"
        for field, value in (
            ("baseBranchOid", "d" * 40),
            ("headRefOid", "e" * 40),
            ("state", "CLOSED"),
        ):
            changed = deepcopy(data)
            changed[field] = value
            responses = api_responses(data)
            responses[-2:] = api_responses(changed)[-2:]
            run.side_effect = responses
            with self.subTest(field=field), redirect_stderr(io.StringIO()):
                self.assertEqual(main(["--pr", "176"]), 1)

    @patch("check_handoff.subprocess.run")
    def test_cli_unavailable_logs_fail_without_printing_raw_output(self, run: Mock) -> None:
        data = fixture()
        data["comments"][0]["createdAt"] = "2000-01-01T00:00:00Z"
        responses = api_responses(data)
        responses[3] = subprocess.CompletedProcess([], 1, "private log", "signed redirect")
        run.side_effect = responses
        error = io.StringIO()
        with redirect_stderr(error):
            self.assertEqual(main(["--pr", "176"]), 1)
        self.assertNotIn("private log", error.getvalue())
        self.assertNotIn("signed redirect", error.getvalue())

    @patch("check_handoff.subprocess.run")
    def test_cli_missing_or_invalid_pr_does_not_call_gh(self, run: Mock) -> None:
        for args in ([], ["--pr", "0"], ["--pr", "--web"], ["--pr", "main"]):
            with self.subTest(args=args), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as exc:
                    main(args)
                self.assertEqual(exc.exception.code, 2)
        run.assert_not_called()

    @patch("check_handoff.subprocess.run")
    def test_cli_network_failure_and_invalid_json_fail_closed(self, run: Mock) -> None:
        for response in (
            subprocess.CompletedProcess([], 1, "", "access failed"),
            subprocess.CompletedProcess([], 0, "not JSON", ""),
            subprocess.CompletedProcess([], 0, "null", ""),
        ):
            run.return_value = response
            with self.subTest(response=response), redirect_stderr(io.StringIO()):
                self.assertEqual(main(["--pr", "176"]), 1)


if __name__ == "__main__":
    unittest.main()
