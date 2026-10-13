"""Offline source boundaries and lossless comparison projection."""

import argparse
import asyncio
import copy
import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import test_enrichment_contact_first as contact_fixture

from sfr_enrichment.binding import SourceHost, search_links
from sfr_enrichment.evidence import immutable_json
from sfr_enrichment.semantics import prepare_control
from sfr_enrichment_legacy.enrichment_contact_first import digest
from sfr_enrichment_legacy.enrichment_experiment import sha
from sfr_enrichment_legacy.enrichment_fragments import process_partial
from sfr_enrichment_legacy.enrichment_glm_compare import compact, legacy_pdf_text, summarize
from sfr_enrichment_legacy.enrichment_glm_runner import (
    check_job_budget,
    continuation_plan,
    drain_provider_refusals,
    experiment,
    experiment_live3,
    frozen,
    live3_schema,
    run_pi,
    source_bound_candidate,
    verify_live3,
)
from sfr_enrichment_legacy.enrichment_verifier_benchmark import check_schema


class PublicationTests(unittest.TestCase):
    def test_fresh_typed_work_binding_and_reserved_query_precede_resolver(self) -> None:
        anchor = {
            "title": "A New Face for DSpace",
            "doi": "10.1045/november2007-phillips",
            "query": '"A New Face for DSpace" "10.1045/november2007-phillips"',
        }
        for incorrect in (False, True):
            with self.subTest(incorrect=incorrect), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                immutable_json(
                    root / "manifest.json",
                    {"publication_anchor": anchor, "collector_interface": "fragment-ids"},
                )
                host = SourceHost(root, {"id": "A1", "orcid": "0000-0001-7196-1640"}, "live")
                with self.assertRaisesRegex(ValueError, "fresh observed"):
                    host.check_publication_query(anchor["query"])
                url = next(iter(host.allowed))
                source = {
                    "source_kind": "structured_orcid",
                    "url": url,
                    "body_sha256": "body",
                    "text_sha256": "text",
                    "checked_at": "2026-10-11",
                }
                metadata = {
                    "activities-summary": {
                        "works": {
                            "group": [
                                {
                                    "work-summary": [
                                        {
                                            "put-code": 123,
                                            "title": {"title": {"value": anchor["title"]}},
                                            "external-ids": {
                                                "external-id": [
                                                    {
                                                        "external-id-type": "doi"
                                                        if not incorrect
                                                        else "isbn",
                                                        "external-id-value": anchor["doi"],
                                                    }
                                                ]
                                            },
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                }
                if incorrect:
                    with self.assertRaisesRegex(ValueError, "absent or ambiguous"):
                        host.bind_publication(source, json.dumps(metadata))
                    self.assertFalse((root / "publication-anchor-observed.json").exists())
                else:
                    host.bind_publication(source, json.dumps(metadata))
                    host.check_publication_query(anchor["query"])
                    with self.assertRaises(ValueError):
                        host.check_publication_query("Alexey Maslov MEPhI")
                    with patch("sfr_enrichment.binding.PublicLoader") as loader:
                        with self.assertRaisesRegex(ValueError, "query must be reserved"):
                            asyncio.run(host.source("https://doi.org/" + anchor["doi"]))
                        with self.assertRaisesRegex(ValueError, "must precede"):
                            asyncio.run(host.public_search("name query"))
                        loader.assert_not_called()
                    host.publication_search_reserved = True
                    host.check_publication_query("Alexey Maslov MEPhI")
                    record = json.loads((root / "publication-anchor-observed.json").read_text())
                    self.assertTrue(record["resolver_NOT_search_exact_URL"])
                    self.assertEqual(record["work_put_code"], 123)


class PartialPolicyTests(unittest.TestCase):
    def test_saved_replay_is_finite_without_model_or_source_calls(self) -> None:
        from sfr_enrichment_legacy.enrichment_live_partial import INDEX, replay

        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp).resolve()
            previous, root = parent / "previous", parent / "new"
            self.saved(previous)
            immutable_json(previous / "stopped.json", {})
            immutable_json(
                previous / INDEX,
                {
                    "private_file_sha256": {
                        str(p.relative_to(previous)): sha(p)
                        for p in previous.rglob("*")
                        if p.is_file()
                    }
                },
            )
            scope = parent / "scope.md"
            scope.write_text("Synthetic offline scope")
            args = argparse.Namespace(
                root=root,
                previous=previous,
                scope=scope,
                scope_url="test",
                deadline=(datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            )
            with (
                patch("sfr_enrichment_legacy.enrichment_live_partial.SEAL", sha(previous / INDEX)),
                patch("sfr_enrichment_legacy.enrichment_live_partial.CASES", [{"author_id": "A1"}]),
                patch(
                    "sfr_enrichment_legacy.enrichment_live_partial.subprocess.check_output",
                    side_effect=lambda cmd, **_: "" if "status" in cmd else "a" * 40,
                ),
                patch("sfr_enrichment_legacy.enrichment_native.execute") as execute,
                patch("sfr_enrichment.binding.PublicLoader") as loader,
            ):
                metrics = replay(args)
                self.assertEqual(metrics["new_model_jobs"], 0)
                self.assertEqual(metrics["cases"][0]["new_status"], "accepted")
                execute.assert_not_called()
                loader.assert_not_called()
                with self.assertRaisesRegex(ValueError, "New offline root"):
                    replay(args)
            self.assertTrue((root / "stopped.json").exists())
            self.assertEqual(
                (root / "inputs/A1/raw-result.json").read_bytes(),
                (previous / "verification/A1/native/raw-result.json").read_bytes(),
            )

    def test_partial_is_saved_separately_from_full_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            builder = Live3Tests()
            host, _ = builder.fixture(root, city=True)

            def reply(*args: Any, **kwargs: Any) -> tuple[Path, dict[str, Any]]:
                path, receipt = builder.reply(*args, **kwargs)
                raw = json.loads(path.read_text())
                raw["items"][0].update(identity_verdict="supported", object_relation="supported")
                raw["items"][1].update(information_date="2019-12-11", date_basis="source_metadata")
                path.write_text(json.dumps(raw))
                receipt["raw_result_sha256"] = sha(path)
                (path.parent / "receipt.json").write_text(json.dumps(receipt))
                return path, receipt

            with patch("sfr_enrichment_legacy.enrichment_native.execute", side_effect=reply):
                result = verify_live3(root, host.profile, 85)
            self.assertEqual(result["status"], "partial")
            self.assertEqual(result["counts"]["validated_atoms"], 1)
            self.assertTrue((root / "verification/A1/partial-verdict.json").exists())
            self.assertFalse((root / "verification/A1/verdict.json").exists())

    def saved(self, root: Path, *, empty: bool = False) -> tuple[Any, ...]:
        builder = Live3Tests()
        host, _ = builder.fixture(root, identity_only=empty)
        with patch("sfr_enrichment_legacy.enrichment_native.execute", side_effect=builder.reply):
            verify_live3(root, host.profile, 85)
        directory = root / "verification/A1"
        task = json.loads((directory / "task.json").read_text())
        raw = json.loads((directory / "native/raw-result.json").read_text())
        receipt = json.loads((directory / "native/receipt.json").read_text())
        return task["semantic_input"], host.full_corpus(), task, raw, receipt

    def process(self, args: tuple[Any, ...]) -> dict[str, Any]:
        source, corpus, task, raw, receipt = args
        # Synthetic mutation tests have their own consistent raw receipt.
        raw_sha = digest(json.dumps(raw, sort_keys=True).encode())
        receipt = receipt | {"raw_result_sha256": raw_sha}
        return process_partial(source, corpus, task, raw, receipt, task["input_sha256"], raw_sha)

    def test_valid_contact_survives_same_unsupported_metadata_date_as_city(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            args = self.saved(Path(temp))
            source, corpus, _, raw, _ = args
            contact = raw["items"][0]
            contact.update(identity_verdict="supported", object_relation="supported")
            key = next(k for k, v in corpus["values"].items() if v["kind"] != "email")
            value = corpus["values"][key]
            ref = value["fragment_id"]
            source["items"].append(
                {
                    "item_id": key,
                    "origin": "collector",
                    "original_field": "city",
                    "value": corpus["fragments"][ref]["excerpt"],
                    "evidence_refs": [ref],
                }
            )
            city = copy.deepcopy(contact)
            city.update(
                item_id=key,
                evidence_refs=[ref],
                information_date="2019-12-11",
                date_basis="source_metadata",
                current_applicability="unknown",
            )
            raw["items"].append(city)
            original = copy.deepcopy(raw)
            result = self.process(args)
            self.assertEqual(result["packet_status"], "partial")
            self.assertEqual(
                result["counts"],
                {
                    "requested_atoms": 2,
                    "validated_atoms": 1,
                    "rejected_atoms": 1,
                    "blocked_atoms": 0,
                    "usable_atoms": 1,
                },
            )
            self.assertIn("metadata", result["items"][1]["reason"])
            self.assertFalse(result["fully_accepted_nonempty"])
            self.assertNotIn("result", result)
            self.assertEqual(raw, original)
            self.assertEqual(result["raw_result"], original)

    def test_common_gates_block_every_atom(self) -> None:
        mutations = (
            "identity",
            "author",
            "source",
            "provenance",
            "schema",
            "span",
            "id",
            "profile_date",
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                args = self.saved(Path(temp))
                source, corpus, task, raw, receipt = args
                if mutation == "identity":
                    raw["profile_assessments"]["identity"]["verdict"] = "conflicting"
                elif mutation == "author":
                    raw["author_id"] = "OTHER"
                elif mutation == "source":
                    task["source_catalog"] = []
                elif mutation == "provenance":
                    receipt["agent_id"] = source["collector_agent_id"]
                elif mutation == "schema":
                    del raw["profile_assessments"]["activity"]["status"]
                elif mutation == "span":
                    corpus["values"][source["items"][0]["item_id"]]["end"] += 1
                elif mutation == "id":
                    raw["items"][0]["item_id"] = "foreign"
                else:
                    raw["profile_assessments"]["activity"].update(
                        information_date="2099", date_basis="content"
                    )
                result = self.process(args)
                self.assertEqual(result["packet_status"], "rejected")
                self.assertEqual(result["counts"]["blocked_atoms"], 1)
                self.assertEqual(result["counts"]["usable_atoms"], 0)
                self.assertTrue(result["common_error"])

    def test_all_invalid_empty_and_previous_valid_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            args = self.saved(Path(temp))
            result = self.process(args)
            self.assertTrue(result["fully_validated"])
            self.assertEqual(
                result["items"][0]["effective_classification"],
                result["items"][0]["original_classification"],
            )
            args[3]["items"][0]["information_date"] = "2099"
            result = self.process(args)
            self.assertEqual(result["packet_status"], "rejected")
            self.assertEqual(result["counts"]["rejected_atoms"], 1)
            self.assertEqual(result["counts"]["usable_atoms"], 0)
            args[4]["raw_result_sha256"] = "wrong"
            result = process_partial(
                args[0], args[1], args[2], args[3], args[4], args[2]["input_sha256"], "actual"
            )
            self.assertIn("receipt SHA", result["common_error"])
        with tempfile.TemporaryDirectory() as temp:
            result = self.process(self.saved(Path(temp), empty=True))
            self.assertEqual(result["packet_status"], "identity_only")
            self.assertTrue(result["fully_validated"])
            self.assertFalse(result["fully_accepted_nonempty"])
            self.assertEqual(result["counts"]["usable_atoms"], 0)


class Live3Tests(unittest.TestCase):
    def fixture(
        self, root: Path, *, identity_only: bool = False, city: bool = False
    ) -> tuple[SourceHost, dict[str, Any]]:
        profile = {"id": "A1", "name": "Jane Researcher"}
        immutable_json(root / "sample.json", [profile])
        immutable_json(
            root / "manifest.json",
            {
                "method": "glm-public-runner-v1",
                "experiment_kind": "live3-independent-sol-v1",
                "collector_interface": "fragment-ids",
                "mode": "live",
                "code_sha256": {},
                "sample_sha256": sha(root / "sample.json"),
                "max_GLM_jobs": 3,
                "max_Sol_jobs": 3,
                "day_jobs_before": 35,
                "day_cap": 41,
                "full_prompt_utf8_cap": 1000000,
                "Sol_timeout_seconds": 900,
                "deadline_acquisition": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            },
        )
        host = SourceHost(root, profile, "live")
        source = contact_fixture.ContactFirstTests().run_source(
            host.directory,
            "<h1>Jane Researcher</h1><p>jane@example.edu</p>"
            + "x" * 6000
            + "<p>OTHER AUTHOR: address belongs to somebody else. Dated2026</p>",
        )
        path = host.directory / ("source-" + digest(contact_fixture.URL.encode()) + ".json")
        host.allowed[contact_fixture.URL], host.records[contact_fixture.URL] = 0, path
        view = asyncio.run(
            host.tool({"action": "read", "url": contact_fixture.URL, "query": "", "start": 0})
        )
        self.assertTrue(view["candidate_ids_NOT_personal_verdicts"])
        key = next(k for k, v in view["values"].items() if v["kind"] == "email")
        ref = view["values"][key]["fragment_id"]
        raw: dict[str, Any] = {
            "author_id": "A1",
            "selections": []
            if identity_only
            else [{"value_id": key, "field": "personal_contact", "evidence_refs": [ref]}],
            "profile_evidence": {"identity": [ref], "current_affiliation": []},
            "limitations": "",
        }
        check_schema(raw, live3_schema())
        if city:
            text_key = next(k for k, v in view["values"].items() if v["kind"] != "email")
            raw["selections"].append(
                {
                    "value_id": text_key,
                    "field": "city",
                    "evidence_refs": [view["values"][text_key]["fragment_id"]],
                }
            )
        packet = asyncio.run(host.bind(raw))
        immutable_json(root / "collector.json", packet)
        prepared = prepare_control(
            root,
            profile,
            root / "collector.json",
            packet["evidence_pool"],
            Path(__file__).resolve().parents[2] / "enrichment/configs/verifier-v3.md",
            sha(root / "sample.json"),
            namespace="live3",
            source_kind="GLM_selected_live_public_bodies",
        )
        immutable_json(
            root / "prepared/A1.json", {"input_path": str(prepared), "sha256": sha(prepared)}
        )
        self.assertEqual(source["text_sha256"], host.full_corpus()["sources"][0]["text_sha256"])
        return host, raw

    def reply(
        self,
        directory: Path,
        prompt: str,
        _schema: dict[str, Any],
        _cwd: Path,
        *,
        missing_status: bool = False,
        wrong_year: bool = False,
        **kwargs: Any,
    ) -> tuple[Path, dict[str, Any]]:
        task = json.loads(prompt)["task"]
        source = task["semantic_input"]
        self.assertEqual(kwargs["model"], "gpt-6.1-sol")
        self.assertEqual(kwargs["effort"], "high")
        self.assertTrue(kwargs["disable_mcp"])
        self.assertEqual(kwargs["required_config"]["provider"], "openai")
        refs = list(source["evidence_pool"])
        self.assertIn("OTHER AUTHOR", source["evidence_pool"][refs[-1]]["excerpt"])
        row = {
            "verdict": "insufficient",
            "evidence_refs": [refs[0]],
            "information_date": None,
            "date_basis": "unknown",
            "explanation": "Недостаточно",
            "status": "unknown",
        }
        axis = {k: v for k, v in row.items() if k != "status"}
        activity = dict(row)
        if missing_status:
            activity.pop("status")
        result = {
            k: task[k]
            for k in ("author_id", "input_sha256", "batch_input_sha256", "batch_ticket_id")
        }
        result.update(
            rules_version="semantic-v3",
            items=[
                {
                    "item_id": item["item_id"],
                    "text_verdict": "supported",
                    "identity_verdict": "conflicting",
                    "field_verdict": "correct",
                    "corrected_field": None,
                    "fact_kind": "literal",
                    "object_type": "scientist",
                    "object_relation": "conflicting",
                    "student_level": ["unknown"],
                    "information_date": "2027" if wrong_year else "2026",
                    "date_basis": "content",
                    "current_applicability": "historical",
                    "evidence_refs": [refs[-1]],
                    "explanation": "Не целевой автор",
                    "question": "Чей адрес?",
                }
                for item in source["items"]
            ],
            profile_assessments={
                "identity": axis | {"verdict": "supported"},
                "current_affiliation": axis,
                "activity": activity,
            },
            summary={
                k: "Неизвестно" for k in ("known", "unknown", "identity", "current_opportunity")
            },
        )
        directory.mkdir(parents=True)
        immutable_json(directory / "raw-result.json", result)
        receipt = {
            "agent_id": "native:independent-test",
            "tool_calls": 0,
            "runtime_status": "runtime_not_exposed",
            "model": None,
            "effort": None,
            "tokens": None,
            "cost_usd": None,
            "raw_result_sha256": sha(directory / "raw-result.json"),
        }
        immutable_json(directory / "receipt.json", receipt)
        return directory / "raw-result.json", receipt

    def test_full_pipeline_bind_and_independent_verifier_can_use_unselected_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            host, raw = self.fixture(root)
            with patch(
                "sfr_enrichment_legacy.enrichment_native.execute", side_effect=self.reply
            ) as execute:
                outcome = verify_live3(root, host.profile, 85)
            self.assertEqual(outcome["status"], "verified")
            self.assertEqual(execute.call_count, 1)
            verdict = json.loads((root / "verification/A1/verdict.json").read_text())
            self.assertEqual(list(verdict["classifications"]), [raw["selections"][0]["value_id"]])
            self.assertFalse(
                verdict["classifications"][raw["selections"][0]["value_id"]]["usable_coverage"]
            )
            self.assertEqual(verdict["result"]["items"][0]["identity_verdict"], "conflicting")

    def test_identity_only_packet_is_checked_but_fully_empty_packet_is_not(self) -> None:
        for empty in (False, True):
            with self.subTest(empty=empty), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                host, _ = self.fixture(root, identity_only=True)
                if empty:
                    info = json.loads((root / "prepared/A1.json").read_text())
                    path = Path(info["input_path"])
                    source = json.loads(path.read_text())
                    source["profile_evidence"]["identity"] = []
                    path.write_text(json.dumps(source))
                    (root / "prepared/A1.json").write_text(
                        json.dumps({"input_path": str(path), "sha256": sha(path)})
                    )
                with patch(
                    "sfr_enrichment_legacy.enrichment_native.execute", side_effect=self.reply
                ) as execute:
                    outcome = verify_live3(root, host.profile, 85)
                self.assertEqual(outcome["status"], "skipped" if empty else "verified")
                self.assertEqual(execute.call_count, 0 if empty else 1)

    def test_missing_status_and_absent_content_year_are_kept_as_raw_failure(self) -> None:
        for missing, year in ((True, False), (False, True)):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                host, _ = self.fixture(root)

                def execute(
                    *args: Any, missing: bool = missing, year: bool = year, **kwargs: Any
                ) -> tuple[Path, dict[str, Any]]:
                    return self.reply(*args, missing_status=missing, wrong_year=year, **kwargs)

                with patch("sfr_enrichment_legacy.enrichment_native.execute", side_effect=execute):
                    outcome = verify_live3(root, host.profile, 85)
                self.assertEqual(outcome["status"], "rejected")
                saved = json.loads((root / "verification/A1/native/raw-result.json").read_text())
                self.assertEqual("status" in saved["profile_assessments"]["activity"], not missing)
                self.assertFalse((root / "verification/A1/verdict.json").exists())

    def test_full_context_cap_and_tampered_source_prevent_model_job(self) -> None:
        for tamper in (False, True):
            with self.subTest(tamper=tamper), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                host, _ = self.fixture(root)
                if tamper:
                    record = json.loads(next(host.directory.glob("source-*.json")).read_text())
                    (host.directory / record["text_path"]).write_text("changed")
                else:
                    manifest = json.loads((root / "manifest.json").read_text())
                    manifest["full_prompt_utf8_cap"] = 1
                    (root / "manifest.json").write_text(json.dumps(manifest))
                with patch("sfr_enrichment_legacy.enrichment_native.execute") as execute:
                    if tamper:
                        with self.assertRaises(ValueError):
                            verify_live3(root, host.profile, 85)
                    else:
                        self.assertEqual(verify_live3(root, host.profile, 85)["status"], "skipped")
                    execute.assert_not_called()
                self.assertFalse(list((root / "model-jobs").glob("*Sol*")))

    def test_invented_or_foreign_id_is_rejected_without_fetch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            host, raw = self.fixture(root)
            raw["selections"][0]["value_id"] = "A2-foreign"
            with patch("sfr_enrichment.binding.PublicLoader") as loader:
                with self.assertRaisesRegex(ValueError, "value ID"):
                    asyncio.run(host.bind(raw))
                loader.assert_not_called()

    def test_independent_profile_failure_does_not_repeat_or_stop_other_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sample = [{"id": "A1"}, {"id": "A2"}, {"id": "A3"}]
            immutable_json(root / "sample.json", sample)
            with (
                patch(
                    "sfr_enrichment_legacy.enrichment_glm_runner.frozen",
                    return_value={
                        "experiment_kind": "live3-independent-sol-v1",
                        "day_jobs_before": 35,
                    },
                ),
                patch(
                    "sfr_enrichment_legacy.enrichment_glm_runner.run_pi",
                    return_value={"host_error": None, "usage_complete": True},
                ) as collect,
                patch(
                    "sfr_enrichment_legacy.enrichment_glm_runner.verify_live3",
                    side_effect=lambda _r, p, _q: {
                        "status": "skipped" if p["id"] == "A1" else "verified"
                    },
                ),
            ):
                result = experiment_live3(root, 85)
            self.assertEqual(collect.call_count, 4)
            self.assertEqual(len(result["rows"]), 3)
            self.assertTrue((root / "stopped.json").exists())

    def test_incomplete_runtime_stops_before_verifier_or_next_collector(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            immutable_json(root / "sample.json", [{"id": f"A{i}"} for i in range(3)])
            with (
                patch(
                    "sfr_enrichment_legacy.enrichment_glm_runner.frozen",
                    return_value={
                        "experiment_kind": "live3-independent-sol-v1",
                        "day_jobs_before": 35,
                    },
                ),
                patch(
                    "sfr_enrichment_legacy.enrichment_glm_runner.run_pi",
                    return_value={"host_error": None, "usage_complete": False},
                ) as collect,
                patch("sfr_enrichment_legacy.enrichment_glm_runner.verify_live3") as verify,
            ):
                result = experiment_live3(root, 85)
            self.assertEqual(collect.call_count, 2)  # zero-inference preflight, first profile
            verify.assert_not_called()
            self.assertEqual(result["rows"], [])
            self.assertEqual(result["partial_reason"], "Collector runtime incomplete")
            self.assertTrue((root / "stopped.json").exists())


class GLMRunnerTests(unittest.TestCase):
    def test_collector_host_failure_stops_before_next_profile_or_verifier(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sample = [{"id": f"A{i}"} for i in range(10)]
            immutable_json(root / "sample.json", sample)
            immutable_json(root / "manifest.json", {"groups": [["A4", "A5"], ["A6", "A7"]]})
            calls = []

            def collect(
                _root: Path, profile: dict[str, Any], *, probe: bool = False
            ) -> dict[str, Any]:
                if probe:
                    return {"done": True, "model_requests": 0}
                calls.append(profile["id"])
                # A real exception can have an empty message; it is still a host failure.
                return {"done": False, "model_requests": 1, "host_error": ""}

            args = argparse.Namespace(
                root=root,
                baseline=root,
                mode="live",
                scope=root,
                scope_url="scope",
                baseline_pdf_module_path=root,
                remaining_percent=4,
            )
            with (
                patch("sfr_enrichment_legacy.enrichment_glm_runner.freeze"),
                patch("sfr_enrichment_legacy.enrichment_glm_runner.run_pi", side_effect=collect),
                patch("sfr_enrichment_legacy.enrichment_glm_compare.verify_group") as verifier,
                patch("sfr_enrichment_legacy.enrichment_glm_compare.summarize", return_value={}),
            ):
                experiment(args)
            self.assertEqual(calls, ["A4"])
            verifier.assert_not_called()
            self.assertTrue((root / "stopped.json").exists())
            self.assertIn(
                "Collector host failure",
                json.loads((root / "experiment-partial.json").read_text())["reason"],
            )

    def test_remaining6_validates_both_seals_and_excludes_four_spent_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            sample = [{"id": f"A{i}"} for i in range(10)]

            def predecessor(root: Path, manifest: dict[str, Any], start: int) -> None:
                immutable_json(root / "sample.json", sample)
                immutable_json(
                    root / "manifest.json", manifest | {"sample_sha256": sha(root / "sample.json")}
                )
                immutable_json(root / "stopped.json", {})
                immutable_json(root / "metrics-reconciled.json", {"day_jobs_after": 17 + start + 2})
                for aid in (f"A{start}", f"A{start + 1}"):
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

            first, second = parent / "first", parent / "second"
            predecessor(first, {}, 0)
            predecessor(second, continuation_plan(sample, first), 2)
            plan = continuation_plan(sample, second)
            self.assertEqual(plan["scheduled_profile_ids"], [f"A{i}" for i in range(4, 10)])
            self.assertEqual(plan["excluded_spent_profile_ids"], [f"A{i}" for i in range(4)])
            self.assertEqual(plan["groups"], [["A4", "A5"], ["A6", "A7"], ["A8", "A9"]])
            self.assertEqual(plan["day_jobs_before"], 21)
            self.assertFalse(plan["first_usable_pair_before_further_collection"])
            new = parent / "new"
            manifest = plan | {"day_cap": 30, "max_Sol_jobs": 3}
            for i in range(4):
                with (
                    patch(
                        "sfr_enrichment_legacy.enrichment_glm_runner.frozen", return_value=manifest
                    ),
                    self.assertRaisesRegex(ValueError, "excluded"),
                ):
                    run_pi(new, sample[i])
            for i in range(6):
                immutable_json(new / "model-jobs" / f"G{i}.json", {"stage": "collect"})
            with self.assertRaisesRegex(ValueError, "job cap"):
                check_job_budget(new, manifest, "collect")
            for i in range(3):
                immutable_json(new / "model-jobs" / f"S{i}.json", {"stage": "verify"})
            with self.assertRaisesRegex(ValueError, "job cap"):
                check_job_budget(new, manifest, "verify")
            (first / "model-jobs/A0.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "seal mismatch"):
                continuation_plan(sample, second)

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
                patch("sfr_enrichment_legacy.enrichment_glm_runner.frozen", return_value=manifest),
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
                return {"index": index, "profiles_verified": 0 if index == 0 else 1}

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
                patch("sfr_enrichment_legacy.enrichment_glm_runner.freeze"),
                patch("sfr_enrichment_legacy.enrichment_glm_runner.run_pi", side_effect=collect),
                patch(
                    "sfr_enrichment_legacy.enrichment_glm_runner.source_bound_candidate",
                    side_effect=lambda _r, aid: aid != "A2",
                ),
                patch(
                    "sfr_enrichment_legacy.enrichment_glm_compare.verify_group", side_effect=verify
                ),
                patch("sfr_enrichment_legacy.enrichment_glm_compare.summarize", return_value={}),
            ):
                experiment(args)
            self.assertEqual(calls[:5], ["A2", "verify0", "A3", "verify1", "A4"])
            self.assertEqual(calls.count("verify1"), 1)
            self.assertEqual(
                [c for c in calls if c.startswith("A")], [f"A{i}" for i in range(2, 10)]
            )
            # A first nonempty packet that cannot fit the full context is not a verified pair.
            blocked = root / "blocked"
            immutable_json(blocked / "sample.json", sample)
            immutable_json(
                blocked / "manifest.json",
                read_manifest := json.loads((root / "manifest.json").read_text()),
            )
            calls.clear()
            args.root = blocked

            def skip(_root: Path, index: int, _remaining: float) -> dict[str, Any]:
                calls.append(f"verify{index}")
                return {"index": index, "partial": True, "model_jobs": 0}

            with (
                patch("sfr_enrichment_legacy.enrichment_glm_runner.freeze"),
                patch("sfr_enrichment_legacy.enrichment_glm_runner.run_pi", side_effect=collect),
                patch(
                    "sfr_enrichment_legacy.enrichment_glm_runner.source_bound_candidate",
                    side_effect=lambda _r, aid: aid != "A2",
                ),
                patch(
                    "sfr_enrichment_legacy.enrichment_glm_compare.verify_group",
                    side_effect=skip,
                ),
                patch("sfr_enrichment_legacy.enrichment_glm_compare.summarize", return_value={}),
            ):
                experiment(args)
            self.assertEqual(calls, ["A2", "verify0", "A3", "verify1"])
            self.assertIn(
                "not verified",
                json.loads((blocked / "experiment-partial.json").read_text())["reason"],
            )
            self.assertTrue((blocked / "stopped.json").exists())
            self.assertEqual(read_manifest["groups"][0], ["A2"])
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
            with patch("sfr_enrichment.binding.read", side_effect=AssertionError("baseline leak")):
                host = SourceHost(root, {"id": "A1", "orcid": "0000-0002-2614-0146"}, "live")
            self.assertEqual(
                list(host.allowed), ["https://pub.orcid.org/v3.0/0000-0002-2614-0146/record"]
            )
            with patch("sfr_enrichment.binding.PublicLoader") as loader:
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
            with patch("sfr_enrichment.binding.PublicLoader") as loader:
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
            with patch(
                "sfr_enrichment_legacy.enrichment_glm_compare.checked_source",
                return_value=(text, text),
            ):
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
                patch(
                    "sfr_enrichment_legacy.enrichment_glm_compare.checked_source",
                    return_value=(text, text),
                ),
                self.assertRaisesRegex(ValueError, "quote changed"),
            ):
                compact(inp)

    def test_historical_parser_refuses_fresh_pdf_before_subprocess(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            immutable_json(root / "manifest.json", {"baseline_pdf_body_sha256": []})
            with patch("sfr_enrichment.replay.subprocess.run") as run:
                with self.assertRaisesRegex(ValueError, "cannot process a new PDF"):
                    legacy_pdf_text(root, b"%PDF-new")
                run.assert_not_called()

    def test_public_search_challenge_stops_domain_and_is_not_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = SourceHost(root, {"id": "A1"}, "live")
            with (
                patch("sfr_enrichment.binding.PublicLoader") as loader,
                patch("sfr_enrichment.binding.checked_source", return_value=("challenge-form", "")),
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
            with patch("sfr_enrichment_legacy.enrichment_glm_compare.facts", return_value=unknown):
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
            with patch("sfr_enrichment_legacy.enrichment_glm_compare.facts", return_value=unknown):
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
            with patch("sfr_enrichment_legacy.enrichment_glm_compare.facts", return_value=unknown):
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
            with patch("sfr_enrichment.binding.PublicLoader") as loader:
                with self.assertRaisesRegex(ValueError, "no live fallback"):
                    asyncio.run(host.source(next(iter(host.allowed))))
                loader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
