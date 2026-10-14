"""Lossless delivered evidence and oversized profile isolation, no real transports."""

import asyncio
import importlib.util
import json
import socket
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
import test_enrichment_assisted as helpers

from sfr_enrichment.common import read
from sfr_enrichment.compact import compact_input, encode, expand_input
from sfr_enrichment.contacts import ContactInputTooLarge, verify_contact_input
from sfr_enrichment.runner import run


def meter_module() -> Any:
    path = Path(__file__).parents[1] / "research/isolation209_meter.py"
    spec = importlib.util.spec_from_file_location("isolation209_meter", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


class MeterTests(unittest.TestCase):
    def test_native_prepared_source_and_unattempted_are_distinct(self) -> None:
        from sfr_enrichment.evidence import immutable_json

        meter = meter_module()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(meter.unfinished_outcome(root, "A")["outcome"], "not_attempted")
            immutable_json(root / "sources/A/source-test.json", {})
            self.assertEqual(
                meter.unfinished_outcome(root, "A")["outcome"], "failed_source_partial"
            )
            immutable_json(root / "prepared/A.json", {})
            self.assertEqual(
                meter.unfinished_outcome(root, "A")["outcome"], "failed_prepared_unverified"
            )
            immutable_json(root / "runs/A/native_verifier/started.json", {})
            self.assertEqual(
                meter.unfinished_outcome(root, "A")["outcome"], "failed_native_unknown"
            )
            immutable_json(root / "runs/A/native_verifier/receipt.json", {})
            self.assertEqual(
                meter.unfinished_outcome(root, "A")["outcome"], "failed_native_unvalidated"
            )

    def test_DNS_failure_has_reservation_without_physical_HTTP(self) -> None:
        from sfr_enrichment.sources import PublicLoader

        fixture = helpers.AssistedTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        url = "https://public.example/a"
        loader = PublicLoader(fixture.root / "sources/A1", [url], fixture.root, "A1")

        async def request() -> None:
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(lambda _: self.fail("DNS failure must not GET"))
            ) as client:
                await loader.request(client, url, "test", 1000)

        with patch("sfr_enrichment.sources.socket.getaddrinfo", side_effect=socket.gaierror("DNS")):
            asyncio.run(request())
        counts = meter_module().source_http_counts(fixture.root)
        self.assertEqual(counts["source_reservations"], 1)
        self.assertEqual(counts["physical_HTTP"], 0)
        self.assertEqual(counts["pre_HTTP_failures"], 1)
        self.assertEqual(counts["unknown_HTTP_attempts"], 0)
        path = fixture.root / "HTTP-ledger/0000-finished.json"
        path.unlink()
        counts = meter_module().source_http_counts(fixture.root)
        self.assertEqual(counts["unknown_HTTP_attempts"], 1)
        self.assertEqual(counts["physical_HTTP"], 0)


class DateIsolationTests(unittest.TestCase):
    def test_invalid_identity_metadata_date_rejected_and_other_person_verified(self) -> None:
        from sfr_enrichment.evidence import immutable_json

        fixture = helpers.AssistedTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)

        def native(
            directory: Path, prompt: str, *args: object, **kwargs: Any
        ) -> tuple[Path, dict[str, Any]]:
            result_path, receipt = fixture.fake_native(directory, prompt, *args, **kwargs)
            if json.loads(prompt)["task"]["author_id"] == "A1":
                result = read(result_path)
                result["profile_assessments"]["identity"].update(
                    information_date="2023-04-03", date_basis="source_metadata"
                )
                result_path.unlink()  # disposable mocked fixture only
                immutable_json(result_path, result)
                from sfr_enrichment.common import sha

                receipt["raw_result_sha256"] = sha(result_path)
                (directory / "receipt.json").unlink()
                immutable_json(directory / "receipt.json", receipt)
            return result_path, receipt

        fixture.mocked_run(native=native)
        failure = read(fixture.root / "profile-failures/A1.json")
        self.assertEqual(failure["status"], "invalid_identity_metadata_date")
        self.assertTrue(failure["model_called"])
        self.assertTrue((fixture.root / "results/A1.json").exists())
        self.assertFalse((fixture.root / "date-checks/A1.json").exists())
        self.assertTrue((fixture.root / "date-checks/A2.json").exists())
        self.assertNotIn(
            "A1",
            [
                read(Path(row["input_path"]))["author_id"]
                for row in read(fixture.root / "entries.json")
            ],
        )
        with patch("sfr_enrichment.native.execute", side_effect=AssertionError("retry")):
            asyncio.run(run(fixture.root, 90))

    def test_other_metadata_axis_remains_common_invariant(self) -> None:
        from sfr_enrichment.fragments import UnsupportedIdentityMetadataDate, _orcid_employment_date

        with self.assertRaises(UnsupportedIdentityMetadataDate):
            _orcid_employment_date({}, {"information_date": "2023-04-03"}, "identity")
        with self.assertRaises(ValueError) as raised:
            _orcid_employment_date({}, {}, "activity")
        self.assertNotIsInstance(raised.exception, UnsupportedIdentityMetadataDate)

    def test_mixed_identity_and_common_date_error_is_fatal_in_any_order(self) -> None:
        from sfr_enrichment.fragments import UnsupportedIdentityMetadataDate, check_dates

        corpus = {"fragments": {"E": {"excerpt": "Publication 2023"}}}
        identity = {
            "information_date": "2023-04-03",
            "date_basis": "source_metadata",
            "evidence_refs": ["E"],
        }
        for basis, date in [("source_metadata", "2023"), ("content", "bad")]:
            activity = {"information_date": date, "date_basis": basis, "evidence_refs": ["E"]}
            for pairs in [
                [("identity", identity), ("activity", activity)],
                [("activity", activity), ("identity", identity)],
            ]:
                with self.subTest(basis=basis, order=pairs[0][0]):
                    with self.assertRaises(ValueError) as raised:
                        check_dates(corpus, {"items": [], "profile_assessments": dict(pairs)})
                    self.assertNotIsInstance(raised.exception, UnsupportedIdentityMetadataDate)
        malformed = dict(identity, information_date="bad")
        with self.assertRaises(ValueError) as raised:
            check_dates(corpus, {"items": [], "profile_assessments": {"identity": malformed}})
        self.assertNotIsInstance(raised.exception, UnsupportedIdentityMetadataDate)

    def test_cited_year_absent_is_local_but_mixed_metadata_errors_are_common(self) -> None:
        from sfr_enrichment.fragments import MissingCitedDateYear, check_dates

        corpus = {"fragments": {"E": {"excerpt": "Publication 2023"}}}
        item = {"information_date": "2018", "date_basis": "content", "evidence_refs": ["E"]}
        with self.assertRaises(MissingCitedDateYear):
            check_dates(corpus, {"items": [item], "profile_assessments": {}})
        activity = dict(item, date_basis="source_metadata")
        for pairs in [
            [("identity", item), ("activity", activity)],
            [("activity", activity), ("identity", item)],
        ]:
            with self.assertRaises(ValueError) as raised:
                check_dates(corpus, {"items": [], "profile_assessments": dict(pairs)})
            self.assertNotIsInstance(raised.exception, MissingCitedDateYear)
        for date in ["bad", "date2018", "0000", "2024-99", "2024-02-31"]:
            with self.assertRaises(ValueError) as raised:
                check_dates(
                    corpus,
                    {"items": [dict(item, information_date=date)], "profile_assessments": {}},
                )
            self.assertNotIsInstance(raised.exception, MissingCitedDateYear)

    def test_invalid_cited_year_has_no_card_and_next_person_continues(self) -> None:
        from sfr_enrichment.common import sha
        from sfr_enrichment.evidence import immutable_json

        fixture = helpers.AssistedTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)

        def native(
            directory: Path, prompt: str, *args: object, **kwargs: Any
        ) -> tuple[Path, dict[str, Any]]:
            path, receipt = fixture.fake_native(directory, prompt, *args, **kwargs)
            if json.loads(prompt)["task"]["author_id"] == "A1":
                result = read(path)
                result["items"][0].update(information_date="2018", date_basis="content")
                path.unlink()
                immutable_json(path, result)
                receipt["raw_result_sha256"] = sha(path)
                (directory / "receipt.json").unlink()
                immutable_json(directory / "receipt.json", receipt)
            return path, receipt

        fixture.mocked_run(native=native)
        self.assertEqual(
            read(fixture.root / "profile-failures/A1.json")["status"], "date_year_absent_unverified"
        )
        self.assertFalse((fixture.root / "date-checks/A1.json").exists())
        self.assertTrue((fixture.root / "date-checks/A2.json").exists())

    def test_malformed_present_year_is_common_in_both_mixed_orders(self) -> None:
        from sfr_enrichment.fragments import (
            MissingCitedDateYear,
            UnsupportedIdentityMetadataDate,
            check_dates,
        )

        corpus = {"fragments": {"E": {"excerpt": "Publication 2018"}}}
        local = {"information_date": "2020", "date_basis": "content", "evidence_refs": ["E"]}
        for date in ["2018-02-31", "2018-99", "date2018"]:
            malformed = dict(local, information_date=date)
            for pairs in [
                [("activity", malformed)],
                [("identity", local), ("activity", malformed)],
                [("activity", malformed), ("identity", local)],
            ]:
                with self.subTest(date=date, order=pairs[0][0]):
                    with self.assertRaises(ValueError) as raised:
                        check_dates(corpus, {"items": [], "profile_assessments": dict(pairs)})
                    self.assertNotIsInstance(
                        raised.exception, (MissingCitedDateYear, UnsupportedIdentityMetadataDate)
                    )
