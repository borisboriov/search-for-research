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
from enrichment_night import bind, locked, permission, remaining, run


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
                        "method": "enrichment-cli-bounded-v1",
                        "sample_sha256": sha(root / "sample.json"),
                        "rules_hashes": {"scripts/enrichment_night.py": "0" * 64},
                    }
                ),
            )
            with self.assertRaisesRegex(ValueError, "новый раунд"):
                locked(root)


if __name__ == "__main__":
    unittest.main()
