"""Literal restoration, strict IDs and terminal bounded-stage failures."""

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from enrichment_fragments import CASES, catalog, hydrate, run


def fixture() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    text = "Другой автор\r\ncontact@example.org\r\nДата содержания: 2007."
    record = {
        "url": "https://example.org/source",
        "body_sha256": "body",
        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "text": text,
        "source_kind": "direct_http",
        "checked_at": "2026-10-11",
    }
    corpus = {"author_id": "A1", "profile": {"id": "A1"}} | catalog("A1", [record])
    value_id = next(k for k, v in corpus["values"].items() if v["kind"] == "email")
    ref = corpus["values"][value_id]["fragment_id"]
    task = {
        "author_id": "A1",
        "input_sha256": "sha",
        "batch_input_sha256": "sha",
        "batch_ticket_id": "ticket",
        "corpus": corpus,
    }
    axis: dict[str, Any] = {
        "verdict": "insufficient",
        "evidence_refs": [],
        "information_date": None,
        "date_basis": "unknown",
        "explanation": "Личность не установлена.",
    }
    raw = {
        k: task[k] for k in ("author_id", "input_sha256", "batch_input_sha256", "batch_ticket_id")
    } | {
        "rules_version": "semantic-v3",
        "selections": [{"value_id": value_id, "field": "personal_contact", "evidence_refs": [ref]}],
        "items": [
            {
                "item_id": value_id,
                "text_verdict": "supported",
                "identity_verdict": "insufficient",
                "field_verdict": "correct",
                "corrected_field": None,
                "fact_kind": "literal",
                "object_type": "scientist",
                "object_relation": "insufficient",
                "student_level": ["unknown"],
                "information_date": "2007",
                "date_basis": "content",
                "current_applicability": "historical",
                "evidence_refs": [ref],
                "explanation": "Адрес буквальный, принадлежность не установлена.",
                "question": "Чей адрес?",
            }
        ],
        "profile_assessments": {
            "identity": copy.deepcopy(axis),
            "current_affiliation": copy.deepcopy(axis),
            "activity": axis | {"status": "unknown"},
        },
        "summary": {
            k: "Не установлено." for k in ("known", "unknown", "identity", "current_opportunity")
        },
    }
    provenance = {
        "agent_id": "test-runtime",
        "runtime_status": "runtime_not_exposed",
        "model": None,
        "effort": None,
        "tokens": None,
        "cost_usd": None,
    }
    return task, raw, provenance


class FragmentTests(unittest.TestCase):
    def test_literal_crlf_email_and_historical_date_are_restored_without_identity_inference(
        self,
    ) -> None:
        task, raw, provenance = fixture()
        result = hydrate(task, raw, provenance)
        item = result["input"]["items"][0]
        self.assertEqual(item["value"], "contact@example.org")
        self.assertIn("\r\n", next(iter(result["input"]["evidence_pool"].values()))["excerpt"])
        self.assertEqual(result["result"]["items"][0]["information_date"], "2007")
        self.assertFalse(result["derived"][item["item_id"]]["usable_coverage"])

    def test_foreign_unknown_or_duplicate_ids_and_wrong_sha_rejected(self) -> None:
        for mutation in (
            "foreign_value",
            "foreign_fragment",
            "missing_anchor",
            "duplicate",
            "wrong_sha",
            "missing_assessment",
        ):
            with self.subTest(mutation=mutation):
                task, raw, provenance = fixture()
                if mutation == "foreign_value":
                    raw["selections"][0]["value_id"] = "A2-foreign"
                elif mutation == "foreign_fragment":
                    raw["items"][0]["evidence_refs"] = ["foreign"]
                elif mutation == "missing_anchor":
                    raw["selections"][0]["evidence_refs"] = []
                elif mutation == "duplicate":
                    raw["selections"] *= 2
                elif mutation == "wrong_sha":
                    raw["input_sha256"] = "other"
                else:
                    raw["items"] = []
                with self.assertRaises((ValueError, KeyError)):
                    hydrate(task, raw, provenance)

    def test_email_tamper_out_of_bounds_text_as_contact_and_invented_date_rejected(self) -> None:
        for mutation in ("literal", "offset", "text_contact", "date", "invented_year"):
            with self.subTest(mutation=mutation):
                task, raw, provenance = fixture()
                key = raw["selections"][0]["value_id"]
                if mutation == "literal":
                    task["corpus"]["values"][key]["literal"] = "invented@example.org"
                elif mutation == "offset":
                    task["corpus"]["values"][key]["end"] = 10000
                elif mutation == "date":
                    raw["items"][0]["date_basis"] = "url_only"
                elif mutation == "invented_year":
                    raw["items"][0]["information_date"] = "2039"
                else:
                    key = next(
                        k for k, v in task["corpus"]["values"].items() if v["kind"] == "text"
                    )
                    raw["selections"][0]["value_id"] = raw["items"][0]["item_id"] = key
                with self.assertRaises(ValueError):
                    hydrate(task, raw, provenance)

    def test_all_text_covered_and_boundary_email_matches_literal(self) -> None:
        text = "ю" * 1490 + "test@example.org" + "\r\n" + "x" * 3000
        record = {
            "url": "https://example.org/a",
            "body_sha256": "b",
            "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "text": text,
            "source_kind": "direct_http",
            "checked_at": "now",
        }
        result = catalog("A1", [record])
        seen: set[int] = set()
        for f in result["fragments"].values():
            self.assertEqual(f["excerpt"], text[f["start"] : f["end"]])
            seen.update(range(f["start"], f["end"]))
        self.assertEqual(seen, set(range(len(text))))
        emails = [v for v in result["values"].values() if v["kind"] == "email"]
        self.assertEqual(len(emails), 1)
        self.assertEqual(emails[0]["literal"], "test@example.org")
        self.assertEqual(result, catalog("A1", [record]))
        self.assertNotEqual(set(result["values"]), set(catalog("A2", [record])["values"]))

    def test_runtime_failure_stops_stage_without_next_model_or_hidden_retry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            aid = CASES[0]["author_id"]
            task, _, _ = fixture()
            task["author_id"] = aid
            (root / "tasks").mkdir()
            (root / "corpora").mkdir()
            corpus = root / "corpora" / f"{aid}.json"
            corpus.write_text(json.dumps(task["corpus"]))
            task["input_sha256"] = hashlib.sha256(corpus.read_bytes()).hexdigest()
            path = root / "tasks" / f"{aid}.json"
            path.write_text(json.dumps(task))
            (root / "instruction.txt").write_text("instruction")
            from enrichment_fragments import output_schema

            prompt = json.dumps(
                {"task": task, "output_json_schema": output_schema(task["corpus"])},
                ensure_ascii=False,
                separators=(",", ":"),
            )
            manifest = {
                "cases": CASES,
                "stage_cap": 6,
                "deadline": "2099-01-01T00:00:00+00:00",
                "corpora": {
                    aid: {
                        "task_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                    }
                },
            }
            with (
                patch("enrichment_fragments.frozen", return_value=manifest),
                patch("enrichment_fragments.access_stopped", return_value=False),
                patch(
                    "enrichment_fragments.run_pi", side_effect=ValueError("technical failure")
                ) as glm,
                patch("enrichment_fragments.execute") as sol,
            ):
                result = run(root, 0)
            self.assertEqual(glm.call_count, 1)
            sol.assert_not_called()
            self.assertEqual(result["stage_jobs_reserved"], 1)
            self.assertEqual(result["cumulative_reserved"], 29)
            self.assertEqual(result["partial_reason"], "technical failure")
            self.assertTrue((root / "stopped.json").exists())

    def test_pi_bad_control_json_kills_process_and_preserves_failed_attempt(self) -> None:
        from enrichment_pi_pilot import HIGH_CONFIGS, run_pi

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            process = MagicMock()
            process.stdout = iter(["invalid-json\n"])
            process.poll.return_value = None
            process.wait.return_value = -9
            with (
                patch("enrichment_pi_pilot.access_stopped", return_value=False),
                patch("enrichment_pi_pilot.subprocess.Popen", return_value=process),
                patch("enrichment_pi_pilot.threading.Timer"),
                self.assertRaises(ValueError),
            ):
                run_pi(
                    root,
                    None,
                    "A1",
                    "pi_verifier",
                    {},
                    "shared",
                    {},
                    config_override=HIGH_CONFIGS["pi_verifier"],
                    method_override="fragment-offline3-v1",
                )
            process.kill.assert_called_once()
            failed = json.loads((root / "runs/A1/pi_verifier/finished.json").read_text())
            self.assertEqual(failed["exit_code"], -9)
            self.assertFalse(failed["done"])


if __name__ == "__main__":
    unittest.main()
