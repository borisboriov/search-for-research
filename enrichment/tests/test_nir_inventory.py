"""Synthetic metadata inventory regression tests; no project private archives are read."""

import copy
import hashlib
import json
import stat
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from sfr_enrichment.common import sha
from sfr_enrichment.nir_inventory import (
    PLAN_SCHEMA,
    build_inventory,
    candidate_identity_keys,
    canonical_document_url,
    canonical_email,
    canonical_identifier,
    make_lookup,
    overlap_reasons,
    validate_inventory,
    write_inventory,
)


class PriorInventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.tmp = Path(self.temporary.name)
        self.base = self.tmp / "experiments"
        self.root = self.base / "enrichment-synthetic"
        self.root.mkdir(parents=True)
        self.save(
            self.root / "sample.json",
            [
                {"id": "A123", "name": "Synthetic", "orcid": "0000-0000-0000-0001"},
                {"id": "A456", "name": "Synthetic"},
            ],
        )
        self.save(
            self.root / "collector.json",
            {
                "author_id": "A123",
                "items": [
                    {
                        "item_id": "contact_001",
                        "field": "email",
                        "value": "Example @ institute.invalid",
                        "status": "insufficient",
                    }
                ],
                "evidence_pool": {
                    "E0001": {
                        "url": "https://Institute.invalid/Doc#one",
                        "body_sha256": "a" * 64,
                        "text_sha256": "b" * 64,
                        "excerpt": "Synthetic evidence",
                    }
                },
            },
        )
        self.catalogue = self.tmp / "catalogue.json"
        self.save(
            self.catalogue,
            {
                "schema": "enrichment-storage-catalogue-v1",
                "at": "2026-10-11T00:00:00Z",
                "roots": [{"path": str(self.root)}, {"path": str(self.tmp / "old-log.txt")}],
            },
        )
        self.plan = {
            "schema": PLAN_SCHEMA,
            "scope": "Synthetic recorded targets and explicit evidence, no real SFR subjects",
            "catalogue": {"path": str(self.catalogue), "sha256": sha(self.catalogue)},
            "experiment_base": str(self.base),
            "metadata_byte_limit": 1024 * 1024,
            "extra_roots": [],
        }

    @staticmethod
    def save(path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False))

    def test_writer_materials_and_seals_preserve_independent_evidence(self) -> None:
        material = self.root / "v2/verifier-source-materials/evaluation-1/A123.json"
        excerpt = "Independent synthetic verifier evidence"
        self.save(
            material,
            {
                "author_id": "A123",
                "rules_version": "synthetic_complete_v2",
                "provenance": {"independent_search": True},
                "claim_verdicts": [
                    {
                        "claim_id": "contact_001",
                        "evidence": [
                            {
                                "url": "https://independent.invalid/evidence",
                                "excerpt": excerpt,
                            }
                        ],
                    }
                ],
            },
        )
        seal = self.root / "v2/verifier-materials-evaluation1-final.json"
        self.save(
            seal,
            {
                "writing_stopped": True,
                "files": [
                    {
                        "path": str(material.relative_to(self.root)),
                        "sha256": sha(material),
                    }
                ],
            },
        )
        inventory = build_inventory(self.plan)
        digest = hashlib.sha256(excerpt.encode()).hexdigest()
        self.assertIn(digest, inventory["lookup"]["document_sha256"]["excerpt"])
        self.assertIn("https://independent.invalid/evidence", inventory["lookup"]["document_urls"])
        self.assertNotIn(
            sha(material), {h for hs in inventory["lookup"]["document_sha256"].values() for h in hs}
        )
        checks = inventory["coverage"]["source_record_reference_checks"]
        self.assertEqual(checks[0]["status"], "resolved_exact_metadata")
        self.assertTrue(inventory["completeness"]["complete"])
        material.unlink()
        missing = build_inventory(self.plan)
        self.assertFalse(missing["completeness"]["complete"])
        self.assertTrue(
            any(
                g["kind"] == "unresolved_metadata_reference"
                for g in missing["completeness"]["gaps"]
            )
        )

    def test_derived_writer_families_and_keyed_targets_are_selected(self) -> None:
        for family in (
            "corpora",
            "tasks",
            "comparison-inputs/leg",
            "comparison-results/leg",
            "verification/A123",
            "normalized",
            "model-inputs",
            "results",
            "human-packets/annotator",
        ):
            self.save(
                self.root / family / "task.json",
                {
                    "author_id": "A123",
                    "sources": [
                        {"url": "https://writer.invalid/" + family, "text_sha256": "c" * 64}
                    ],
                    "prompt": "never @ prompt.invalid",
                },
            )
        self.save(
            self.root / "v2/collector-source-materials/defs.json",
            {
                "defs": {"A123": {"special": {"personal_contact": "keyed@writer.invalid"}}},
            },
        )
        self.save(
            self.root / "orcid/A123--synthetic.json",
            {
                "author_id": "A123",
                "method": "synthetic-derived",
                "fields": {},
                "orcid_status": "ok",
                "source": "https://orcid.invalid/public-record",
                "candidates": {
                    "links": [{"url": "https://profile.invalid/researcher"}],
                    "emails": [{"email": "public@writer.invalid"}],
                    "activities": {"email": "never@activity.invalid"},
                },
            },
        )
        self.save(
            self.root / "orcid/raw/A999.json", {"author_id": "A999", "email": "never@raw.invalid"}
        )
        inventory = build_inventory(self.plan)
        emails = {p["email"] for p in inventory["pairs"]}
        self.assertIn("keyed@writer.invalid", emails)
        self.assertIn("public@writer.invalid", emails)
        self.assertIn("https://orcid.invalid/public-record", inventory["lookup"]["document_urls"])
        self.assertIn("https://profile.invalid/researcher", inventory["lookup"]["document_urls"])
        self.assertFalse(any(address.startswith("never") for address in emails))
        self.assertIn("c" * 64, inventory["lookup"]["document_sha256"]["text"])
        self.assertEqual(
            inventory["coverage"]["writer_family_source_counts"]["derived_orcid_result"], 1
        )
        self.assertTrue(inventory["completeness"]["complete"])

    def test_writer_metadata_reference_closure_is_typed(self) -> None:
        corpus = self.root / "corpora/A123.json"
        self.save(corpus, {"author_id": "A123", "sources": []})
        self.save(
            self.root / "source-maps/A123.json",
            [
                {
                    "text_sha256": "d" * 64,
                    "copied_dependencies": {str(corpus): sha(corpus), "body.bin": "e" * 64},
                }
            ],
        )
        self.save(
            self.root / "groups/1/mapping.json",
            {
                "input-local": {
                    "author_id": "A123",
                    "original_input_path": str(corpus),
                    "original_input_sha256": sha(corpus),
                    "corpus_sha256": sha(corpus),
                }
            },
        )
        inventory = build_inventory(self.plan)
        self.assertTrue(inventory["completeness"]["complete"])
        self.assertEqual(len(inventory["coverage"]["source_record_reference_checks"]), 2)
        self.assertEqual(
            inventory["coverage"]["writer_metadata_hash_checks"][0]["status"],
            "resolved_exact_metadata_hash",
        )
        self.assertEqual(len(inventory["coverage"]["unread_dependency_file_receipts"]), 1)
        hashes = {h for hs in inventory["lookup"]["document_sha256"].values() for h in hs}
        self.assertNotIn("e" * 64, hashes)
        self.assertNotIn(sha(corpus), hashes)
        self.assertIn("d" * 64, hashes)

    def test_derived_orcid_schema_and_cap_fail_closed(self) -> None:
        target = self.root / "orcid/A123.json"
        self.save(target, {"author_id": "A123", "unexpected": "not a derived result"})
        inventory = build_inventory(self.plan)
        self.assertFalse(inventory["completeness"]["complete"])
        self.assertTrue(
            any(
                g["kind"] == "unsupported_derived_orcid_schema"
                for g in inventory["completeness"]["gaps"]
            )
        )
        self.plan["metadata_kind_byte_limits"] = {"arbitrary": 100}
        with self.assertRaisesRegex(ValueError, "bounded derived ORCID"):
            build_inventory(self.plan)

    def test_targets_partial_candidates_documents_and_provenance(self) -> None:
        inventory = build_inventory(self.plan)
        self.assertTrue(inventory["completeness"]["complete"])
        self.assertEqual(len(inventory["people"]), 2)
        self.assertEqual(len(inventory["pairs"]), 1)
        self.assertEqual(inventory["pairs"][0]["email"], "Example@institute.invalid")
        self.assertEqual(inventory["lookup"]["document_sha256"]["body"], ["a" * 64])
        self.assertEqual(inventory["lookup"]["document_sha256"]["text"], ["b" * 64])
        self.assertNotIn(
            sha(self.root / "collector.json"), inventory["lookup"]["document_sha256"]["body"]
        )
        self.assertTrue(all(p["provenance"] for p in inventory["people"]))
        validate_inventory(inventory)
        reasons = overlap_reasons(
            inventory,
            {
                "identity_keys": ["orcid:0000-0000-0000-0001"],
                "email": "Example@institute.invalid",
                "snapshot_sha256": ["b" * 64],
                "source_urls": ["https://institute.invalid/Doc#two"],
                "example_keys": [],
            },
        )
        self.assertIn("researcher_alias_overlap", reasons)
        self.assertIn("researcher_email_pair_overlap", reasons)
        self.assertIn("document_bytes_overlap:text", reasons)
        self.assertIn("document_url_overlap", reasons)

    def test_copies_merge_records_preserve_every_occurrence(self) -> None:
        second = self.base / "enrichment-replay"
        second.mkdir()
        for name in ("sample.json", "collector.json"):
            (second / name).write_bytes((self.root / name).read_bytes())
        inventory = build_inventory(self.plan)
        self.assertEqual(len(inventory["people"]), 2)
        self.assertEqual(len(inventory["pairs"]), 1)
        self.assertEqual(len(inventory["pairs"][0]["provenance"]), 2)
        self.assertEqual(len(inventory["coverage"]["roots"]), 2)
        self.assertTrue(
            any(r["discovery"] == "post_catalogue_or_extra" for r in inventory["coverage"]["roots"])
        )

    def test_casefold_is_conservative_not_mailbox_equivalence(self) -> None:
        inventory = build_inventory(self.plan)
        reasons = overlap_reasons(
            inventory, {"identity_keys": ["openalex:A123"], "email": "example@INSTITUTE.INVALID"}
        )
        self.assertIn("conservative_email_casefold_collision", reasons)
        self.assertNotIn("researcher_email_pair_overlap", reasons)
        self.assertNotEqual(
            canonical_email("Example@x.invalid"), canonical_email("example@x.invalid")
        )
        self.assertEqual(canonical_email(" e @ x.invalid "), "e@x.invalid")
        self.assertEqual(canonical_identifier("https://openalex.org/A123"), "openalex:A123")
        self.assertEqual(
            candidate_identity_keys(
                {
                    "identifiers": {"x": ["https://orcid.org/0000-0000-0000-0001"]},
                    "aliases": ["Synthetic name", "A123"],
                },
                "new-group",
            ),
            ["openalex:A123", "orcid:0000-0000-0000-0001"],
        )
        self.assertEqual(
            canonical_document_url("https://EXAMPLE.invalid/A?q=One#two"),
            "https://example.invalid/A?q=One",
        )

    def test_names_do_not_merge_and_sampling_frames_not_scanned(self) -> None:
        self.save(
            self.root / "catalogue-frame.jsonl", [{"id": "A999", "name": "Unused frame subject"}]
        )
        raw = self.root / "raw" / "page.json"
        self.save(raw, {"author_id": "A888", "email": "never@example.invalid"})
        inventory = build_inventory(self.plan)
        self.assertEqual(len(inventory["people"]), 2)
        self.assertNotIn("openalex:A999", inventory["lookup"]["identity_keys"])
        self.assertNotIn("openalex:A888", inventory["lookup"]["identity_keys"])
        self.assertGreater(
            inventory["coverage"]["statistics"]["raw_or_unselected_files_not_read"], 0
        )
        self.assertTrue(all(s["path"] != str(raw) for s in inventory["sources"]))

    def test_missing_experiment_blocks_but_missing_old_log_does_not(self) -> None:
        missing = self.base / "enrichment-missing"
        self.plan["extra_roots"] = [str(missing)]
        inventory = build_inventory(self.plan)
        self.assertFalse(inventory["completeness"]["complete"])
        self.assertTrue(
            any(
                g["kind"] == "missing_experiment_root" and g["path"] == str(missing.resolve())
                for g in inventory["completeness"]["gaps"]
            )
        )
        validate_inventory(inventory)
        inventory["completeness"]["complete"] = True
        with self.assertRaisesRegex(ValueError, "Completeness"):
            validate_inventory(inventory)

    def test_too_large_malformed_and_empty_exposure_metadata_are_gaps(self) -> None:
        for kind in ("too_large", "malformed", "empty"):
            with self.subTest(kind=kind):
                extra = self.base / ("enrichment-" + kind)
                extra.mkdir()
                (extra / "sample.json").write_text(
                    "x" * (1024 * 1024 + 1)
                    if kind == "too_large"
                    else "{bad"
                    if kind == "malformed"
                    else "[]"
                )
        inventory = build_inventory(self.plan)
        self.assertFalse(inventory["completeness"]["complete"])
        kinds = {g["kind"] for g in inventory["completeness"]["gaps"]}
        self.assertTrue(
            {"metadata_over_byte_limit", "unreadable_metadata", "no_identified_targets_in_metadata"}
            <= kinds
        )

    def test_source_changes_and_forged_projection_are_rejected(self) -> None:
        inventory = build_inventory(self.plan)
        forged = copy.deepcopy(inventory)
        forged["people"] = []
        forged["pairs"] = []
        with self.assertRaises(ValueError):
            validate_inventory(forged)
        forged["lookup"] = make_lookup(
            forged["people"], forged["pairs"], forged["documents"], forged["examples"]
        )
        with self.assertRaisesRegex(ValueError, "do not reproduce"):
            validate_inventory(forged)
        with self.assertRaisesRegex(ValueError, "producer inventory"):
            validate_inventory(
                {"schema": inventory["schema"], "lookup": {}, "completeness": {"complete": True}}
            )
        (self.root / "sample.json").write_text("[]")
        with self.assertRaisesRegex(ValueError, "source hash changed"):
            validate_inventory(inventory)

    def test_declared_cohort_coverage_and_linked_sidecar_closure(self) -> None:
        sidecar = self.root / "cache" / "source-receipt.json"
        self.save(sidecar, {"url": "https://sidecar.invalid/doc", "text_sha256": "c" * 64})
        collector_path = self.root / "collector.json"
        collector = json.loads(collector_path.read_text())
        collector["evidence_pool"]["E0001"].update(
            source_record_path=str(sidecar), source_record_sha256=sha(sidecar)
        )
        self.save(collector_path, collector)
        inventory = build_inventory(self.plan)
        root = inventory["coverage"]["roots"][0]
        self.assertEqual(root["uncovered_cohort_identity_keys"], [])
        self.assertEqual(len(root["expected_cohort_identity_keys"]), 3)
        checks = inventory["coverage"]["source_record_reference_checks"]
        self.assertEqual(checks[0]["status"], "resolved_exact_metadata")
        self.assertIn("c" * 64, inventory["lookup"]["document_sha256"]["text"])
        self.assertEqual(
            inventory["coverage"]["statistics"]["explicitly_referenced_metadata_files_read"], 1
        )
        sidecar.unlink()
        incomplete = build_inventory(self.plan)
        self.assertFalse(incomplete["completeness"]["complete"])
        self.assertTrue(
            any(
                g["kind"] == "unresolved_metadata_reference"
                for g in incomplete["completeness"]["gaps"]
            )
        )

    def test_literal_terminal_newline_is_not_repaired_model_data(self) -> None:
        source = self.root / "collector.json"
        source.write_bytes(source.read_bytes() + b"\\n")
        inventory = build_inventory(self.plan)
        self.assertTrue(inventory["completeness"]["complete"])
        self.assertTrue(
            any(
                s.get("parse_encoding") == "complete_json_with_literal_terminal_newline"
                for s in inventory["sources"]
            )
        )
        self.assertEqual(len(inventory["pairs"]), 1)
        source.write_bytes(source.read_bytes() + b"malformed")
        self.assertFalse(build_inventory(self.plan)["completeness"]["complete"])

    def test_structured_historical_raw_rows_plural_contacts_and_publication_refs(self) -> None:
        self.save(
            self.root / "contacts_sfr5.json",
            {
                "sample_size": 1,
                "manual_sample": [{"author_id": "A789"}],
                "raw": [
                    {
                        "author_id": "A789",
                        "name": "Synthetic historical target",
                        "orcid_emails": ["old@past.invalid"],
                        "crossref_emails": ["other@past.invalid"],
                        "dois": ["10.1234/synthetic"],
                    }
                ],
            },
        )
        inventory = build_inventory(self.plan)
        self.assertTrue(inventory["completeness"]["complete"])
        self.assertIn("openalex:A789", inventory["lookup"]["identity_keys"])
        self.assertEqual(len(inventory["pairs"]), 3)
        self.assertEqual(
            inventory["publication_references"][0]["role"],
            "publication_reference_not_document_snapshot",
        )
        self.assertFalse(any(d["url"] and "doi.org" in d["url"] for d in inventory["documents"]))
        bad = json.loads((self.root / "contacts_sfr5.json").read_text())
        bad["sample_size"] = 2
        self.save(self.root / "contacts_sfr5.json", bad)
        self.assertFalse(build_inventory(self.plan)["completeness"]["complete"])

    def test_cohort_snapshot_hashes_must_resolve(self) -> None:
        self.save(self.root / "manifest.json", {"sample_sha256": sha(self.root / "sample.json")})
        inventory = build_inventory(self.plan)
        self.assertEqual(
            inventory["coverage"]["cohort_snapshot_hash_checks"][0]["status"],
            "resolved_exact_cohort_snapshot",
        )
        self.save(self.root / "manifest.json", {"sample_sha256": "f" * 64})
        self.assertFalse(build_inventory(self.plan)["completeness"]["complete"])

    def test_readable_metadata_does_not_invent_unrecorded_historical_contact_details(self) -> None:
        self.save(
            self.root / "contacts_manual_sfr5.json",
            {
                "checked": 1,
                "rows": [
                    {
                        "author_id": "A123",
                        "email_published": True,
                        "note": "The historical observation did not retain address or page",
                    }
                ],
            },
        )
        inventory = build_inventory(self.plan)
        self.assertTrue(inventory["coverage"]["metadata_scope_complete"])
        self.assertFalse(inventory["completeness"]["prior_details_complete"])
        self.assertFalse(inventory["completeness"]["complete"])
        gaps = [
            g
            for g in inventory["completeness"]["gaps"]
            if g["kind"] == "historical_capture_detail_missing"
        ]
        self.assertEqual(gaps[0]["selector"], "$.rows[0]")
        self.assertEqual(gaps[0]["missing_fields"], ["email_literal", "document_locator"])
        self.assertIn("openalex:A123", inventory["lookup"]["identity_keys"])
        validate_inventory(inventory)
        inventory["completeness"]["complete"] = True
        with self.assertRaisesRegex(ValueError, "Completeness"):
            validate_inventory(inventory)

    def test_explicit_synthetic_layer_has_no_invented_real_identifiers(self) -> None:
        fixture = self.tmp / "training-fixture"
        self.save(
            fixture / "selection.json",
            [
                {
                    "group_id": "fake-one",
                    "profile": {"name": "Fictional", "identifiers": {"synthetic": "one"}},
                    "email": "fake@training.invalid",
                    "evidence": [
                        {"url": "https://training.invalid/demo", "excerpt": "A synthetic quote"}
                    ],
                }
            ],
        )
        self.plan["development_roots"] = [str(fixture)]
        text = fixture / "source.txt"
        text.write_text("A synthetic quote")
        self.plan["development_documents"] = [
            {
                "path": str(text),
                "sha256": sha(text),
                "representation": "text",
                "version": "synthetic-test",
            }
        ]
        inventory = build_inventory(self.plan)
        self.assertTrue(inventory["completeness"]["complete"])
        synthetic = [p for p in inventory["people"] if p["person_key"].startswith("synthetic:")]
        self.assertEqual(len(synthetic), 1)
        self.assertEqual(synthetic[0]["identity_keys"], [])
        self.assertIn(sha(text), inventory["lookup"]["document_sha256"]["text"])
        self.assertIn(
            "evidence_excerpt_overlap:excerpt",
            overlap_reasons(
                inventory,
                {
                    "identity_keys": ["openalex:A9999"],
                    "email": "new@new.invalid",
                    "excerpt_sha256": [hashlib.sha256(text.read_bytes()).hexdigest()],
                },
            ),
        )

    def test_thin_legacy_request_metadata_is_read_without_responses_or_transport_origins(
        self,
    ) -> None:
        directory = self.root / "runs" / "A123" / "pi_verifier" / "pi"
        self.save(
            directory / "0001-mcp-request.json",
            {
                "server": "tool-server",
                "message": {
                    "method": "tools/call",
                    "params": {
                        "name": "open",
                        "arguments": {
                            "location": "https://legacy.invalid/visited",
                            "search_query": "A query mentioning https://query.invalid/not-a-visit",
                        },
                    },
                },
            },
        )
        self.save(
            directory / "0002-http.json",
            {"origin": "https://transport.invalid", "pathname": "/mcp", "status": 200},
        )
        self.save(
            directory / "0003-mcp-response.json",
            {"author_id": "A99999", "email": "not-mined@response.invalid"},
        )
        inventory = build_inventory(self.plan)
        self.assertIn("https://legacy.invalid/visited", inventory["lookup"]["document_urls"])
        requested = [
            d for d in inventory["documents"] if d["url"] == "https://legacy.invalid/visited"
        ]
        self.assertEqual(requested[0]["representation"], "requested_url")
        self.assertIsNone(requested[0]["sha256"])
        self.assertNotIn("https://query.invalid/not-a-visit", inventory["lookup"]["document_urls"])
        self.assertNotIn("https://transport.invalid", inventory["lookup"]["document_urls"])
        self.assertNotIn("openalex:A99999", inventory["lookup"]["identity_keys"])
        self.assertTrue(any(s["kind"] == "source_request_metadata" for s in inventory["sources"]))
        self.assertIsNone(canonical_document_url("https://user:placeholder@auth.invalid/doc"))
        self.assertIsNone(canonical_document_url("https://:placeholder@auth.invalid/doc"))
        self.assertIsNone(
            canonical_document_url("https://auth.invalid/doc?access_token=placeholder")
        )

    def test_saved_derivative_private_immutable_and_reproducible(self) -> None:
        plan_path = self.tmp / "plan.json"
        self.save(plan_path, self.plan)
        output = self.tmp / "private-inventory"
        result = write_inventory(plan_path, output)
        self.assertTrue(result.is_file())
        self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((output / "inventory.json").stat().st_mode), 0o600)
        inventory = json.loads((output / "inventory.json").read_text())
        validate_inventory(inventory)
        proof = json.loads(result.read_text())
        self.assertEqual(
            proof["inventory_sha256"],
            hashlib.sha256((output / "inventory.json").read_bytes()).hexdigest(),
        )
        with self.assertRaises(FileExistsError):
            write_inventory(plan_path, output)


if __name__ == "__main__":
    unittest.main()
