"""Literal restoration, strict IDs and terminal bounded-stage failures."""

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from sfr_enrichment_legacy.enrichment_fragments import (
    CASES,
    DATE_GUARD_POLICY,
    catalog,
    hydrate,
    run,
    saved_source_paths,
    snapshot_source,
)


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


def metadata_fixture(
    mutation: str = "",
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Saved issue197 field/object/epoch reproduced without private contact/source bytes."""
    task, raw, provenance = fixture()
    orcid = "0000-0003-0365-8695"
    employment: dict[str, Any] = {
        "created-date": {"value": 1560767764206},
        "last-modified-date": {"value": 1576026926116},
        "put-code": 8089983,
        "department-name": "Mechanics and Mathematics department",
        "organization": {"name": "Novosibirsk State University"},
        "path": f"/{orcid}/employment/8089983",
    }
    record: dict[str, Any] = {
        "orcid-identifier": {"path": orcid},
        "description": "contact@example.org; literal content date 2007",
        "activities-summary": {
            "employments": {
                "affiliation-group": [{"summaries": [{"employment-summary": employment}]}]
            }
        },
    }
    if mutation == "same_epoch_aliases":
        employment["created-date"]["value"] = employment["last-modified-date"]["value"]
    elif mutation == "same_year_different_instants":
        employment["created-date"]["value"] = employment["last-modified-date"]["value"] - 1000
    elif mutation == "seconds":
        employment["last-modified-date"]["value"] = 1576026926
    elif mutation == "boolean":
        employment["last-modified-date"]["value"] = True
    elif mutation == "string":
        employment["last-modified-date"]["value"] = "1576026926116"
    elif mutation == "arbitrary_number":
        employment["last-modified-date"] = None
        employment["untyped_number"] = 1576026926116
    elif mutation == "collection_metadata":
        employment["last-modified-date"]["value"] = 1560767764206
        record["activities-summary"]["employments"]["last-modified-date"] = {"value": 1576026926116}
    elif mutation == "work_metadata":
        employment["last-modified-date"]["value"] = 1560767764206
        record["activities-summary"]["works"] = {"last-modified-date": {"value": 1576026926116}}
    elif mutation == "neighbor_employment":
        other = copy.deepcopy(employment)
        other["put-code"] = 99
        other["path"] = f"/{orcid}/employment/99"
        other["organization"]["name"] = "Another University"
        record["activities-summary"]["employments"]["affiliation-group"].append(
            {"summaries": [{"employment-summary": other}]}
        )
    elif mutation == "foreign_profile":
        record["orcid-identifier"]["path"] = "0000-0000-0000-0000"
    elif mutation == "wrong_object_path":
        employment["path"] = f"/{orcid}/employment/99"
    elif mutation == "uncited_field":
        employment["department-name"] = "x" * 3000
    text = json.dumps(record, ensure_ascii=False, indent=2)
    source = {
        "url": f"https://pub.orcid.org/v3.0/{orcid}/record",
        "source_kind": "structured_orcid",
        "checked_at": "2026-10-11T00:00:00+00:00",
        "body_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "text": text,
    }
    if mutation == "untyped_source":
        source["source_kind"] = "direct_http"
    elif mutation == "future_update":
        source["checked_at"] = "2018-01-01T00:00:00+00:00"
    corpus = catalog("A1", [source]) | {
        "profile": {"id": "A1", "orcid": f"https://orcid.org/{orcid}"}
    }
    task["corpus"] = corpus
    key = next(k for k, v in corpus["values"].items() if v["kind"] == "email")
    ref = corpus["values"][key]["fragment_id"]
    raw["selections"][0].update(value_id=key, evidence_refs=[ref])
    raw["items"][0].update(item_id=key, evidence_refs=[ref])
    raw["profile_assessments"]["current_affiliation"].update(
        information_date="2019-12-11",
        date_basis="source_metadata",
        evidence_refs=list(corpus["fragments"]),
    )
    if mutation == "uncited_field":
        raw["profile_assessments"]["current_affiliation"]["evidence_refs"] = [
            key for key, f in corpus["fragments"].items() if f["start"] >= 3000
        ]
    return task, raw, provenance


class FragmentTests(unittest.TestCase):
    def test_saved_orcid_employment_timestamp_uses_exact_field_object_and_utc(self) -> None:
        task, raw, provenance = metadata_fixture()
        original = copy.deepcopy(raw)
        normalized = hydrate(task, raw, provenance)
        binding = normalized["date_guard"]["metadata_bindings"][0]
        self.assertEqual(normalized["date_guard"]["policy"], DATE_GUARD_POLICY)
        self.assertEqual(binding["utc"], "2019-12-11T01:15:26.116000+00:00")
        self.assertEqual(binding["epoch_milliseconds"], 1576026926116)
        self.assertEqual(
            binding["json_path"][-3:], ["employment-summary", "last-modified-date", "value"]
        )
        self.assertEqual(binding["object_path"], "/0000-0003-0365-8695/employment/8089983")
        self.assertEqual(raw, original)
        self.assertEqual(normalized["result"]["profile_assessments"], raw["profile_assessments"])
        item = normalized["result"]["items"][0]
        self.assertEqual(item["information_date"], "2007")
        self.assertEqual(item["current_applicability"], "historical")
        self.assertFalse(normalized["derived"][item["item_id"]]["usable_coverage"])

    def test_identical_epoch_aliases_keep_both_paths_but_different_instants_reject(self) -> None:
        result = hydrate(*metadata_fixture("same_epoch_aliases"))
        binding = result["date_guard"]["metadata_bindings"][0]
        self.assertEqual(len(binding["equivalent_json_paths"]), 2)
        with self.assertRaisesRegex(ValueError, "different.*instants"):
            hydrate(*metadata_fixture("same_year_different_instants"))

    def test_metadata_dates_reject_wrong_units_objects_fields_and_uncited_spans(self) -> None:
        for mutation in (
            "seconds",
            "boolean",
            "string",
            "arbitrary_number",
            "collection_metadata",
            "work_metadata",
            "neighbor_employment",
            "foreign_profile",
            "wrong_object_path",
            "uncited_field",
            "untyped_source",
            "future_update",
        ):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                hydrate(*metadata_fixture(mutation))

    def test_metadata_does_not_accept_reading_date_or_promote_contact_to_current(self) -> None:
        for mutation in ("reading_date", "invented_day", "unknown", "contact_date"):
            with self.subTest(mutation=mutation):
                task, raw, provenance = metadata_fixture()
                axis = raw["profile_assessments"]["current_affiliation"]
                if mutation == "reading_date":
                    axis["information_date"] = "2026-10-11"
                elif mutation == "invented_day":
                    axis["information_date"] = "2019-12-12"
                elif mutation == "unknown":
                    axis["date_basis"] = "unknown"
                else:
                    raw["items"][0].update(
                        date_basis="source_metadata",
                        information_date="2019-12-11",
                        current_applicability="current",
                    )
                with self.assertRaises(ValueError):
                    hydrate(task, raw, provenance)

    def test_saved_source_inventory_includes_rendered_records_but_not_old_answers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for folder in ("sources", "rendered-sources", "prepared"):
                path = root / folder / "A1" / "source-same.json"
                path.parent.mkdir(parents=True)
                path.write_text("{}")
            paths = saved_source_paths(root, "A1")
            self.assertEqual(len(paths), 2)
            self.assertEqual({p.parent.parent.name for p in paths}, {"sources", "rendered-sources"})

    def test_rendered_snapshot_preserves_parent_decoder_and_receipts(self) -> None:
        from sfr_enrichment_legacy.enrichment_contact_first import digest

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = root / "original"
            rendered = root / "rendered"
            original.mkdir()
            rendered.mkdir()
            record = {
                "url": "https://example.org/source",
                "source_kind": "direct_http",
                "body_path": "body.bin",
                "decoded_path": "decoded.txt",
                "text_path": "text.txt",
            }
            key = digest(("direct_http" + chr(0) + record["url"]).encode())
            for directory in (original, rendered):
                for filename in ("body.bin", "decoded.txt", "text.txt"):
                    (directory / filename).write_bytes(b"saved literal bytes")
                (directory / f"request-result-{key}.json").write_text("{}")
            parent = original / "source.json"
            parent.write_text(json.dumps(record))
            decoder = original / "decoder.json"
            decoder.write_text(json.dumps({"body_path": "decoder.js"}))
            (original / "decoder.js").write_bytes(b"saved decoder bytes")
            path = rendered / "source.json"
            path.write_text(
                json.dumps(
                    record
                    | {"parent_source_path": str(parent), "decoder_receipt_path": str(decoder)}
                )
            )
            target = root / "new-root"
            copied = snapshot_source(target, path)
            self.assertIn(str(parent), copied)
            self.assertIn(str(decoder), copied)
            self.assertIn(str(original / "decoder.js"), copied)
            for old, new in copied.items():
                self.assertEqual(Path(old).read_bytes(), (target / new).read_bytes())

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
            from sfr_enrichment_legacy.enrichment_fragments import output_schema

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
                patch("sfr_enrichment_legacy.enrichment_fragments.time.time", return_value=1000.0),
                patch("sfr_enrichment_legacy.enrichment_fragments.frozen", return_value=manifest),
                patch(
                    "sfr_enrichment_legacy.enrichment_fragments.access_stopped", return_value=False
                ),
                patch(
                    "sfr_enrichment_legacy.enrichment_fragments.run_pi",
                    side_effect=ValueError("technical failure"),
                ) as glm,
                patch("sfr_enrichment_legacy.enrichment_fragments.execute") as sol,
            ):
                result = run(root, 0)
            self.assertEqual(glm.call_count, 1)
            self.assertEqual(glm.call_args.kwargs["deadline_epoch"], 1600.0)
            sol.assert_not_called()
            self.assertEqual(result["stage_jobs_reserved"], 1)
            self.assertEqual(result["cumulative_reserved"], 29)
            self.assertEqual(result["partial_reason"], "technical failure")
            self.assertTrue((root / "stopped.json").exists())

    def test_pi_bad_control_json_kills_process_and_preserves_failed_attempt(self) -> None:
        from sfr_enrichment_legacy.enrichment_pi_pilot import HIGH_CONFIGS, run_pi

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = {"z": "цитата\r\n", "a": {"F1500": "second", "F0": "first"}}
            output = {"properties": {"z": {"type": "string"}, "a": {"type": "string"}}}
            common = json.dumps(
                {"task": task, "output_json_schema": output},
                ensure_ascii=False,
                separators=(",", ":"),
            )
            process = MagicMock()
            process.stdout = iter(["invalid-json\n"])
            process.poll.return_value = None
            process.wait.return_value = -9
            with (
                patch(
                    "sfr_enrichment_legacy.enrichment_pi_pilot.access_stopped", return_value=False
                ),
                patch(
                    "sfr_enrichment_legacy.enrichment_pi_pilot.subprocess.Popen",
                    return_value=process,
                ),
                patch("sfr_enrichment_legacy.enrichment_pi_pilot.threading.Timer"),
                self.assertRaises(ValueError),
            ):
                run_pi(
                    root,
                    None,
                    "A1",
                    "pi_verifier",
                    task,
                    "shared",
                    output,
                    config_override=HIGH_CONFIGS["pi_verifier"],
                    method_override="fragment-offline3-v1",
                    expected_user_prompt_sha256=hashlib.sha256(common.encode()).hexdigest(),
                )
            request = json.loads((root / "runs/A1/pi_verifier/request.json").read_bytes())
            restored = json.dumps(
                {"task": request["task"], "output_json_schema": request["output_schema"]},
                ensure_ascii=False,
                separators=(",", ":"),
            )
            self.assertEqual(restored, common)
            self.assertEqual(
                request["expected_user_prompt_sha256"], hashlib.sha256(common.encode()).hexdigest()
            )
            process.kill.assert_called_once()
            failed = json.loads((root / "runs/A1/pi_verifier/finished.json").read_text())
            self.assertEqual(failed["exit_code"], -9)
            self.assertFalse(failed["done"])

    def test_repeat_counts_local_failures_without_retry_and_stops_common_input_failure(
        self,
    ) -> None:
        from sfr_enrichment_legacy.enrichment_fragments import output_schema
        from sfr_enrichment_legacy.enrichment_pi_pilot import HIGH_CONFIGS

        for mode in ("output", "runtime", "common", "provider_error"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / "instruction.txt").write_text("instruction")
                manifest: dict[str, Any] = {
                    "cases": CASES,
                    "stage_cap": 6,
                    "deadline": "2099-01-01T00:00:00+00:00",
                    "cumulative_start": 29,
                    "prior_partial_jobs": 1,
                    "continue_independent_output_failures": True,
                    "instruction_sha256": "instruction-sha",
                    "corpora": {},
                }
                for case in CASES:
                    aid = case["author_id"]
                    task, _, _ = fixture()
                    task["author_id"] = aid
                    for folder, value in (("corpora", task["corpus"]), ("tasks", task)):
                        (root / folder).mkdir(exist_ok=True)
                        if folder == "tasks":
                            task["input_sha256"] = hashlib.sha256(
                                (root / "corpora" / f"{aid}.json").read_bytes()
                            ).hexdigest()
                        (root / folder / f"{aid}.json").write_text(json.dumps(value))
                    prompt = json.dumps(
                        {"task": task, "output_json_schema": output_schema(task["corpus"])},
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    manifest["corpora"][aid] = {
                        "task_sha256": hashlib.sha256(
                            (root / "tasks" / f"{aid}.json").read_bytes()
                        ).hexdigest(),
                        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                    }
                raw = root / "raw.json"
                raw.write_text("{}")
                glm_calls = 0

                def glm(
                    *args: Any,
                    _manifest: dict[str, Any] = manifest,
                    _mode: str = mode,
                    _root: Path = root,
                    _raw: Path = raw,
                    **kwargs: Any,
                ) -> tuple[Path, dict[str, Any]]:
                    nonlocal glm_calls
                    glm_calls += 1
                    aid = args[2]
                    digest = _manifest["corpora"][aid]["prompt_sha256"]
                    if glm_calls == 1 and _mode in ("runtime", "provider_error"):
                        p = _root / "runs" / aid / "pi_verifier" / "pi"
                        p.mkdir(parents=True)
                        (p / "001-model-request-config.json").write_text(
                            json.dumps(
                                {
                                    "user_prompt_sha256": digest,
                                    "instruction_sha256": "instruction-sha",
                                    "effective": HIGH_CONFIGS["pi_verifier"],
                                    "tools": [],
                                }
                            )
                        )
                        if _mode == "provider_error":
                            (p / "002-session-event.json").write_text(
                                json.dumps(
                                    {
                                        "type": "message_end",
                                        "message": {
                                            "role": "assistant",
                                            "stopReason": "error",
                                            "errorMessage": "quota exhausted despite HTTP 200",
                                        },
                                    }
                                )
                            )
                        raise ValueError("unfinished local reply")
                    return _raw, {"user_prompt_sha256": "wrong" if _mode == "common" else digest}

                def sol(*args: Any, _raw: Path = raw, **kwargs: Any) -> tuple[Path, dict[str, Any]]:
                    return _raw, {"prompt_sha256": hashlib.sha256(args[1].encode()).hexdigest()}

                normalized: list[Any] = [{"ok": True} for _ in range(6)]
                if mode == "output":
                    normalized[0] = ValueError("invalid date")
                with (
                    patch(
                        "sfr_enrichment_legacy.enrichment_fragments.frozen", return_value=manifest
                    ),
                    patch(
                        "sfr_enrichment_legacy.enrichment_fragments.access_stopped",
                        return_value=False,
                    ),
                    patch(
                        "sfr_enrichment_legacy.enrichment_fragments.run_pi", side_effect=glm
                    ) as g,
                    patch(
                        "sfr_enrichment_legacy.enrichment_fragments.execute", side_effect=sol
                    ) as s,
                    patch(
                        "sfr_enrichment_legacy.enrichment_fragments.normalized_provenance",
                        return_value={},
                    ),
                    patch(
                        "sfr_enrichment_legacy.enrichment_fragments.hydrate", side_effect=normalized
                    ),
                ):
                    result = run(root, 0)
                if mode in ("common", "provider_error"):
                    self.assertEqual(g.call_count, 1)
                    s.assert_not_called()
                    self.assertEqual(result["cumulative_reserved"], 30)
                    self.assertIn(
                        "differs" if mode == "common" else "unfinished", result["partial_reason"]
                    )
                else:
                    self.assertEqual((g.call_count, s.call_count), (3, 3))
                    self.assertEqual(result["cumulative_reserved"], 35)
                    self.assertEqual(result["stage_jobs_completed"], 5)
                    self.assertEqual(len(result["failures"]), 1)
                    self.assertEqual(
                        result["failures"][0]["phase"],
                        mode if mode == "runtime" else "output_validation",
                    )
                self.assertTrue((root / "stopped.json").exists())


if __name__ == "__main__":
    unittest.main()
