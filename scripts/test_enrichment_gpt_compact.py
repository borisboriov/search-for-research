"""Защита полного источника, слепых пакетов и quota gate без inference."""

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from enrichment_batch import encoded, immutable
from enrichment_experiment import now, read, sha
from enrichment_gpt_compact import CASES, allow_new, judge_response, packets, response, task_for


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
                unblinding = root / "unblinding" / paths[0].name
                mapping = read(unblinding)
                aid = CASES[0]
                mapping[aid]["A"], mapping[aid]["B"] = mapping[aid]["B"], mapping[aid]["A"]
                unblinding.write_bytes(encoded(mapping))
                with self.assertRaisesRegex(ValueError, "Packet/unblinding изменён"):
                    packets(root)
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

    def test_modified_validated_verdict_and_receipt_are_rejected_without_raw_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = root / "runs" / "a" / "baseline"
            raw = {"items": [{"verdict": "unsupported"}], "provenance": {}}
            for name, data in (
                ("raw-result.json", encoded(raw)),
                ("events.jsonl", b"events"),
                ("prompt.txt", b"prompt"),
            ):
                immutable(run / name, data)
            receipt = {
                key: sha(run / name)
                for name, key in (
                    ("raw-result.json", "raw_result_sha256"),
                    ("events.jsonl", "events_sha256"),
                    ("prompt.txt", "prompt_sha256"),
                )
            }
            immutable(run / "receipt.json", encoded(receipt))
            altered = {"items": [{"verdict": "supported"}], "provenance": {}}
            immutable(
                run / "validated.json",
                encoded({"result": altered, "receipt": receipt, "human_reviewed": 0}),
            )
            with (
                patch("enrichment_gpt_compact.normalized_provenance", return_value={}),
                self.assertRaisesRegex(ValueError, "отличается от raw"),
            ):
                response(root, "a", "baseline")
            saved = read(run / "validated.json")
            saved["receipt"]["tokens"] = {"input_tokens": 0}
            (run / "validated.json").write_bytes(encoded(saved))
            with self.assertRaisesRegex(ValueError, "receipt изменён"):
                response(root, "a", "baseline")

    def test_modified_judge_grade_is_rejected_without_raw_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "judge-inputs" / "packet-01.json"
            run = root / "judges" / path.stem
            raw = {"atom_evaluations": [{"grade": "incorrect", "severity": "high"}]}
            for name, data in (
                ("raw-result.json", encoded(raw)),
                ("events.jsonl", b"events"),
                ("prompt.txt", b"prompt"),
            ):
                immutable(run / name, data)
            receipt = {
                key: sha(run / name)
                for name, key in (
                    ("raw-result.json", "raw_result_sha256"),
                    ("events.jsonl", "events_sha256"),
                    ("prompt.txt", "prompt_sha256"),
                )
            }
            immutable(run / "receipt.json", encoded(receipt))
            immutable(
                run / "validated.json",
                encoded(
                    {
                        "result": {"atom_evaluations": [{"grade": "correct", "severity": "none"}]},
                        "receipt": receipt,
                        "human_reviewed": 0,
                    }
                ),
            )
            with self.assertRaisesRegex(ValueError, "Judge result отличается"):
                judge_response(root, path)

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
