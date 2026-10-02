"""Synthetic report oracle: logical order, per-attempt funnel and private HTML."""

from __future__ import annotations

import contextlib
import copy
import csv
import io
import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

from analytics import diagnostic_problems, instant, main, summarize, write_report


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
        # Keep A1 as the first opened profile; opening A2 later must qualify.
        for row in data["analytics_events"]:
            if row["visit_id"] == "v1" and row["client_seq"] >= 5:
                row["client_seq"] += 1
        data["analytics_events"].append(
            {
                "event_id": "v1-second-profile",
                "visit_id": "v1",
                "search_id": "s1",
                "name": "profile_opened",
                "client_seq": 5,
                "received_at": "2026-10-02T12:00:00Z",
                "client_at": "1999-01-01T00:00:00Z",
                "data": {"author_id": "A2"},
            }
        )
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

    def test_attempt_csv_denominators_use_one_unit(self) -> None:
        data = self.fixture()
        data["analytics_events"] = [e for e in data["analytics_events"] if e["visit_id"] == "v1"]
        data["analytics_searches"] = [
            s for s in data["analytics_searches"] if s["visit_id"] == "v1"
        ]
        summary = summarize(data, instant("2026-10-02", "UTC"), instant("2026-10-03", "UTC"))
        self.assertEqual(summary["funnel_attempts"]["attempt"], 2)
        self.assertEqual(summary["funnel_visits"]["attempt"], 1)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "report"
            write_report(summary, out, "UTC")
            with (out / "funnel.csv").open(newline="") as stream:
                rows = {r["stage"]: r for r in csv.DictReader(stream)}
            self.assertEqual(rows["visit"]["denominator_attempts"], "")
            self.assertEqual(rows["attempt"]["denominator_attempts"], "")
            self.assertEqual(rows["attempt"]["denominator_visits"], "1")
            self.assertEqual(rows["display"]["denominator_attempts"], "2")
            self.assertEqual(rows["profile"]["denominator_attempts"], "2")
            self.assertEqual(rows["letter_copy"]["denominator_attempts"], "1")

    def test_sequence_gaps_only_count_missing_internal_observations(self) -> None:
        def event(seq: int, received: str) -> dict[str, Any]:
            return {
                "event_id": f"event-{seq}",
                "visit_id": "visit",
                "search_id": None,
                "client_seq": seq,
                "name": "visit_started" if seq == 5 else "profile_direct",
                "received_at": received,
                "client_at": "2026-10-02T12:00:00Z",
                "data": {},
            }

        data: dict[str, Any] = {
            "schema_version": 1,
            "analytics_searches": [],
            "analytics_context": [],
            "analytics_events": [event(5, "2026-10-02T12:00:00Z")],
        }
        start, end = instant("2026-10-02", "UTC"), instant("2026-10-03", "UTC")
        prefix = summarize(data, start, end)
        self.assertEqual(prefix["observed_sequence_gap_count"], 0)
        self.assertEqual(prefix["visits_with_sequence_gaps"], 0)
        data["analytics_events"].append(event(8, "2026-10-02T12:00:00Z"))
        data["analytics_events"].append(copy.deepcopy(data["analytics_events"][0]))
        missing = summarize(data, start, end)
        self.assertEqual(missing["observed_sequence_gap_count"], 2)
        self.assertEqual(missing["observed_sequence_gap_intervals"], 1)
        self.assertEqual(missing["visits_with_sequence_gaps"], 1)
        self.assertEqual(
            missing["traffic_groups"]["unclassified"]["observed_sequence_gap_count"], 2
        )
        # Delivery after the original period cannot silently alter that cohort.
        data["analytics_events"].extend(
            [
                event(6, "2026-10-03T01:00:00Z"),
                event(7, "2026-10-03T01:00:00Z"),
            ]
        )
        self.assertEqual(summarize(data, start, end)["observed_sequence_gap_count"], 2)
        filled = summarize(data, start, instant("2026-10-04", "UTC"))
        self.assertEqual(filled["observed_sequence_gap_count"], 0)
        self.assertEqual(filled["visits_with_sequence_gaps"], 0)


class DiagnosticsTests(unittest.TestCase):
    def clean(self) -> dict[str, Any]:
        return {
            "database_available": True,
            "migration": "analytics_0003",
            "expected_migration": "analytics_0003",
            "migration_current": True,
            "pending_count": 0,
            "quarantine_count": 0,
            "error_count": 0,
            "incomplete": False,
            "last_error": None,
            "disk_free_bytes": 1000,
            "reserve_bytes": 100,
        }

    def test_operator_policy_rejects_nonclean_states_without_changing_history(self) -> None:
        cases = (
            ({"database_available": False}, "database_unavailable"),
            ({"migration": "analytics_0001", "migration_current": False}, "migration_not_current"),
            ({"migration": "analytics_0002", "migration_current": False}, "migration_not_current"),
            ({"migration": "analytics_0002", "migration_current": True}, "migration_not_current"),
            ({"pending_count": 1}, "pending_records"),
            ({"quarantine_count": 1}, "quarantined_records"),
            ({"incomplete": True}, "incomplete_observations"),
            ({"error_count": 4, "last_error": None}, "historical_errors"),
            ({"last_error": "disk_write"}, "unresolved_storage_error"),
            ({"disk_free_bytes": 50}, "disk_below_reserve"),
        )
        self.assertEqual(diagnostic_problems(self.clean()), [])
        for updates, expected in cases:
            with self.subTest(updates=updates):
                state = {**self.clean(), **updates}
                before = copy.deepcopy(state)
                self.assertIn(expected, diagnostic_problems(state))
                self.assertEqual(state, before)

    def test_check_cli_returns_policy_status_and_preserves_error_evidence(self) -> None:
        # These mocks test the operator exit decision, not database persistence.
        # Persistence/migrations remain covered by the separate actual PG suite.
        cases: tuple[tuple[dict[str, Any], bool, int, str | None], ...] = (
            ({}, False, 0, None),
            ({}, True, 1, "database_unavailable"),
            ({"migration": "analytics_0001"}, False, 1, "migration_not_current"),
            ({"migration": "analytics_0002"}, False, 1, "migration_not_current"),
            ({"pending_count": 1}, False, 1, "pending_records"),
            ({"quarantine_count": 1}, False, 1, "quarantined_records"),
            ({"incomplete": True}, False, 1, "incomplete_observations"),
            ({"error_count": 3, "last_error": None}, False, 1, "historical_errors"),
        )
        with tempfile.TemporaryDirectory() as directory:
            settings = SimpleNamespace(
                analytics_database_url="postgresql+psycopg://synthetic@localhost/synthetic",
                analytics_spool_dir=Path(directory),
            )
            for updates, unavailable, expected_exit, expected_reason in cases:
                with self.subTest(updates=updates, unavailable=unavailable):
                    state = {**self.clean(), **updates}
                    engine = MagicMock()
                    connection = engine.connect.return_value.__enter__.return_value
                    connection.execute.return_value.scalar.return_value = state["migration"]
                    connection.execute.return_value.mappings.return_value.one.return_value = {
                        "count": 0,
                        "last_received_at": None,
                        "last_persisted_at": None,
                    }
                    if unavailable:
                        engine.connect.side_effect = RuntimeError("PRIVATE_DRIVER_ERROR")
                    output = io.StringIO()
                    with (
                        patch("sys.argv", ["analytics.py", "check"]),
                        patch("sfr_api.settings.ApiSettings", return_value=settings),
                        patch("sfr_api.analytics.store.DurableStore") as store,
                        patch(
                            "analytics.database_url", return_value=settings.analytics_database_url
                        ),
                        patch("analytics.create_engine", return_value=engine),
                        patch("alembic.script.ScriptDirectory.from_config") as migration,
                        contextlib.redirect_stdout(output),
                    ):
                        store.return_value.diagnostics.return_value = state
                        migration.return_value.get_current_head.return_value = "analytics_0003"
                        self.assertEqual(main(), expected_exit)
                    observed = json.loads(output.getvalue())
                    self.assertEqual(observed["check_ok"], expected_exit == 0)
                    if expected_reason:
                        self.assertIn(expected_reason, observed["check_reasons"])
                    else:
                        self.assertEqual(observed["check_reasons"], [])
                    self.assertEqual(observed["error_count"], updates.get("error_count", 0))
                    self.assertEqual(observed["last_error"], updates.get("last_error"))
                    self.assertNotIn("PRIVATE_DRIVER_ERROR", output.getvalue())
