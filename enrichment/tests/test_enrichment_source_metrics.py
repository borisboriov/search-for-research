"""Проверка разделения частной карты источников и безопасных агрегатов."""

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from sfr_enrichment_legacy.enrichment_experiment import sha, write_new
from sfr_enrichment_legacy.enrichment_source_metrics import source_metrics


class SourceMetricsTest(unittest.TestCase):
    def test_private_mapping_safe_export_and_input_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / "verification" / "v2"
            claim: dict[str, Any] = {
                "claim_id": "c1",
                "field": "personal_contact",
                "value": "private@example.org",
                "evidence": [
                    {
                        "url": "https://example.org/private-person",
                        "excerpt": "private@example.org",
                        "information_date": None,
                    }
                ],
            }
            input_path = directory / "inputs" / "A1.json"
            write_new(input_path, {"author_id": "A1", "collector": {"claims": [claim]}})
            output_path = directory / "outputs" / "run" / "A1.json"
            output: dict[str, Any] = {
                "input_sha256": sha(input_path),
                "result": {
                    "author_id": "A1",
                    "identity": {"verdict": "insufficient_evidence"},
                    "claim_verdicts": [
                        {**claim, "verdict": "confirmed_by_source"},
                    ],
                    "new_findings": [],
                },
            }
            write_new(output_path, output)
            with patch(
                "sfr_enrichment_legacy.enrichment_source_metrics.verified_sample",
                return_value=[{"id": "A1"}],
            ):
                private, safe = source_metrics(root, "v2", "run")
                self.assertEqual(private["sources"][0]["url"], claim["evidence"][0]["url"])
                self.assertEqual(safe["sources"][0]["profiles"], 1)
                self.assertEqual(
                    safe["confirmed_original_claims_with_unresolved_identity_by_field"],
                    {"personal_contact": 1},
                )
                self.assertEqual(safe["identity_linked_confirmed_original_profiles_by_field"], {})
                self.assertEqual(safe["sources"][0]["unknown_date_evidence"], 2)
                exported = json.dumps(safe)
                for secret in ("private@example.org", "private-person", "A1", "example.org"):
                    self.assertNotIn(secret, exported)
                self.assertEqual(source_metrics(root, "v2", "run"), (private, safe))
                output["result"]["identity"] = {"verdict": "confirmed_by_source"}
                output["result"]["claim_verdicts"][0]["evidence"] = [
                    {**claim["evidence"][0], "url": "https://example.org/independent"}
                ]
                output["result"]["new_findings"] = [
                    {"field": "topic", "evidence": claim["evidence"]}
                ]
                output_path.write_text(json.dumps(output))
                _, linked = source_metrics(root, "v2", "run")
                self.assertEqual(
                    linked["identity_linked_confirmed_original_profiles_by_field"],
                    {"personal_contact": 1},
                )
                self.assertEqual(
                    linked["identity_linked_new_finding_profiles_by_field"], {"topic": 1}
                )
                self.assertEqual(
                    linked["confirmed_original_claims_using_additional_source_by_field"],
                    {"personal_contact": 1},
                )
                input_path.write_text(json.dumps({"author_id": "A1", "collector": {"claims": []}}))
                with self.assertRaises(ValueError):
                    source_metrics(root, "v2", "run")


if __name__ == "__main__":
    unittest.main()
