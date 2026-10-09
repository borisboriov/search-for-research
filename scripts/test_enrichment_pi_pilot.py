"""Регрессии границ свежего пилота без сети и LLM."""

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from enrichment_batch import Batch, encoded, immutable
from enrichment_experiment import FIELDS, sha
from enrichment_pi_pilot import (
    final_json,
    import_pi,
    policy,
    reader_body,
    reserve,
    run_pi,
    validate_collection,
)


class PilotTests(unittest.TestCase):
    def fixture(self, root: Path) -> Batch:
        immutable(root / "sample.json", encoded([{"id": "A1"}, {"id": "A2"}]))
        immutable(root / "manifest.json", encoded({"sample_sha256": sha(root / "sample.json")}))
        immutable(root / "rules.md", b"fixed rules")
        batch = Batch.create(
            root / "batches" / "01", root, ["A1"], root / "rules.md", concurrency=1
        )
        batch.ticket("A1", "collect")
        return batch

    def test_nested_json_body_excludes_metadata(self) -> None:
        result = {
            "content": [
                {
                    "text": json.dumps(
                        json.dumps(
                            {
                                "url": "https://official.test",
                                "content": "Exact\nquote",
                                "metadata": {"note": "not body"},
                            }
                        )
                    )
                }
            ]
        }
        self.assertEqual(reader_body(result), "Exact\nquote")
        self.assertNotIn("not body", reader_body(result))
        self.assertEqual(final_json('```json\n{"x":1}\n```'), {"x": 1})

    def test_global_counter_recovers_batch_charge_without_auxiliary_event(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            batch = self.fixture(root)
            operation = batch.reserve("A1-collect", "search", "first")
            batch.finish_operation(operation, "ok")
            with patch("enrichment_pi_pilot.events", return_value=[]):
                operation = reserve(root, batch, "A1", "search", "second")
            batch.finish_operation(operation, "ok")
            operation = reserve(root, batch, "A1", "search", "third")
            batch.finish_operation(operation, "ok")
            operation = reserve(root, batch, "A1", "search", "fourth")
            batch.finish_operation(operation, "ok")
            with self.assertRaisesRegex(ValueError, "Бюджет"):
                reserve(root, batch, "A1", "search", "fifth")

    def test_unknown_attempt_never_relaunches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            batch = self.fixture(root)
            immutable(root / "runs" / "A1" / "collector" / "started.json", b"{}")
            with patch("enrichment_pi_pilot.subprocess.Popen") as launch:
                with self.assertRaisesRegex(ValueError, "Незавершённая"):
                    run_pi(root, batch, "A1", "collector", {}, "rules", {})
                launch.assert_not_called()

    def test_service_refusal_survives_next_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            batch = self.fixture(root)
            immutable(root / "pilot-events" / "000000.json", encoded({"action": "service_stopped"}))
            with patch("enrichment_pi_pilot.subprocess.Popen") as launch:
                with self.assertRaisesRegex(ValueError, "остановлен"):
                    run_pi(root, batch, "A2", "collector", {}, "rules", {})
                launch.assert_not_called()

    def test_private_dns_never_contacts_policy_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            batch = self.fixture(root)
            with (
                patch(
                    "enrichment_pi_pilot.socket.getaddrinfo",
                    return_value=[(2, 1, 6, "", ("10.2.3.4", 443))],
                ),
                patch("enrichment_pi_pilot.httpx.Client") as network,
            ):
                with self.assertRaisesRegex(ValueError, "непубличный"):
                    policy(root, batch, "A1", "https://official.test/person")
                network.assert_not_called()

    def test_found_requires_actual_atom(self) -> None:
        raw: dict[str, Any] = {
            "field_statuses": dict.fromkeys(FIELDS, "not_checked"),
            "items": [],
            "profile_evidence": {"identity": [], "current_affiliation": []},
            "evidence_pool": {},
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertEqual(validate_collection(root, "A1", raw), {})
            raw["field_statuses"]["workload"] = "found"
            with self.assertRaisesRegex(ValueError, "без атома"):
                validate_collection(root, "A1", raw)

    def test_failed_pi_import_is_not_success(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            immutable(
                root / "finished.json",
                encoded({"done": False, "exit_code": 0, "pending_operations": []}),
            )
            with self.assertRaisesRegex(ValueError, "не завершён"):
                import_pi(root, "A1", "collector")
            self.assertFalse((root / "receipt.json").exists())

    def test_http_capture_latches_without_auxiliary_event(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            batch = self.fixture(root)
            immutable(
                root / "runs" / "A1" / "collector" / "pi" / "000001-http.json",
                encoded({"status": 429}),
            )
            with patch("enrichment_pi_pilot.subprocess.Popen") as launch:
                with self.assertRaisesRegex(ValueError, "остановлен"):
                    run_pi(root, batch, "A2", "collector", {}, "rules", {})
                launch.assert_not_called()

    def test_mcp_refusal_search_latches_without_http_status(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            batch = self.fixture(root)
            operation = batch.reserve("A1-collect", "search", "search target has no domain")
            batch.finish_operation(operation, "429")
            with patch("enrichment_pi_pilot.subprocess.Popen") as launch:
                with self.assertRaisesRegex(ValueError, "остановлен"):
                    run_pi(root, batch, "A2", "collector", {}, "rules", {})
                launch.assert_not_called()

    def test_prefixed_json_import_without_another_call(self) -> None:
        self.assertEqual(
            final_json('Итоговый JSON:\n```json\n{"author_id":"A1"}\n```'), {"author_id": "A1"}
        )
