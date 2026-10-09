"""Защита полного источника, слепых пакетов и quota gate без inference."""

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from enrichment_batch import encoded, immutable
from enrichment_experiment import now, read
from enrichment_gpt_compact import CASES, allow_new, packets, task_for


class CompactTests(unittest.TestCase):
    def test_same_semantic_bytes_are_used_without_removing_quotes_or_identifiers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = {
                "profile": {"orcid": "fixed", "profile_text": "full subject anchor"},
                "evidence_pool": {"e": {"excerpt": "Exact цитата\nwith spaces  "}},
            }
            immutable(root / "inputs/a.json", encoded(source))
            one, two = task_for(root, "a"), task_for(root, "a")
            self.assertEqual(one, two)
            self.assertEqual(one["semantic_input"], source)
            self.assertEqual(one["input_sha256"], one["batch_input_sha256"])

    def test_blind_packet_keeps_substantive_answers_and_hides_runtime_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for aid in CASES:
                immutable(
                    root / "inputs" / f"{aid}.json",
                    encoded(
                        {
                            "author_id": aid,
                            "profile": {"id": aid},
                            "items": [],
                            "evidence_pool": {},
                            "profile_evidence": {"identity": [], "current_affiliation": []},
                        }
                    ),
                )
            result = {
                "items": [],
                "profile_assessments": {"identity": "literal assessment"},
                "summary": {"unknown": "unknown"},
                "provenance": {"model": "secret-runtime"},
            }
            with (
                patch("enrichment_gpt_compact.locked"),
                patch("enrichment_gpt_compact.response", return_value={"result": result}),
            ):
                paths = packets(root)
                again = packets(root)
            self.assertEqual(paths, again)
            for path in paths:
                self.assertNotIn("secret-runtime", path.read_text())
                packet = read(path)
                for profile in packet["profiles"]:
                    self.assertEqual(set(profile["responses"]), {"A", "B"})
                    self.assertEqual(
                        profile["responses"]["A"]["profile_assessments"],
                        result["profile_assessments"],
                    )
                self.assertTrue((root / "unblinding" / path.name).exists())

    def test_quota_requires_official_fresh_snapshot_and_stops_at_reserved_margin(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("enrichment_gpt_compact.NO_NEW_AFTER", datetime(2099, 1, 1, tzinfo=UTC)),
        ):
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "snapshot"):
                allow_new(root)
            immutable(
                root / "quota-01.json",
                encoded({"checked_at": now(), "codex": {"remaining_percent": 15}}),
            )
            with self.assertRaisesRegex(ValueError, "15%"):
                allow_new(root)


if __name__ == "__main__":
    unittest.main()
