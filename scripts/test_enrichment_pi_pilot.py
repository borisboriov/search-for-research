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

    def test_raw_mcp_refusal_latches_before_operation_ack(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            batch = self.fixture(root)
            immutable(
                root / "runs" / "A1" / "collector" / "pi" / "000003-mcp-response.json",
                encoded(
                    {
                        "server": "zai_search",
                        "message": {
                            "result": {"isError": True, "content": [{"text": "Quota exceeded 429"}]}
                        },
                    }
                ),
            )
            with patch("enrichment_pi_pilot.subprocess.Popen") as launch:
                with self.assertRaisesRegex(ValueError, "остановлен"):
                    run_pi(root, batch, "A2", "collector", {}, "rules", {})
                launch.assert_not_called()

    def test_full_pair_queue_import_with_unsupported_atom_and_no_network(self) -> None:
        from enrichment_pi_pilot import finish_artifacts, run_profile

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            profiles = [
                {"id": f"A{i}", "name": "Тест", "institution": "Тест", "institution_id": "I1"}
                for i in range(1, 13)
            ]
            immutable(root / "sample.json", encoded(profiles))
            immutable(root / "manifest.json", encoded({"sample_sha256": sha(root / "sample.json")}))
            from enrichment_pi_pilot import COLLECT_RULES

            batches = [
                Batch.create(
                    root / "batches" / f"{i + 1:02d}", root, [p["id"]], COLLECT_RULES, concurrency=1
                )
                for i, p in enumerate(profiles)
            ]

            def assessment(task: dict[str, Any]) -> dict[str, Any]:
                source = task["semantic_input"]
                axis = {
                    "verdict": "insufficient",
                    "evidence_refs": [],
                    "information_date": None,
                    "date_basis": "unknown",
                    "explanation": "Нет оснований.",
                }
                return {
                    k: task[k]
                    for k in ("author_id", "batch_ticket_id", "batch_input_sha256", "input_sha256")
                } | {
                    "rules_version": "semantic-v3",
                    "items": [
                        {
                            "item_id": item["item_id"],
                            "text_verdict": "insufficient",
                            "identity_verdict": "insufficient",
                            "field_verdict": "insufficient",
                            "corrected_field": None,
                            "fact_kind": "literal",
                            "object_type": "scientist",
                            "object_relation": "insufficient",
                            "student_level": ["unknown"],
                            "information_date": None,
                            "date_basis": "unknown",
                            "current_applicability": "unknown",
                            "evidence_refs": [],
                            "explanation": "Нет прочитанного доказательства.",
                            "question": "Есть ли первоисточник?",
                        }
                        for item in source["items"]
                    ],
                    "profile_assessments": {
                        "identity": axis,
                        "current_affiliation": axis,
                        "activity": axis | {"status": "unknown"},
                    },
                    "summary": dict.fromkeys(
                        ("known", "unknown", "identity", "current_opportunity"),
                        "Основания не установлены.",
                    ),
                }

            def pi_call(
                root: Path, batch: Batch, aid: str, stage: str, task: dict[str, Any], *args: Any
            ) -> Any:
                if stage == "collector":
                    value = {
                        k: task[k] for k in ("author_id", "batch_ticket_id", "batch_input_sha256")
                    } | {
                        "items": [
                            {
                                "item_id": aid + "_1",
                                "field": "personal_contact",
                                "value": "Неподтверждённый кандидат",
                                "evidence_refs": [],
                            }
                        ],
                        "evidence_pool": {},
                        "profile_evidence": {"identity": [], "current_affiliation": []},
                        "field_statuses": dict.fromkeys(FIELDS, "not_checked"),
                    }
                else:
                    value = assessment(task)
                path = root / "runs" / aid / stage / "result.json"
                immutable(path, encoded(value))
                return path, {
                    "agent_id": aid + "-" + stage,
                    "model": "fake",
                    "effort": "low",
                    "runtime_status": "recorded",
                    "tokens": 0,
                    "cost_usd": None,
                }

            def native_call(directory: Path, prompt: str, *args: Any, **kwargs: Any) -> Any:
                task = json.loads(prompt.split("\nВХОД:\n")[-1])
                path = directory / "raw-result.json"
                immutable(path, encoded(assessment(task)))
                return path, {
                    "agent_id": task["author_id"] + "-native",
                    "runtime_status": "runtime_not_exposed",
                    "model": None,
                    "effort": None,
                    "tokens": {"input_tokens": 1, "output_tokens": 1},
                    "cost_usd": None,
                }

            with (
                patch("enrichment_pi_pilot.run_pi", side_effect=pi_call) as pi,
                patch("enrichment_pi_pilot.execute", side_effect=native_call) as native,
            ):
                for p, b in zip(profiles[:3], batches[:3], strict=True):
                    run_profile(root, p, b)
                finish_artifacts(root)
                self.assertEqual(pi.call_count, 6)
                self.assertEqual(native.call_count, 3)
            self.assertTrue((root / "paired-human" / "packets" / "pi12-01" / "cards.html").exists())
            for batch in batches[:3]:
                with batch.locked() as log:
                    self.assertIsNotNone(batch.completed(log, batch.config["ids"][0], "metrics"))
