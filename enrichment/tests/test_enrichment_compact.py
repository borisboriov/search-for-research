"""Lossless delivered evidence and oversized profile isolation, no real transports."""

import asyncio
import json
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

import test_enrichment_assisted as helpers

from sfr_enrichment.common import read
from sfr_enrichment.compact import compact_input, encode, expand_input
from sfr_enrichment.contacts import ContactInputTooLarge, verify_contact_input
from sfr_enrichment.runner import run


def source() -> dict[str, Any]:
    text = "Identity dated 2026: scientist contact@example.org, context."
    base = {
        "source_record_path": "/saved/source.json",
        "source_record_sha256": "a" * 64,
        "representation": "static_text",
        "url": "https://public.example/a",
    }
    return {
        "items": [{"evidence_refs": ["E1"]}],
        "profile_evidence": {"identity": ["F1"]},
        "evidence_pool": {
            "E1": {**base, "start": 0, "end": 30, "excerpt": text[:30]},
            "F1": {**base, "start": 20, "end": len(text), "excerpt": text[20:]},
        },
    }


class CompactTests(unittest.TestCase):
    def test_union_is_lossless_and_delivers_overlap_once(self) -> None:
        original = source()
        compact = compact_input(original)
        self.assertEqual(expand_input(compact), original)
        self.assertEqual(len(compact["evidence_blocks"]), 1)
        block = next(iter(compact["evidence_blocks"].values()))
        self.assertEqual(
            block["excerpt"], "Identity dated 2026: scientist contact@example.org, context."
        )
        self.assertNotIn("excerpt", compact["evidence_pool"]["E1"])
        self.assertEqual(encode(compact_input(original)), encode(compact))

    def test_gaps_representations_and_registry_versions_remain_distinct(self) -> None:
        for change in ["gap", "representation", "source_record_sha256", "source_record_path"]:
            original = source()
            row = original["evidence_pool"]["F1"]
            if change == "gap":
                row["start"] = 31
                row["excerpt"] = row["excerpt"][11:]
            else:
                row[change] += "-other"
            compact = compact_input(original)
            self.assertEqual(len(compact["evidence_blocks"]), 2)
            self.assertEqual(expand_input(compact), original)

    def test_unicode_ranges_and_individual_metadata_preserved(self) -> None:
        original = source()
        for row in original["evidence_pool"].values():
            row["excerpt"] = "я" * (row["end"] - row["start"])
        original["evidence_pool"]["E1"]["information_date"] = None
        compact = compact_input(original)
        self.assertEqual(expand_input(compact), original)
        self.assertIn("information_date", expand_input(compact)["evidence_pool"]["E1"])
        self.assertNotIn("information_date", expand_input(compact)["evidence_pool"]["F1"])

    def test_conflicting_overlap_unknown_refs_and_block_rejected(self) -> None:
        original = source()
        original["evidence_pool"]["F1"]["excerpt"] = "X" * len(
            original["evidence_pool"]["F1"]["excerpt"]
        )
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            compact_input(original)
        original = source()
        original["items"][0]["evidence_refs"] = ["unknown"]
        with self.assertRaisesRegex(ValueError, "Unknown evidence"):
            compact_input(original)
        compact = compact_input(source())
        compact["evidence_pool"]["E1"]["block_id"] = "unknown"
        with self.assertRaisesRegex(ValueError, "Unknown block"):
            expand_input(compact)

    def test_oversized_first_has_explicit_failure_and_second_verified(self) -> None:
        fixture = helpers.AssistedTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        original = verify_contact_input

        def verify(root: Path, input_path: Path, **kwargs: Any) -> Path:
            if read(input_path)["author_id"] == "A1":
                raise ContactInputTooLarge(1_000_001, 1_000_000)
            return original(root, input_path, **kwargs)

        with patch("sfr_enrichment.runner.verify_contact_input", side_effect=verify):
            fixture.mocked_run()
        failure = read(fixture.root / "profile-failures/A1.json")
        self.assertEqual(failure["status"], "input_too_large")
        self.assertFalse(failure["model_called"])
        self.assertFalse((fixture.root / "runs/A1/native_verifier/started.json").exists())
        self.assertTrue((fixture.root / "results/A2.json").exists())
        with (
            patch("httpx.AsyncClient.get", side_effect=AssertionError("retry")),
            patch("sfr_enrichment.native.execute", side_effect=AssertionError("retry")),
        ):
            asyncio.run(run(fixture.root, 90))

    def test_actual_prompt_contains_blocks_and_matches_canonical(self) -> None:
        fixture = helpers.AssistedTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        delivered = []

        def native(
            directory: Path, prompt: str, *args: object, **kwargs: object
        ) -> tuple[Path, dict[str, Any]]:
            delivered.append(json.loads(prompt)["task"]["semantic_input"])
            return fixture.fake_native(directory, prompt, *args, **kwargs)

        fixture.mocked_run(native=native)
        for compact in delivered:
            aid = compact["author_id"]
            canonical = read(Path(read(fixture.root / f"prepared/{aid}.json")["input_path"]))
            self.assertEqual(expand_input(compact), canonical)
            self.assertEqual(
                read(fixture.root / f"model-inputs/{aid}.json")["compact_input"], compact
            )
