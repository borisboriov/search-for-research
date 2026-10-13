"""Проверки неизменной выборки, изоляции, бюджета и остановки ORCID."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx

from sfr_enrichment_legacy.enrichment_experiment import (
    ORCID_API,
    latest_results,
    private_root,
    public_candidates,
    run_orcid,
    select_sample,
    sha,
    verified_sample,
    write_new,
)


class EnrichmentTests(unittest.TestCase):
    def docs(self) -> list[dict[str, Any]]:
        return [
            {"id": f"A{i:02d}{j:02d}", "institution": f"I{i:02d}", "h_index": 20 - j}
            for i in range(12)
            for j in range(10)
        ]

    def setup_root(self, root: Path) -> Path:
        sample, _ = select_sample(self.docs())
        for i, row in enumerate(sample):
            row.update(cohort="pilot" if i < 10 else "evaluation", orcid=f"0000-0000-0000-{i:04d}")
        write_new(root / "sample.json", sample)
        write_new(root / "manifest.json", {"sample_sha256": sha(root / "sample.json")})
        rules = root / "rules.json"
        write_new(
            rules,
            {
                "source": ORCID_API,
                "access": "allowed",
                "checked_at": "2026-10-08",
                "terms_url": "https://info.orcid.org/terms",
            },
        )
        return rules

    def test_selection_strata_ties_and_input_order(self) -> None:
        sample, groups = select_sample(self.docs())
        self.assertEqual(len(sample), 100)
        self.assertEqual(len({row["id"] for row in sample}), 100)
        self.assertEqual(len(groups), 12)
        self.assertEqual([row["id"] for row in sample[96:]], ["A0008", "A0108", "A0208", "A0308"])
        self.assertEqual(select_sample(list(reversed(self.docs()))), (sample, groups))

    def test_duplicate_ids_and_unknown_h_index_rejected(self) -> None:
        docs = self.docs()
        with self.assertRaises(ValueError):
            select_sample([*docs, docs[0]])
        docs[0]["h_index"] = None
        with self.assertRaises(ValueError):
            select_sample(docs)

    def test_raw_cannot_be_written_into_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".git").write_text("gitdir: elsewhere")
            with self.assertRaises(ValueError):
                private_root(root / "raw")

    def test_snapshot_tampering_and_overwrite_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.setup_root(root)
            with self.assertRaises(FileExistsError):
                write_new(root / "sample.json", [])
            (root / "sample.json").write_text("[]")
            with self.assertRaises(ValueError):
                verified_sample(root)

    def test_public_email_visibility_no_identity_inference(self) -> None:
        candidates = public_candidates(
            {
                "person": {
                    "emails": {
                        "email": [
                            {"email": "visible@example.org", "visibility": "public"},
                            {"email": "private@example.org", "visibility": "limited"},
                        ]
                    }
                }
            }
        )
        self.assertEqual(len(candidates["emails"]), 1)
        self.assertEqual(candidates["identity_verdict"], "not_checked")

    def test_429_stops_source_and_survives_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rules = self.setup_root(root)
            calls = []

            def response(request: httpx.Request) -> httpx.Response:
                calls.append(request)
                return httpx.Response(429)

            client = httpx.Client(transport=httpx.MockTransport(response))
            with (
                patch(
                    "sfr_enrichment_legacy.enrichment_experiment.httpx.Client", return_value=client
                ),
                patch("sfr_enrichment_legacy.enrichment_experiment.time.sleep"),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                run_orcid(root, "pilot", "research@example.org", rules)
            self.assertEqual(len(calls), 1)
            self.assertTrue((root / "orcid-stop.json").exists())
            self.assertEqual(len(latest_results(root)), 10)
            with (
                patch("sfr_enrichment_legacy.enrichment_experiment.httpx.Client") as factory,
                contextlib.redirect_stdout(io.StringIO()),
            ):
                run_orcid(root, "pilot", "research@example.org", rules, retry_transport=True)
            self.assertEqual(len(calls), 1)
            # Context can be entered, but no additional network request is sent.
            factory.return_value.__enter__.return_value.get.assert_not_called()

    def test_evaluation_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rules = self.setup_root(root)
            with (
                self.assertRaises(ValueError),
                patch("sfr_enrichment_legacy.enrichment_experiment.httpx.Client") as client,
            ):
                run_orcid(root, "evaluation", "research@example.org", rules)
            client.assert_not_called()

    def test_budget_counts_failed_reserved_requests(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rules = self.setup_root(root)
            write_new(root / "requests" / "0001.json", {"outcome": "failed_before_response"})
            with (
                patch("sfr_enrichment_legacy.enrichment_experiment.MAX_REQUESTS", 1),
                patch("sfr_enrichment_legacy.enrichment_experiment.httpx.Client") as factory,
                contextlib.redirect_stdout(io.StringIO()),
            ):
                run_orcid(root, "pilot", "research@example.org", rules)
            factory.return_value.__enter__.return_value.get.assert_not_called()
            self.assertTrue(
                all(row["orcid_status"] == "not_checked" for row in latest_results(root).values())
            )

    def test_successful_restart_does_not_repeat_requests(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rules = self.setup_root(root)
            client = httpx.Client(
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(200, json={"person": {}})
                )
            )
            with (
                patch(
                    "sfr_enrichment_legacy.enrichment_experiment.httpx.Client", return_value=client
                ),
                patch("sfr_enrichment_legacy.enrichment_experiment.time.sleep"),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                run_orcid(root, "pilot", "research@example.org", rules)
            before = len(list((root / "requests").glob("*.json")))
            with (
                patch("sfr_enrichment_legacy.enrichment_experiment.httpx.Client") as factory,
                contextlib.redirect_stdout(io.StringIO()),
            ):
                run_orcid(root, "pilot", "research@example.org", rules)
            factory.return_value.__enter__.return_value.get.assert_not_called()
            self.assertEqual(len(list((root / "requests").glob("*.json"))), before)

    def test_interruption_after_raw_recovers_without_network_or_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rules = self.setup_root(root)
            raw_hashes = {}
            for i in range(10):
                path = root / "raw" / f"0000-0000-0000-{i:04d}.json"
                write_new(
                    path,
                    {
                        "person": {
                            "emails": {
                                "email": [{"email": "public@example.org", "visibility": "public"}]
                            }
                        }
                    },
                )
                raw_hashes[path] = sha(path)
            with (
                patch("sfr_enrichment_legacy.enrichment_experiment.httpx.Client") as factory,
                contextlib.redirect_stdout(io.StringIO()),
            ):
                run_orcid(root, "pilot", "research@example.org", rules)
            factory.return_value.__enter__.return_value.get.assert_not_called()
            self.assertEqual(len(latest_results(root)), 10)
            self.assertTrue(all(row["recovered_from_raw"] for row in latest_results(root).values()))
            self.assertTrue(all(sha(path) == digest for path, digest in raw_hashes.items()))
            self.assertEqual(len(list((root / "cache").glob("*.json"))), 10)


if __name__ == "__main__":
    unittest.main()
