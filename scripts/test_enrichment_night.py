"""Регрессии ограниченного CLI-пути без источников и model inference."""

import tempfile
import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from enrichment_batch import Batch, encoded, immutable
from enrichment_experiment import FIELDS, sha
from enrichment_native import deadline_timeout
from enrichment_night import (
    METHOD,
    bind,
    completion_status,
    host_events,
    locked,
    permission,
    remaining,
    require_access,
    run,
)


class FakeBatch:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = rows or []

    @contextmanager
    def locked(self) -> Iterator[list[dict[str, Any]]]:
        yield self.rows


class BoundedTests(unittest.TestCase):
    def test_hidden_robots_are_counted_separately_in_exact_remaining(self) -> None:
        rows = [
            {
                "action": "reserved",
                "cached": False,
                "ticket_id": "a-collect",
                "kind": kind,
                "target": target,
            }
            for kind, target in (
                ("search", "query"),
                ("page", "https://example.com/robots.txt"),
                ("page", "https://example.com/person"),
            )
        ]
        self.assertEqual(
            remaining(cast(Batch, FakeBatch(rows)), "a"),
            {
                "search_remaining": 3,
                "resources_remaining_including_robots": 6,
                "host_robots": 1,
                "source_reads": 1,
            },
        )

    def test_model_robots_denied_before_any_policy_or_reservation(self) -> None:
        row = {
            "id": "reservation-1",
            "server": "zai_reader",
            "tool": "webReader",
            "rpc_id": 1,
            "arguments": {"url": "https://example.com/robots.txt"},
        }
        with (
            patch("enrichment_night.access_stopped", return_value=False),
            patch("enrichment_night.time.monotonic", return_value=10),
            patch("enrichment_night.policy") as policy_mock,
            patch("enrichment_night.reserve") as reserve_mock,
            patch("enrichment_night.event"),
        ):
            result = permission(Path("/unused"), cast(Batch, FakeBatch()), "a", row, 0, {})
        self.assertFalse(result["allowed"])
        policy_mock.assert_not_called()
        reserve_mock.assert_not_called()

    def test_timeout_phase_denies_before_any_source_request(self) -> None:
        with (
            patch("enrichment_night.time.monotonic", return_value=361),
            patch("enrichment_night.event"),
            patch("enrichment_night.reserve") as reserve_mock,
        ):
            result = permission(Path("/unused"), cast(Batch, FakeBatch()), "a", {"id": "1"}, 0, {})
        self.assertFalse(result["allowed"])
        reserve_mock.assert_not_called()

    def test_nonliteral_quote_is_preserved_as_rejection_and_not_given_to_verifier(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            immutable(
                root / "source.json",
                encoded(
                    {
                        "message": {
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": '{"content":"Official exact sentence."}',
                                    }
                                ]
                            }
                        }
                    }
                ),
            )
            source = {
                "action": "source_finished",
                "author_id": "a",
                "kind": "zai_reader",
                "outcome": "ok",
                "arguments": {"url": "https://example.com/person"},
                "raw_file": "source.json",
                "checked_at": "2026-10-09",
            }
            evidence = {
                "url": "https://example.com/person",
                "excerpt": "invented paraphrase",
                "information_date": None,
                "object_type": "scientist",
            }
            raw: dict[str, Any] = {
                "items": [
                    {
                        "item_id": "c1",
                        "field": "personal_contact",
                        "value": "candidate",
                        "evidence_refs": ["e1"],
                    }
                ],
                "evidence_pool": {"e1": evidence},
                "profile_evidence": {"identity": ["e1"], "current_affiliation": []},
                "field_statuses": {
                    field: "found" if field == "personal_contact" else "not_checked"
                    for field in FIELDS
                },
            }
            with patch("enrichment_night.events", return_value=[source]):
                result, pool, rejected = bind(root, "a", raw)
            self.assertEqual(pool, {})
            self.assertEqual(result["items"], [])
            self.assertEqual(result["field_statuses"]["personal_contact"], "not_checked")
            self.assertEqual(raw["evidence_pool"]["e1"], evidence)
            self.assertEqual(len(rejected), 2)

    def test_stop_is_checked_before_any_new_job(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            immutable(root / "stopped.json", encoded({"reason": "saved failure"}))
            with patch("enrichment_night.locked"), patch("enrichment_night.run_profile") as launch:
                with self.assertRaises(ValueError):
                    run(root, 1)
                launch.assert_not_called()

    def test_modified_code_rejects_resume(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            immutable(root / "sample.json", encoded([]))
            immutable(
                root / "manifest.json",
                encoded(
                    {
                        "method": METHOD,
                        "sample_sha256": sha(root / "sample.json"),
                        "rules_hashes": {"scripts/enrichment_night.py": "0" * 64},
                    }
                ),
            )
            with self.assertRaisesRegex(ValueError, "новый раунд"):
                locked(root)


class SafetyRegressionTests(unittest.TestCase):
    def test_quota_denies_completed_classification_and_dependent_job(self) -> None:
        self.assertEqual(completion_status(True, 0, {}, True), "access_refused_partial_unknown")
        with (
            patch("enrichment_night.access_stopped", return_value=True),
            self.assertRaisesRegex(ValueError, "STOP"),
        ):
            require_access(Path("/unused"))

    def test_file_ipc_delivers_once_in_order_without_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for seq, kind in ((3, "done"), (1, "reserve"), (2, "mcp_result")):
                immutable(root / f"{seq:06d}-host-event.json", encoded({"type": kind}))
            seen: set[str] = set()
            self.assertEqual(
                [row["type"] for row in host_events(root, seen)], ["reserve", "mcp_result", "done"]
            )
            self.assertEqual(host_events(root, seen), [])

    def test_absolute_deadline_limits_probe_and_remaining_inference_together(self) -> None:
        with patch("enrichment_native.time.time", side_effect=[100, 125, 151]):
            self.assertEqual(deadline_timeout(30, 150), 30)
            self.assertEqual(deadline_timeout(600, 150), 25)
            with self.assertRaisesRegex(ValueError, "deadline"):
                deadline_timeout(600, 150)


if __name__ == "__main__":
    unittest.main()
