"""Смысловые регрессии: текст не равен полю, актуальности и идентичности."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from enrichment_experiment import read, sha, write_new
from enrichment_semantics import (
    RULES_VERSION,
    classification,
    import_result,
    metrics,
    prepare,
    prepare_control,
    validate,
)


def assessment(item_id: str = "c1", **changes: Any) -> dict[str, Any]:
    return {
        "item_id": item_id,
        "text_verdict": "supported",
        "identity_verdict": "supported",
        "field_verdict": "correct",
        "corrected_field": None,
        "fact_kind": "literal",
        "object_type": "scientist",
        "object_relation": "supported",
        "student_level": ["masters"],
        "information_date": None,
        "date_basis": "unknown",
        "current_applicability": "undated",
        "evidence_refs": ["E0001"],
        "explanation": "Текст подтверждает только этот факт.",
        "question": "Согласны ли вы с принадлежностью факта?",
        **changes,
    }


def fixture(field: str = "topic") -> tuple[dict[str, Any], dict[str, Any]]:
    source: dict[str, Any] = {
        "author_id": "A1",
        "collector_agent_id": "collector",
        "old_verifier_agent_id": "old",
        "items": [{"item_id": "c1", "origin": "collector", "original_field": field}],
        "evidence_pool": {"E0001": {"excerpt": "Точная цитата"}},
    }
    result: dict[str, Any] = {
        "author_id": "A1",
        "input_sha256": "digest",
        "rules_version": RULES_VERSION,
        "provenance": {
            "agent_id": "new",
            "runtime_status": "runtime_not_exposed",
            "model": None,
            "effort": None,
            "tokens": None,
            "cost_usd": None,
        },
        "items": [assessment()],
        "profile_assessments": {
            name: {
                "verdict": "insufficient",
                "evidence_refs": [],
                "explanation": "Не установлено",
                "information_date": None,
                "date_basis": "unknown",
                **({"status": "unknown"} if name == "activity" else {}),
            }
            for name in ("identity", "current_affiliation", "activity")
        },
        "summary": {
            name: "Не установлено"
            for name in ("known", "unknown", "identity", "current_opportunity")
        },
    }
    return source, result


class SemanticsTest(unittest.TestCase):
    def test_duration_and_nationality_cannot_be_confirmed_as_other_fields(self) -> None:
        for field, kind, corrected in (
            ("workload", "appointment_duration", "appointment_duration"),
            ("external_students", "nationality", "nationality"),
        ):
            with self.subTest(field=field):
                source, result = fixture(field)
                result["items"][0]["fact_kind"] = kind
                with self.assertRaises(ValueError):
                    validate(source, result, "digest")
                result["items"][0].update(field_verdict="misclassified", corrected_field=corrected)
                derived = validate(source, result, "digest")["c1"]
                self.assertFalse(derived["usable_coverage"])
                self.assertEqual(derived["corrected_field"], corrected)
        source, result = fixture("workload")
        result["items"][0]["fact_kind"] = "effort"
        self.assertTrue(validate(source, result, "digest")["c1"]["usable_coverage"])

    def test_department_negative_history_undated_and_postdoc_not_current_personal_intake(
        self,
    ) -> None:
        source, result = fixture("direct_willingness")
        row = result["items"][0]
        row.update(
            fact_kind="willingness",
            object_type="organization",
            current_applicability="explicit_negative",
            field_verdict="insufficient",
        )
        derived = validate(source, result, "digest")["c1"]
        self.assertIn("personal_willingness_requires_scientist", derived["reason"])
        self.assertIn("negative_not_positive_coverage", derived["reason"])
        source, result = fixture("published_recruitment")
        row = result["items"][0]
        row.update(fact_kind="intake", object_type="offer")
        for state in ("historical", "expired", "undated", "unknown"):
            row["current_applicability"] = state
            self.assertFalse(validate(source, result, "digest")["c1"]["usable_coverage"])
        row.update(
            current_applicability="current",
            information_date="2026-10-01",
            date_basis="content",
            student_level=["postdoc"],
        )
        self.assertFalse(validate(source, result, "digest")["c1"]["usable_coverage"])
        row["student_level"] = ["phd"]
        self.assertTrue(validate(source, result, "digest")["c1"]["usable_coverage"])
        source, result = fixture("supervision_history")
        result["items"][0].update(
            fact_kind="supervision_history", current_applicability="historical"
        )
        self.assertTrue(validate(source, result, "digest")["c1"]["usable_coverage"])

    def test_unknown_identity_candidate_and_conflicting_death_date_are_not_truth(self) -> None:
        source, result = fixture()
        result["items"][0]["identity_verdict"] = "insufficient"
        self.assertFalse(validate(source, result, "digest")["c1"]["usable_coverage"])
        result["items"][0]["identity_verdict"] = "supported"
        source["items"][0]["origin"] = "verifier_candidate"
        self.assertTrue(validate(source, result, "digest")["c1"]["candidate_only"])
        self.assertFalse(classification(source["items"][0], result["items"][0])["usable_coverage"])
        activity = result["profile_assessments"]["activity"]
        activity.update(
            verdict="supported",
            status="deceased",
            evidence_refs=["E0001"],
            date_basis="conflicting",
            information_date=None,
        )
        validate(source, result, "digest")
        activity["information_date"] = "2025"
        with self.assertRaises(ValueError):
            validate(source, result, "digest")
        activity["information_date"] = None
        result["items"][0]["evidence_refs"] = ["invented"]
        with self.assertRaises(ValueError):
            validate(source, result, "digest")

    def test_control_inputs_keep_collection_lineage_without_fake_old_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_new(root / "sample.json", [{"id": "A1"}])
            write_new(root / "manifest.json", {"sample_sha256": sha(root / "sample.json")})
            collector_path = root / "real-collector.json"
            collector: dict[str, Any] = {
                "author_id": "A1",
                "provenance": {"agent_id": "collector"},
                "items": [
                    {
                        "item_id": "c1",
                        "field": "appointment_duration",
                        "value": "one year",
                        "evidence_refs": ["E0001"],
                    }
                ],
            }
            write_new(collector_path, collector)
            rubric = root / "rubric.md"
            rubric.write_text("rules")
            pool = {"E0001": {"excerpt": "one year"}}
            path = prepare_control(
                root, {"id": "A1"}, collector_path, pool, rubric, sha(root / "sample.json")
            )
            source = read(path)
            self.assertIsNone(source["old_output_sha256"])
            self.assertEqual(
                prepare_control(
                    root, {"id": "A1"}, collector_path, pool, rubric, sha(root / "sample.json")
                ),
                path,
            )
            _, result = fixture()
            result["input_sha256"] = sha(path)
            result["items"][0]["fact_kind"] = "appointment_duration"
            raw = root / "verifier.json"
            write_new(raw, result)
            imported = import_result(root, path, raw, "control")
            self.assertFalse(read(imported)["classifications"]["c1"]["usable_coverage"])
            safe = metrics(root, "control", root / "metrics.json")
            self.assertEqual(safe["denominators"]["profiles_with_v2_baseline"], 0)
            self.assertEqual(safe["denominators"]["profiles"], 1)
            collector["items"][0]["field"] = "topic"
            collector_path.write_text(json.dumps(collector))
            with self.assertRaises(ValueError):
                prepare_control(
                    root, {"id": "A1"}, collector_path, pool, rubric, sha(root / "sample.json")
                )

    def test_blinded_inputs_immutable_resume_metrics_and_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_new(root / "sample.json", [{"id": "A1"}])
            write_new(root / "manifest.json", {"sample_sha256": sha(root / "sample.json")})
            evidence = {
                "url": "https://example.org/person",
                "excerpt": "one-year appointment",
                "checked_at": "2026-10-09",
                "information_date": None,
                "object_type": "offer",
                "explanation": "AUTHOR_EXPECTED_SUPPORTED",
            }
            original = {
                "author_id": "A1",
                "profile": {"id": "A1"},
                "sample_sha256": sha(root / "sample.json"),
                "collector": {
                    "provenance": {"agent_id": "collector"},
                    "claims": [
                        {
                            "claim_id": "c1",
                            "field": "workload",
                            "value": "one-year",
                            "evidence": [evidence],
                        }
                    ],
                },
            }
            old = {
                "input_sha256": "",
                "result": {
                    "provenance": {"agent_id": "old"},
                    "claim_verdicts": [
                        {"claim_id": "c1", "verdict": "confirmed_by_source", "evidence": [evidence]}
                    ],
                    "new_findings": [
                        {"field": "workload", "value": "one-year", "evidence": [evidence]}
                    ],
                    "identity": {"evidence": []},
                    "current_affiliation": {"evidence": []},
                },
            }
            inp, out, rubric = root / "old-input.json", root / "old-output.json", root / "rubric.md"
            write_new(inp, original)
            old["input_sha256"] = sha(inp)
            write_new(out, old)
            rubric.write_text("rules")
            path = prepare(root, inp, out, rubric)
            source = read(path)
            self.assertNotIn("AUTHOR_EXPECTED_SUPPORTED", path.read_text())
            self.assertNotIn("confirmed_by_source", path.read_text())
            self.assertEqual(prepare(root, inp, out, rubric), path)
            _, result = fixture("workload")
            result["input_sha256"] = sha(path)
            result["items"] = [
                assessment(
                    item["item_id"],
                    fact_kind="appointment_duration",
                    field_verdict="misclassified",
                    corrected_field="appointment_duration",
                )
                for item in source["items"]
            ]
            raw = root / "new-result.json"
            write_new(raw, result)
            imported = import_result(root, path, raw, "run")
            self.assertEqual(import_result(root, path, raw, "run"), imported)
            summary = metrics(root, "run", root / "safe.json")
            self.assertEqual(summary["denominators"]["collector_claims"], 1)
            self.assertEqual(summary["denominators"]["verifier_candidates"], 1)
            self.assertEqual(
                summary["coverage_comparison"]["workload"],
                {"v2_source_confirmed_profiles": 1, "v3_usable_profiles": 0},
            )
            self.assertEqual(summary["misclassifications_by_original_field"], {"workload": 1})
            self.assertNotIn("example.org", json.dumps(summary))
            self.assertNotIn("A1", json.dumps(summary))
            changed = copy.deepcopy(result)
            changed["provenance"]["agent_id"] = "old"
            with self.assertRaises(ValueError):
                validate(source, changed, sha(path))
            snapshot = root / "semantic-source-snapshots" / f"{source['old_output_sha256']}.json"
            snapshot.write_text("{}")
            with self.assertRaises(ValueError):
                import_result(root, path, raw, "run")


if __name__ == "__main__":
    unittest.main()
