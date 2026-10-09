"""Фиксация метода требует полного пилота и запрещает тихую перенастройку."""

import tempfile
import unittest
from pathlib import Path

from enrichment_experiment import FIELDS, sha, write_new
from enrichment_protocol import RULE_FILES, freeze_method, validate_lock
from enrichment_verification import prepare


class ProtocolTests(unittest.TestCase):
    def test_lock_requires_full_pilot_and_detects_method_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "data"
            checkout = Path(directory) / "checkout"
            root.mkdir()
            sample = [
                {"id": f"A{i}", "cohort": "pilot" if i < 10 else "evaluation"} for i in range(100)
            ]
            write_new(root / "sample.json", sample)
            write_new(root / "manifest.json", {"sample_sha256": sha(root / "sample.json")})
            for name in RULE_FILES:
                file = checkout / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text("rules")
            with self.assertRaises(FileNotFoundError):
                freeze_method(root, "v2", "native", checkout)
            for row in sample[:10]:
                collector = root / f"collector-{row['id']}.json"
                write_new(
                    collector,
                    {
                        "author_id": row["id"],
                        "claims": [],
                        "field_status": dict.fromkeys(FIELDS, "not_found"),
                        "journal": [],
                        "sources": [],
                        "provenance": {"agent_id": "collector"},
                    },
                )
                input_path = prepare(root, collector, "v2", checkout / RULE_FILES[-1])[0]
                verdict = {
                    "verdict": "insufficient_evidence",
                    "explanation": "bounded",
                    "evidence": [],
                }
                result = {
                    "author_id": row["id"],
                    "input_sha256": sha(input_path),
                    "rules_version": "v2",
                    "provenance": {
                        "agent_id": "verifier",
                        "model": None,
                        "effort": None,
                        "runtime_status": "runtime_not_exposed",
                    },
                    "identity": verdict,
                    "current_affiliation": verdict,
                    "claim_verdicts": [],
                    "new_findings": [],
                    "journal": [],
                    "questions": [],
                    "field_search": {
                        f: {"status": "not_found", "explanation": "bounded"} for f in FIELDS
                    },
                }
                write_new(
                    root / "verification/v2/outputs/native" / f"{row['id']}.json",
                    {"input_sha256": sha(input_path), "result": result},
                )
            path = freeze_method(root, "v2", "native", checkout)
            lock = validate_lock(root, path, checkout)
            self.assertEqual(len(lock["human_sampling"]["random_ids"]), 5)
            self.assertTrue(lock["human_review_pending"])
            with self.assertRaises(FileExistsError):
                freeze_method(root, "v2", "native", checkout)
            (checkout / RULE_FILES[0]).write_text("new method")
            with self.assertRaises(ValueError):
                validate_lock(root, path, checkout)

    def test_path_identifiers_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            freeze_method(Path(directory), "../git", "native", Path(directory))


if __name__ == "__main__":
    unittest.main()
