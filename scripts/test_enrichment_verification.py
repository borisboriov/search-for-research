"""Независимые вердикты, целостность входов и безопасная передача человеку."""

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from enrichment_experiment import FIELDS, read, sha, write_new
from enrichment_verification import (
    import_result,
    journal_check,
    metrics,
    operation_failed,
    packet,
    prepare,
    validate_result,
)


class VerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        write_new(self.root / "sample.json", [{"id": "A1", "name": "<script>alert(1)</script>"}])
        write_new(self.root / "manifest.json", {"sample_sha256": sha(self.root / "sample.json")})
        self.ev = {
            "url": "https://example.edu/person",
            "excerpt": "<img src=x onerror=alert(1)>",
            "information_date": None,
            "checked_at": "2026-10-09",
            "object_type": "scientist",
            "explanation": "Прямое заявление",
        }
        collector = {
            "author_id": "A1",
            "claims": [
                {
                    "claim_id": "c1",
                    "field": "personal_contact",
                    "value": "person@example.edu",
                    "evidence": [self.ev],
                }
            ],
            "field_status": dict.fromkeys(FIELDS, "not_checked"),
            "journal": [],
            "sources": [],
            "provenance": {"agent_id": "collector"},
        }
        self.collector = self.root / "collector.json"
        write_new(self.collector, collector)
        self.rubric = self.root / "rules.md"
        self.rubric.write_text("rules v2")
        self.input = prepare(self.root, self.collector, "v2", self.rubric)[0]

    def result(self) -> dict[str, Any]:
        verdict = {
            "verdict": "insufficient_evidence",
            "explanation": "Не установлено",
            "evidence": [],
        }
        return {
            "author_id": "A1",
            "input_sha256": sha(self.input),
            "rules_version": "v2",
            "provenance": {
                "model": None,
                "effort": None,
                "agent_id": "independent",
                "runtime_status": "runtime_not_exposed",
            },
            "identity": verdict,
            "current_affiliation": verdict,
            "claim_verdicts": [{"claim_id": "c1", **verdict}],
            "new_findings": [],
            "field_search": {
                field: {"status": "not_checked", "explanation": "Лимит"} for field in FIELDS
            },
            "journal": [],
            "questions": ["<script>check</script>"],
        }

    def test_resume_preserves_input(self) -> None:
        before = sha(self.input)
        prepare(self.root, self.collector, "v2", self.rubric)
        self.assertEqual(before, sha(self.input))
        self.rubric.write_text("different rules")
        with self.assertRaises(ValueError):
            prepare(self.root, self.collector, "v2", self.rubric)

    def test_source_snapshot_survives_spool_mutation(self) -> None:
        source = read(self.input)
        snapshot = self.root / source["collector_snapshot"]
        self.assertEqual(sha(snapshot), source["collector_sha256"])
        self.collector.write_text("[]")
        self.assertEqual(sha(snapshot), source["collector_sha256"])
        result_file = self.root / "result-source.json"
        write_new(result_file, self.result())
        import_result(self.root, self.input, result_file, "after-spool-mutation")

    def test_access_failure_aliases_are_not_lost(self) -> None:
        for status in ("inaccessible_rules_lookup", "rules_unavailable", "404_page_not_found"):
            self.assertTrue(operation_failed({"status": status}))
        self.assertFalse(operation_failed({"status": "search_engine_index_cache"}))

    def test_author_questions_are_not_verifier_inputs(self) -> None:
        value = read(self.collector)
        value["questions"] = ["author expects confirmation"]
        other = self.root / "collector-other.json"
        write_new(other, value)
        inp = prepare(self.root, other, "blinded", self.rubric)[0]
        self.assertNotIn("questions", read(inp)["collector"])

    def test_tampered_input_rejected(self) -> None:
        result = self.result()
        self.input.write_text(self.input.read_text() + " ")
        with self.assertRaisesRegex(ValueError, "SHA"):
            validate_result(self.input, result)

    def test_all_claims_and_fields_required(self) -> None:
        result = self.result()
        result["claim_verdicts"] = []
        with self.assertRaises(ValueError):
            validate_result(self.input, result)
        result = self.result()
        del result["field_search"]["payment"]
        with self.assertRaises(ValueError):
            validate_result(self.input, result)

    def test_positive_verdict_requires_primary_fragment(self) -> None:
        result = self.result()
        result["claim_verdicts"][0]["verdict"] = "confirmed_by_source"
        with self.assertRaises(ValueError):
            validate_result(self.input, result)

    def test_unsafe_source_url_rejected(self) -> None:
        result = self.result()
        result["claim_verdicts"][0].update(
            verdict="confirmed_by_source", evidence=[{**self.ev, "url": "javascript:alert(1)"}]
        )
        with self.assertRaises(ValueError):
            validate_result(self.input, result)

    def test_runtime_not_guessed(self) -> None:
        result = self.result()
        result["provenance"]["runtime_status"] = "recorded"
        with self.assertRaises(ValueError):
            validate_result(self.input, result)
        result["provenance"]["model"] = "recorded-model"
        result["provenance"]["effort"] = "medium"
        validate_result(self.input, result)

    def test_verifier_is_not_collector(self) -> None:
        result = self.result()
        result["provenance"]["agent_id"] = "collector"
        with self.assertRaisesRegex(ValueError, "автором"):
            validate_result(self.input, result)

    def test_budget_counts_failures(self) -> None:
        row = {
            "kind": "search",
            "query": "person",
            "status": "inaccessible",
            "checked_at": "2026-10-09",
            "elapsed_seconds": None,
            "cost_usd": 0,
        }
        with self.assertRaises(ValueError):
            journal_check([row] * 5)
        journal_check([row] * 4)

    def test_metrics_only_aggregates_with_explicit_denominators(self) -> None:
        result_path = self.root / "result.json"
        write_new(result_path, self.result())
        import_result(self.root, self.input, result_path, "run1")
        value = metrics(self.root, "v2", "run1", self.root / "safe.json")
        self.assertEqual(value["denominators"]["inputs"], 1)
        self.assertEqual(value["denominators"]["outputs"], 1)
        self.assertEqual(value["denominators"]["human_reviewed"], 0)
        self.assertIsNone(value["human_claim_error_rate"])
        self.assertEqual(value["claim_verdicts"], {"insufficient_evidence": 1})
        serialized = json.dumps(value)
        for personal in ("A1", "person@example.edu", "example.edu", "alert(1)"):
            self.assertNotIn(personal, serialized)

    def test_packet_is_safe_and_results_immutable(self) -> None:
        result_path = self.root / "result.json"
        write_new(result_path, self.result())
        saved = import_result(self.root, self.input, result_path, "run1")
        before = sha(saved)
        import_result(self.root, self.input, result_path, "run1")
        self.assertEqual(before, sha(saved))
        output = packet(self.root, self.input.parent, "run1", ["A1"], "first")
        body = output.read_text()
        self.assertNotIn("<script>", body)
        self.assertNotIn("<img src=x", body)
        self.assertIn("&lt;script&gt;", body)
        self.assertIn("&lt;img", body)
        self.assertIn("Просмотр человеком: нет", body)
        self.assertEqual(output, packet(self.root, self.input.parent, "run1", ["A1"], "first"))
        self.assertFalse(json.loads(saved.read_text())["human_reviewed"])


if __name__ == "__main__":
    unittest.main()
