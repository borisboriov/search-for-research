"""Offline source boundaries and lossless comparison projection."""

import argparse
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

from enrichment_contact_first import digest
from enrichment_experiment import sha
from enrichment_glm_compare import compact, legacy_pdf_text, summarize
from enrichment_glm_runner import (
    check_job_budget,
    continuation_plan,
    drain_provider_refusals,
    experiment,
    frozen,
    run_pi,
    source_bound_candidate,
)
from enrichment_glm_tools import SourceHost, search_links
from enrichment_verification import immutable_json


class GLMRunnerTests(unittest.TestCase):
    def test_continuation_excludes_spent_jobs_and_enforces_shared_30_cap(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sample = [{"id": f"A{i}"} for i in range(10)]
            immutable_json(root / "sample.json", sample)
            immutable_json(root / "manifest.json", {"sample_sha256": sha(root / "sample.json")})
            immutable_json(root / "stopped.json", {})
            immutable_json(root / "metrics-reconciled.json", {"day_jobs_after": 19})
            for aid in ("A0", "A1"):
                immutable_json(
                    root / "model-jobs" / f"{aid}.json", {"stage": "collect", "author_id": aid}
                )
            immutable_json(
                root / "transfer-SHA-index-test.json",
                {
                    "private_file_sha256": {
                        str(p.relative_to(root)): sha(p) for p in root.rglob("*") if p.is_file()
                    }
                },
            )
            plan = continuation_plan(sample, root)
            self.assertEqual(plan["groups"], [["A2"], ["A3", "A4", "A5"], ["A6", "A7", "A8", "A9"]])
            self.assertEqual(plan["day_jobs_before"], 19)
            new = root / "new"
            manifest = plan | {"day_cap": 30, "max_Sol_jobs": 3}
            with (
                patch("enrichment_glm_runner.frozen", return_value=manifest),
                self.assertRaisesRegex(ValueError, "excluded"),
            ):
                run_pi(new, sample[0])
            for i in range(8):
                immutable_json(new / "model-jobs" / f"G{i}.json", {"stage": "collect"})
            with self.assertRaisesRegex(ValueError, "job cap"):
                check_job_budget(new, manifest, "collect")
            self.assertEqual(len(check_job_budget(new, manifest, "verify")), 8)
            for i in range(3):
                immutable_json(new / "model-jobs" / f"S{i}.json", {"stage": "verify"})
            with self.assertRaisesRegex(ValueError, "job cap"):
                check_job_budget(new, manifest, "verify")
            (root / "sample.json").write_text("[]")
            with self.assertRaisesRegex(ValueError, "seal mismatch"):
                continuation_plan(sample, root)

    def test_first_nonempty_pair_precedes_further_collection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sample = [{"id": f"A{i}"} for i in range(10)]
            immutable_json(root / "sample.json", sample)
            immutable_json(
                root / "manifest.json",
                {
                    "groups": [["A2"], ["A3", "A4", "A5"], ["A6", "A7", "A8", "A9"]],
                    "first_usable_pair_before_further_collection": True,
                },
            )
            calls = []

            def collect(
                _root: Path, profile: dict[str, Any], *, probe: bool = False
            ) -> dict[str, Any]:
                if not probe:
                    calls.append(profile["id"])
                return {"done": True, "model_requests": 1}

            def verify(_root: Path, index: int, _remaining: float) -> dict[str, Any]:
                calls.append(f"verify{index}")
                return {"index": index}

            args = argparse.Namespace(
                root=root,
                baseline=root,
                mode="live",
                scope=root,
                scope_url="scope",
                baseline_pdf_module_path=root,
                remaining_percent=6,
            )
            with (
                patch("enrichment_glm_runner.freeze"),
                patch("enrichment_glm_runner.run_pi", side_effect=collect),
                patch(
                    "enrichment_glm_runner.source_bound_candidate",
                    side_effect=lambda _r, aid: aid != "A2",
                ),
                patch("enrichment_glm_compare.verify_group", side_effect=verify),
                patch("enrichment_glm_compare.summarize", return_value={}),
            ):
                experiment(args)
            self.assertEqual(calls[:5], ["A2", "verify0", "A3", "verify1", "A4"])
            self.assertEqual(calls.count("verify1"), 1)
            self.assertEqual(
                [c for c in calls if c.startswith("A")], [f"A{i}" for i in range(2, 10)]
            )
            self.assertFalse(source_bound_candidate(root, "A2"))
            empty = root / "empty.json"
            immutable_json(
                empty, {"evidence_pool": {}, "items": [], "profile_evidence": {"identity": []}}
            )
            immutable_json(
                root / "prepared/A2.json", {"input_path": str(empty), "sha256": sha(empty)}
            )
            self.assertFalse(source_bound_candidate(root, "A2"))

    def test_search_requires_actual_title_link_rows_not_snippets(self) -> None:
        raw: dict[str, Any] = {
            "message": {
                "result": {
                    "content": [
                        {
                            "text": json.dumps(
                                [
                                    {
                                        "title": "Institute",
                                        "link": "https://example.org/",
                                        "content": json.dumps(
                                            [
                                                {
                                                    "title": "Snippet trap",
                                                    "link": "https://example.org/forbidden",
                                                }
                                            ]
                                        ),
                                    },
                                    {"title": "Snippet", "content": "https://example.org/person"},
                                    {"title": "Private", "link": "file:///private/person"},
                                ]
                            )
                        }
                    ]
                }
            }
        }
        self.assertEqual(search_links(raw), ["https://example.org/"])
        raw["message"]["result"]["isError"] = True
        self.assertEqual(search_links(raw), [])

    def test_live_gets_only_known_orcid_and_cannot_open_guessed_page(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch("enrichment_glm_tools.read", side_effect=AssertionError("baseline leak")):
                host = SourceHost(root, {"id": "A1", "orcid": "0000-0002-2614-0146"}, "live")
            self.assertEqual(
                list(host.allowed), ["https://pub.orcid.org/v3.0/0000-0002-2614-0146/record"]
            )
            with patch("enrichment_glm_tools.PublicLoader") as loader:
                with self.assertRaisesRegex(ValueError, "Unregistered"):
                    asyncio.run(host.source("https://example.org/guessed-person"))
                loader.assert_not_called()

    def test_binding_cannot_fetch_unread_source_or_accept_invented_contact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = SourceHost(root, {"id": "A1"}, "live")
            url = "https://example.org/"
            raw: dict[str, Any] = {
                "author_id": "A1",
                "items": [
                    {
                        "field": "personal_contact",
                        "value": "invented@example.org",
                        "url": url,
                        "quote": "real@example.org",
                    }
                ],
                "profile_evidence": {"identity": [], "current_affiliation": []},
            }
            host.allowed[url] = 0
            with patch("enrichment_glm_tools.PublicLoader") as loader:
                with self.assertRaisesRegex(ValueError, "cannot initiate HTTP"):
                    asyncio.run(host.bind(raw))
                loader.assert_not_called()
            record = root / "source.json"
            immutable_json(record, {"x": 1})
            source = {
                "url": url,
                "checked_at": "2026-10-10",
                "source_kind": "direct_http",
                "body_sha256": "b",
                "text_sha256": "t",
            }
            host.records[url] = record
            with patch.object(
                host,
                "source",
                AsyncMock(return_value=(record, source, "real@example.org", "real@example.org")),
            ):
                with self.assertRaisesRegex(ValueError, "Contact value not literal"):
                    asyncio.run(host.bind(raw))
                raw["items"][0]["value"] = "real@example.org"
                packet = asyncio.run(host.bind(raw))
                self.assertEqual(packet["items"][0]["value"], "real@example.org")
                self.assertEqual(packet["evidence_pool"]["E0001"]["excerpt"], "real@example.org")

    def test_compaction_preserves_every_original_quote_and_refs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            record = root / "source.json"
            immutable_json(record, {"url": "https://example.org/"})
            text = "abcdefghij"
            pool = {}
            for ref, start, end, rep in (
                ("E1", 0, 5, "static_text"),
                ("E2", 3, 8, "structured_json"),
                ("E3", 8, 10, "static_text"),
                ("E4", 0, 2, "html_attribute"),
            ):
                pool[ref] = {
                    "source_record_path": str(record),
                    "source_record_sha256": sha(record),
                    "representation": rep,
                    "start": start,
                    "end": end,
                    "excerpt": text[start:end],
                    "body_sha256": digest(text.encode()),
                }
            inp = {
                "evidence_pool": pool,
                "items": [{"evidence_refs": ["E1", "E2", "E3", "E4"]}],
                "profile_evidence": {"identity": ["E2"], "current_affiliation": ["E4"]},
            }
            with patch("enrichment_glm_compare.checked_source", return_value=(text, text)):
                projected = compact(inp)
            self.assertEqual(len(projected["evidence_pool"]), 2)
            self.assertEqual(len(projected["items"][0]["evidence_refs"]), 2)
            for _ref, row in pool.items():
                refs = projected["items"][0]["evidence_refs"]
                self.assertTrue(
                    any(row["excerpt"] in projected["evidence_pool"][r]["excerpt"] for r in refs)
                )
            self.assertEqual(inp["evidence_pool"], pool)
            pool["E1"]["excerpt"] = "tampered"
            with (
                patch("enrichment_glm_compare.checked_source", return_value=(text, text)),
                self.assertRaisesRegex(ValueError, "quote changed"),
            ):
                compact(inp)

    def test_historical_parser_refuses_fresh_pdf_before_subprocess(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            immutable_json(root / "manifest.json", {"baseline_pdf_body_sha256": []})
            with patch("enrichment_glm_compare.subprocess.run") as run:
                with self.assertRaisesRegex(ValueError, "cannot process a new PDF"):
                    legacy_pdf_text(root, b"%PDF-new")
                run.assert_not_called()

    def test_public_search_challenge_stops_domain_and_is_not_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = SourceHost(root, {"id": "A1"}, "live")
            with (
                patch("enrichment_glm_tools.PublicLoader") as loader,
                patch("enrichment_glm_tools.checked_source", return_value=("challenge-form", "")),
            ):
                loader.return_value.load = AsyncMock(
                    return_value={"url": "https://html.duckduckgo.com/"}
                )
                with self.assertRaisesRegex(ValueError, "domain stopped"):
                    asyncio.run(host.public_search("Name"))
            self.assertTrue(list((root / "domain-stops").glob("domain-stop-*.json")))
            self.assertFalse(host.records)
            with self.assertRaisesRegex(ValueError, "identical search retry"):
                asyncio.run(host.public_search("Name"))

    def test_empty_unknown_pairs_do_not_pass_quality_and_missing_cost_is_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run"
            baseline = Path(temporary) / "baseline"
            unknown = {
                "identity": "unknown",
                "current_affiliation": "unknown",
                "contacts": [],
                "unaccepted_contacts": [],
                "unaccepted_atoms": [],
                "readiness": "unknown",
            }
            immutable_json(
                root / "manifest.json",
                {
                    "baseline_root": str(baseline),
                    "method": "glm-public-runner-v1",
                    "mode": "live",
                    "sample_sha256": "frozen",
                },
            )
            immutable_json(
                root / "sample.json", [{"id": f"A{i}", "name": f"Person{i}"} for i in range(10)]
            )
            for i in range(10):
                aid = f"A{i}"
                immutable_json(baseline / "results" / f"{aid}.json", {})
                immutable_json(baseline / "prepared" / f"{aid}.json", {"input_path": "unused"})
                immutable_json(
                    baseline / "runs" / aid / "native_verifier/receipt.json",
                    {"tokens": {}, "wall_elapsed_seconds": 0},
                )
                for leg in ("baseline", "GLM"):
                    immutable_json(root / "comparison-results" / leg / f"{aid}.json", {})
            immutable_json(root / "model-jobs" / "A0-GLM-reserved.json", {})
            with patch("enrichment_glm_compare.facts", return_value=unknown):
                summarize(root)
            metrics = json.loads((root / "metrics.json").read_text())
            self.assertEqual(metrics["profiles_paired_verified"], 10)
            self.assertFalse(metrics["all_paired_profiles_nonregression"])
            self.assertFalse(metrics["GLM_usage_complete"])
            self.assertIsNone(metrics["GLM_total_token_usage_exact"])
            self.assertIsNone(metrics["GLM_wall_seconds_exact"])
            immutable_json(root / "model-jobs/group-00-Sol-reserved.json", {})
            immutable_json(
                root / "groups/00/native_verifier/receipt.json",
                {"tokens": {"input_tokens": 100, "output_tokens": 10}, "wall_elapsed_seconds": 1},
            )
            with patch("enrichment_glm_compare.facts", return_value=unknown):
                summarize(root, suffix="-reconciled")
            partial = json.loads((root / "metrics-reconciled.json").read_text())
            self.assertIsNone(partial["Sol_usage"]["cached_input_tokens"])
            self.assertIsNone(partial["Sol_usage"]["reasoning_output_tokens"])
            self.assertIsNone(partial["Sol_uncached_input"])
            self.assertIsNone(partial["Sol_total_token_usage_exact"])
            self.assertNotEqual(partial["Sol_usage_observation"], "no_jobs")
            immutable_json(
                root / "runs/A0/collector/receipt.json",
                {
                    "author_id": "A0",
                    "usage_complete": True,
                    "token_fields_complete": False,
                    "token_usage": {},
                    "model_requests": 1,
                    "wall_elapsed_seconds": 1,
                },
            )
            with patch("enrichment_glm_compare.facts", return_value=unknown):
                summarize(root, suffix="-missing-GLM-fields")
            missing = json.loads((root / "metrics-missing-GLM-fields.json").read_text())
            self.assertFalse(missing["GLM_usage_complete"])
            self.assertIsNone(missing["GLM_total_token_usage_exact"])
            self.assertEqual(
                missing["GLM_usage_observation"], "observed_lower_bound_incomplete_jobs"
            )

    def test_late_refusal_durable_drain_blocks_next_job(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = root / "pi"
            immutable_json(run / "000001-host-event.json", {"type": "done"})
            # Written after the live host scan and just before stdout EOF.
            immutable_json(
                run / "000002-host-event.json", {"type": "upstream_refusal", "status": None}
            )
            immutable_json(root / "sample.json", [])
            immutable_json(
                root / "manifest.json",
                {
                    "method": "glm-public-runner-v1",
                    "sample_sha256": sha(root / "sample.json"),
                    "code_sha256": {},
                    "deadline_acquisition": "2099-01-01T00:00:00+00:00",
                },
            )
            drain_provider_refusals(root, run)
            with self.assertRaisesRegex(ValueError, "quota refusal"):
                frozen(root)
            receipt = json.loads((root / "quota-stopped.json").read_text())
            self.assertEqual(receipt["source_event_sha256"], sha(run / "000002-host-event.json"))

    def test_replay_has_no_live_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            immutable_json(root / "manifest.json", {"baseline_root": str(root / "fixtures")})
            host = SourceHost(root, {"id": "A1", "orcid": "0000-0002-2614-0146"}, "replay")
            with patch("enrichment_glm_tools.PublicLoader") as loader:
                with self.assertRaisesRegex(ValueError, "no live fallback"):
                    asyncio.run(host.source(next(iter(host.allowed))))
                loader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
