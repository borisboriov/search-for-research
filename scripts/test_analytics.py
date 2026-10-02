"""Synthetic report oracle: logical order, per-attempt funnel and private HTML."""

from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from analytics import instant, summarize, write_report


class ReportTests(unittest.TestCase):
    def fixture(self) -> dict[str, Any]:
        events = []

        def event(name: str, visit: str, search: str | None, seq: int, **data: object) -> None:
            events.append(
                {
                    "event_id": f"{visit}-{seq}",
                    "visit_id": visit,
                    "search_id": search,
                    "name": name,
                    "client_seq": seq,
                    "received_at": "2026-10-02T12:00:00Z",
                    "client_at": "1999-01-01T00:00:00Z",
                    "data": data,
                }
            )

        event("visit_started", "v1", None, 1, viewport="mobile")
        event("search_attempt", "v1", "s1", 2)
        event("results_shown", "v1", "s1", 3, elapsed_ms=150)
        event("profile_opened", "v1", "s1", 4, author_id="A1")
        event("letter_copy_success", "v1", "s1", 5, author_id="A1")
        event("search_attempt", "v1", "s2", 6)
        event("weak_shown", "v1", "s2", 7, elapsed_ms=300)
        # This late letter must NOT complete s2 by borrowing s1 profile.
        event("letter_copy_success", "v1", "s2", 8)
        event("visit_started", "v2", None, 1, viewport="desktop")
        event("profile_direct", "v2", None, 2)
        event("visit_started", "v3", None, 1, viewport="desktop")
        event("search_attempt", "v3", "s3", 2)
        event("empty_shown", "v3", "s3", 3, elapsed_ms=600)
        event("search_attempt", "v3", "s4", 4)
        event("search_error", "v3", "s4", 5, status=503)
        searches = [
            {
                "search_id": f"s{i}",
                "visit_id": "v1" if i < 3 else "v3",
                "received_at": "2026-10-02T12:00:00Z",
                "persisted_at": "2026-10-02T12:01:00Z",
                "outcome": "success" if i != 4 else "error",
                "status": 200 if i != 4 else 503,
                "payload": {
                    "confidence": ["ok", "weak", "none", None][i - 1],
                    "wall_ms": i * 100,
                    "traffic_type": "suspected_bot" if i == 3 else "unclassified",
                    "app_version": "<script>alert(1)</script>",
                    "index_version": "synthetic",
                },
            }
            for i in range(1, 5)
        ]
        return {
            "schema_version": 1,
            "analytics_searches": searches,
            "analytics_events": [*reversed(events), events[0]],
            "analytics_context": [
                {
                    "search_id": "s3",
                    "diagnostic_headers": {"user-agent": "SyntheticBot"},
                    "raw_query": "PRIVATE_PERSON_AND_SECRET",
                }
            ],
        }

    def test_oracle_no_cross_attempt_or_duplicate_inflation(self) -> None:
        summary = summarize(
            self.fixture(),
            instant("2026-10-02", "Europe/Moscow"),
            instant("2026-10-03", "Europe/Moscow"),
        )
        self.assertEqual(
            summary["funnel_visits"],
            {"visit": 2, "attempt": 1, "display": 1, "profile": 1, "letter_copy": 1},
        )
        self.assertEqual(
            summary["funnel_attempts"],
            {"visit": 2, "attempt": 2, "display": 2, "profile": 1, "letter_copy": 1},
        )
        self.assertEqual(summary["repeat_attempts"], 1)
        self.assertEqual(summary["direct_profiles"], 1)
        self.assertEqual(summary["replay_lag_max_seconds"], 60)
        self.assertEqual(summary["dimensions"]["confidence"], {"ok": 1, "weak": 1})
        self.assertEqual(summary["excluded_visits"], {"suspected_bot": 1})
        self.assertGreater(summary["clock_anomalies"], 0)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report"
            write_report(summary, path, "Europe/Moscow")
            page = (path / "report.html").read_text()
            self.assertNotIn("PRIVATE_PERSON_AND_SECRET", page)
            self.assertNotIn("<script>", page)
            self.assertIn("&lt;script&gt;", page)
            self.assertEqual((path / "summary.json").stat().st_mode & 0o777, 0o600)

    def test_copy_requires_same_profile_but_allows_second_opened_profile(self) -> None:
        data = self.fixture()
        for row in data["analytics_events"]:
            if row["name"] == "letter_copy_success" and row["search_id"] == "s1":
                row["data"]["author_id"] = "A2"
        start, end = instant("2026-10-02", "UTC"), instant("2026-10-03", "UTC")
        self.assertEqual(summarize(data, start, end)["funnel_attempts"]["letter_copy"], 0)
        # Change first profile to a second selected author (same attempt).
        for row in data["analytics_events"]:
            if row["name"] == "profile_opened" and row["search_id"] == "s1":
                row["data"]["author_id"] = "A2"
        self.assertEqual(summarize(data, start, end)["funnel_attempts"]["letter_copy"], 1)

    def test_private_directory_does_not_change_shared_permissions(self) -> None:
        from analytics import private_dir

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            path.chmod(0o755)
            with self.assertRaises(PermissionError):
                private_dir(path)
            self.assertEqual(path.stat().st_mode & 0o777, 0o755)

    def test_timezone_boundaries(self) -> None:
        self.assertEqual(
            instant("2026-10-02T00:00:00", "Europe/Moscow"), datetime(2026, 10, 1, 21, tzinfo=UTC)
        )
        self.assertEqual(
            instant("2026-10-02T00:00:00Z", "Europe/Moscow"), datetime(2026, 10, 2, tzinfo=UTC)
        )
        with self.assertRaises(ValueError):
            instant("2026-10-25T02:30:00", "Europe/Berlin")
