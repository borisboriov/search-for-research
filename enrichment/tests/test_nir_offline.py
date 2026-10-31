"""Synthetic preparation regressions; these cases are not SFR pilot observations."""

import hashlib
import json
import stat
import subprocess
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

from sfr_enrichment.batch import encoded
from sfr_enrichment.common import read, sha, write_new
from sfr_enrichment.nir import (
    DIAGNOSTIC_STATUS,
    adjudicate,
    analyze,
    arm_metrics,
    checked,
    compose,
    export,
    freeze,
    import_human,
    import_model,
    import_native,
    main,
    paired_bootstrap,
    prepare_model,
    prepared_request,
)
from sfr_enrichment.nir_inventory import build_inventory, make_lookup


class NirOfflineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.tmp = Path(self.temporary.name)
        self.root = self.tmp / "private"
        self.source = self.tmp / "source.txt"
        self.source.write_text(
            "Synthetic Researcher, example@institute.invalid. Laboratory office."
        )
        self.selection = self.tmp / "selection.json"
        self.cases = [
            {
                "case_id": f"c{i}",
                "group_id": "g1" if i < 3 else f"g{i}",
                "pair_id": f"p{i}",
                "example_ids": [f"e{i}"],
                "profile": {"name": "Synthetic Researcher", "identifiers": {"synthetic": str(i)}},
                "email": f"example{i}@institute.invalid",
                "evidence": [
                    {
                        "source_id": "s1",
                        "url": "https://institute.invalid/source",
                        "captured_at": "2026-10-31T10:00:00+03:00",
                        "content_date": None,
                        "source_path": str(self.source),
                        "excerpt": "Laboratory office.",
                    }
                ],
            }
            for i in range(1, 5)
        ]
        write_new(self.selection, self.cases)
        inventory = self.tmp / "previous-inventory.json"
        write_new(inventory, {"warning": "Synthetic previous-use inventory only"})
        self.exclusions = self.tmp / "exclusions.json"
        write_new(
            self.exclusions,
            {
                "complete_prior_use_inventory": True,
                "inventory_sources": [{"path": str(inventory), "sha256": sha(inventory)}],
                "group_ids": ["previous_person"],
                "pair_ids": ["previous_pair"],
                "example_ids": ["previous_example"],
            },
        )
        self.protocol = self.tmp / "protocol.json"
        write_new(
            self.protocol,
            {
                "rubric": "Synthetic neutral rubric; supported/refuted/insufficient",
                "common_examples": "Only synthetic examples, excluded from a future pilot.",
                "instructions_B": "Strong verdict: label/reason/source_ids; identity permitted.",
                "instructions_C": "identity/object_relation/reason/source_ids; same entity anchor.",
                "model": "synthetic-model",
                "effort": "synthetic-effort",
                "generation": {},
                "code_revision": "synthetic-revision",
                "runtime_version": "synthetic-runtime",
                "limits": {"model_calls": 0, "http_calls": 0},
            },
        )
        freeze(self.root, self.selection, self.exclusions, self.protocol, development_only=True)

    def full_prior_inventory(
        self,
        *,
        representation: str = "body",
        document_hash: str | None = None,
        incomplete: bool = False,
        capture_gaps: int = 0,
    ) -> tuple[Path, Path]:
        sequence = len(list(self.tmp.glob("prior-experiments-*")))
        base = self.tmp / f"prior-experiments-{sequence}"
        old_root = base / "enrichment-synthetic"
        old_root.mkdir(parents=True)
        write_new(
            old_root / "sample.json",
            [
                {"id": "A123", "orcid": "0000-0000-0000-0001"},
                {"id": "A456", "orcid": "0000-0000-0000-001X"},
            ],
        )
        old_metadata = old_root / "collector.json"
        write_new(
            old_metadata,
            {
                "author_id": "A123",
                "items": [
                    {"field": "email", "value": "old@example.invalid", "item_id": "old-item"}
                ],
                "evidence_pool": {
                    "old-evidence": {
                        "url": "https://archive.invalid/paper",
                        representation + "_sha256": document_hash
                        or hashlib.sha256(b"Old synthetic text").hexdigest(),
                        "excerpt": "Old synthetic excerpt",
                    }
                },
            },
        )
        if capture_gaps:
            rows: list[dict[str, Any]] = [{"author_id": f"A60{index}"} for index in range(11)]
            for index in (6, 9, 10)[:capture_gaps]:
                rows[index] = {"author_id": f"A60{index}", "email_published": True}
            write_new(old_root / "contacts_manual_sfr5.json", {"rows": rows})
        catalogue = self.tmp / f"catalogue-{sequence}.json"
        references = [{"path": str(old_root)}]
        if incomplete:
            references.append({"path": str(base / "enrichment-missing")})
        write_new(
            catalogue,
            {
                "schema": "enrichment-storage-catalogue-v1",
                "at": "2026-10-31T00:00:00+03:00",
                "roots": references,
            },
        )
        inventory = build_inventory(
            {
                "schema": "nir_prior_inventory_plan_v1",
                "scope": "Fixed synthetic metadata scope",
                "catalogue": {"path": str(catalogue), "sha256": sha(catalogue)},
                "experiment_base": str(base),
                "metadata_byte_limit": 8388608,
                "extra_roots": [],
            }
        )
        self.assertEqual(inventory["completeness"]["complete"], not (incomplete or capture_gaps))
        inventory_path = self.tmp / f"prior-inventory-{sequence}.json"
        write_new(inventory_path, inventory)
        return inventory_path, old_metadata

    def diagnostic_decision(self, inventory: Path, selection: Path) -> Path:
        old = read(inventory)
        path = self.tmp / f"decision-{len(list(self.tmp.glob('decision-*.json')))}.json"
        write_new(
            path,
            {
                "schema": "nir_diagnostic_decision_v1",
                "purpose": "diagnostic_pilot_not_holdout",
                "planned_n": 30,
                "maximum_n": 30,
                "one_pair_per_person": True,
                "advisor_agreement": "preliminary",
                "authorization": {
                    "authorized_by": "Synthetic owner",
                    "authorized_at": "2026-10-31T23:00:00+03:00",
                    "reference": "Synthetic test authorization only",
                    "scope": "diagnostic_30_pairs",
                },
                "inventory_sha256": sha(inventory),
                "selection_sha256": sha(selection),
                "protocol_sha256": sha(self.protocol),
                "accepted_blocking_gaps": [
                    gap for gap in old["completeness"]["gaps"] if gap["blocking"]
                ],
                "accepted_capture_limits": old["coverage"]["historical_capture_limits"],
                "limitation_acknowledged": True,
            },
        )
        return path

    def real_selection(
        self, *, profile: dict[str, Any] | None = None, source_url: str | None = None
    ) -> Path:
        rows = read(self.selection)[:1]
        rows[0]["profile"] = profile or {
            "name": "Synthetic new target",
            "identifiers": {"openalex": "https://openalex.org/A900"},
        }
        if source_url is not None:
            rows[0]["evidence"][0]["url"] = source_url
        path = self.tmp / f"real-selection-{len(list(self.tmp.glob('real-selection-*.json')))}.json"
        write_new(path, rows)
        return path

    def humans(self, annotator: str, labels: list[str | None]) -> Path:
        packet = export(self.root, annotator)
        value = read(packet.parent / "answers-template.json")
        value.update(
            reviewed_at="2026-10-31T11:00:00+03:00", minutes=8.5, actual_human_attestation=True
        )
        value["answers"] = [
            {
                "case_id": f"c{i}",
                "status": "ok" if label is not None else "technical_skip",
                "label": label,
                "reason": "Synthetic answer only",
                "source_ids": ["s1"],
            }
            for i, label in enumerate(labels, 1)
        ]
        path = self.tmp / f"answers-{annotator}.json"
        write_new(path, value)
        return import_human(self.root, path, "initial")

    def models(self, arm: str, labels: list[str | None]) -> Path:
        manifest, _, protocol = checked(self.root)
        value = {
            "schema": "nir_model_answers_v1",
            "arm": arm,
            "manifest_sha256": sha(self.root / "manifest.json"),
            "cases_sha256": manifest["cases_sha256"],
            "protocol_sha256": manifest["protocol_sha256"],
            "prompt_sha256": manifest["prompt_sha256"][arm],
            **{
                k: protocol[k]
                for k in ("model", "effort", "generation", "code_revision", "runtime_version")
            },
            "results": [],
        }
        for i, label in enumerate(labels, 1):
            response = (
                {"label": label}
                if arm == "B"
                else {"identity": "supported", "object_relation": label}
            )
            value["results"].append(
                {
                    "case_id": f"c{i}",
                    "case_input_sha256": manifest["case_input_sha256"][f"c{i}"],
                    "status": "ok" if label else "technical_skip",
                    "raw_response": json.dumps(
                        response | {"reason": "MODEL_SECRET", "source_ids": ["s1"]}
                    ),
                    "error": "Synthetic technical failure" if not label else None,
                    "started_at": "2026-10-31T10:30:00+03:00",
                    "latency_seconds": 2.0,
                    "cost_usd": None,
                    "input_tokens": 100,
                    "output_tokens": 10,
                    "observed_model": None,
                    "observed_effort": None,
                    "receipt": None,
                }
            )
        path = self.tmp / f"model-{arm}.json"
        write_new(path, value)
        return import_model(self.root, path, "initial")

    def native_fixture(self, request_id: str) -> Path:
        request = prepared_request(self.root, request_id)
        directory = self.tmp / ("native-" + request_id)
        directory.mkdir()
        for source, target in (
            ("prompt_path", "prompt.txt"),
            ("output_schema_path", "schema.json"),
            ("system_prompt_path", "instructions.txt"),
        ):
            (directory / target).write_bytes((self.root / request[source]).read_bytes())
        response = (
            {"label": "supported"}
            if request["arm"] == "B"
            else {"identity": "supported", "object_relation": "supported"}
        )
        write_new(
            directory / "raw-result.json",
            response | {"reason": "Synthetic only", "source_ids": ["s1"]},
        )
        usage = {"input_tokens": 12, "output_tokens": 3, "cached_input_tokens": 5}
        events = [
            {"type": "thread.started", "thread_id": "synthetic-thread"},
            {"type": "turn.completed", "usage": usage},
        ]
        (directory / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events))
        write_new(
            directory / "started.json",
            {
                "started_at_epoch": 1793440800.0,
                "prompt_sha256": request["prompt_sha256"],
                "requested_config": request["native_kwargs"]["required_config"],
            },
        )
        write_new(directory / "finished.json", {"finished_at_epoch": 1793440802.5, "exit_code": 0})
        write_new(
            directory / "receipt.json",
            {
                "raw_result_sha256": sha(directory / "raw-result.json"),
                "events_sha256": sha(directory / "events.jsonl"),
                "tokens": usage,
                "prompt_sha256": request["prompt_sha256"],
                "tool_calls": 0,
                "wall_elapsed_seconds": 2.5,
                "cost_usd": None,
                "model": None,
                "effort": None,
                "requested_model": request["native_kwargs"]["model"],
                "requested_effort": request["native_kwargs"]["effort"],
                "runtime_status": "runtime_not_exposed",
            },
        )
        rendered = [
            {
                "type": "message",
                "role": role,
                "content": [{"type": "input_text", "text": (directory / name).read_text()}],
            }
            for role, name in (("developer", "instructions.txt"), ("user", "prompt.txt"))
        ]
        render_bytes = encoded(rendered)
        render_path = directory / f"isolation-stdout-{hashlib.sha256(render_bytes).hexdigest()}.bin"
        render_path.write_bytes(render_bytes)
        write_new(
            directory / "isolation-probe.json",
            {
                "instruction_delivery": "rendered_instruction_and_exact_final_user",
                "instruction_sha256": request["system_prompt_sha256"],
                "user_prompt_sha256": request["prompt_sha256"],
                "stdout_path": str(render_path),
                "stdout_sha256": sha(render_path),
            },
        )
        return directory

    def test_preparation_has_balanced_order_exact_roles_and_schema_without_transport(self) -> None:
        with patch("subprocess.run") as transport:
            prepared = read(prepare_model(self.root, seed=154))
            transport.assert_not_called()
        self.assertEqual(len(prepared["order"]), 8)
        self.assertEqual(sum(x.endswith("-B") for x in prepared["order"][::2]), 2)
        self.assertFalse(prepared["launch_authorized"])
        b, c = (prepared_request(self.root, "c1-" + arm) for arm in ("B", "C"))
        self.assertEqual(b["system_prompt_sha256"], c["system_prompt_sha256"])
        self.assertEqual(b["case_input_sha256"], c["case_input_sha256"])
        self.assertNotEqual(b["prompt_sha256"], c["prompt_sha256"])
        self.assertIn("label", read(self.root / b["output_schema_path"])["required"])
        self.assertIn("identity", read(self.root / c["output_schema_path"])["required"])
        self.assertNotIn("max_output_tokens", b["native_kwargs"])
        self.assertIsNone(b["deadline_epoch"])
        self.assertTrue(b["requires_existing_isolation_probe"])
        other_root = self.tmp / "replicated"
        freeze(other_root, self.selection, self.exclusions, self.protocol, development_only=True)
        self.assertEqual(prepared["order"], read(prepare_model(other_root, seed=154))["order"])

    def test_native_normalization_keeps_unknown_model_cost_and_actual_usage(self) -> None:
        prepare_model(self.root)
        directory = self.native_fixture("c1-C")
        with patch("subprocess.run") as transport:
            imported = import_native(self.root, "c1-C", directory, "native1")
            transport.assert_not_called()
        result = read(imported)["results"][0]
        self.assertEqual(result["label"], "supported")
        self.assertEqual((result["input_tokens"], result["output_tokens"]), (12, 3))
        self.assertEqual(result["latency_seconds"], 2.5)
        self.assertIsNone(result["observed_model"])
        self.assertIsNone(result["observed_effort"])
        self.assertIsNone(result["cost_usd"])
        saved = self.root / "native-imports" / "native1" / "native" / "receipt.json"
        self.assertEqual(sha(saved), sha(directory / "receipt.json"))

    def test_native_raw_hash_case_and_schema_tampering_are_rejected(self) -> None:
        prepare_model(self.root)
        directory = self.native_fixture("c1-B")
        with self.assertRaisesRegex(ValueError, "case/arm"):
            import_native(self.root, "c2-B", directory, "wrong-case")
        original = (directory / "schema.json").read_bytes()
        (directory / "schema.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "prompt/schema"):
            import_native(self.root, "c1-B", directory, "wrong-schema")
        (directory / "schema.json").write_bytes(original)
        (directory / "raw-result.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "raw hash"):
            import_native(self.root, "c1-B", directory, "wrong-raw")

    def test_native_requires_original_delivery_proof_not_only_claimed_status(self) -> None:
        prepare_model(self.root)
        directory = self.native_fixture("c1-B")
        proof = read(directory / "isolation-probe.json")
        render = Path(proof["stdout_path"])
        render.write_bytes(
            encoded(
                [
                    {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": "wrong prompt"}],
                    }
                ]
            )
        )
        proof["stdout_sha256"] = sha(render)
        render.rename(directory / f"isolation-stdout-{proof['stdout_sha256']}.bin")
        (directory / "isolation-probe.json").write_bytes(encoded(proof))
        with self.assertRaisesRegex(ValueError, "render не доставляет"):
            import_native(self.root, "c1-B", directory, "wrong-delivery")

    def test_adapter_accepts_actual_native_execute_receipt_with_mocked_transport(self) -> None:
        from sfr_enrichment.native import execute

        protocol = read(self.protocol)
        protocol.update(model="gpt-6.1-sol", effort="high", generation={"max_output_tokens": 4096})
        protocol_path = self.tmp / "native-protocol.json"
        write_new(protocol_path, protocol)
        root = self.tmp / "native-contract-root"
        freeze(root, self.selection, self.exclusions, protocol_path, development_only=True)
        prepare_model(root)
        request = prepared_request(root, "c1-B")
        common, prompt = (
            (root / request[key]).read_text() for key in ("system_prompt_path", "prompt_path")
        )
        rendered = [
            {"type": "message", "role": role, "content": [{"type": "input_text", "text": value}]}
            for role, value in (("developer", common), ("user", prompt))
        ]

        def fake_render(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
            self.assertEqual(command[1:3], ["debug", "prompt-input"])
            return subprocess.CompletedProcess(command, 0, stdout=encoded(rendered), stderr=b"")

        def fake_execution(
            command: list[str], content: bytes, output: Any, errors: Any, timeout: float, cap: int
        ) -> subprocess.CompletedProcess[bytes]:
            self.assertEqual(command[1], "exec")
            self.assertEqual(content, prompt.encode())
            self.assertEqual(cap, 65536)
            raw_path = Path(command[command.index("--output-last-message") + 1])
            write_new(
                raw_path,
                {
                    "label": "supported",
                    "reason": "Synthetic contract response",
                    "source_ids": ["s1"],
                },
            )
            events = [
                {"type": "thread.started", "thread_id": "synthetic-native-contract"},
                {"type": "turn.started"},
                {"type": "turn.completed", "usage": {"input_tokens": 21, "output_tokens": 4}},
            ]
            output.write(b"".join((json.dumps(e) + "\n").encode() for e in events))
            return subprocess.CompletedProcess(command, 0)

        directory = self.tmp / "actual-native-mocked"
        empty_cwd = self.tmp / "empty-cwd"
        empty_cwd.mkdir()
        with (
            patch("sfr_enrichment.native.subprocess.run", side_effect=fake_render) as render,
            patch(
                "sfr_enrichment.native.bounded_output_run", side_effect=fake_execution
            ) as execution,
        ):
            execute(
                directory,
                prompt,
                read(root / request["output_schema_path"]),
                empty_cwd,
                system_prompt=common,
                deadline_epoch=time.time() + 3600,
                **request["native_kwargs"],
            )
            self.assertEqual((render.call_count, execution.call_count), (1, 1))
        imported = read(import_native(root, "c1-B", directory, "native-contract"))
        self.assertEqual(imported["results"][0]["input_tokens"], 21)
        self.assertIsNone(imported["results"][0]["observed_model"])
        self.assertEqual(imported["results"][0]["label"], "supported")

    def test_export_is_neutral_even_after_model_results_exist(self) -> None:
        self.models("B", ["supported"] * 4)
        packet = export(self.root, "adelina")
        text = "\n".join(p.read_text() for p in packet.parent.rglob("*.json"))
        self.assertNotIn("MODEL_SECRET", text)
        self.assertNotIn("instructions_B", text)
        self.assertNotIn("model-records", text)
        self.assertNotIn("sasha", text)
        self.assertEqual(read(packet)["cases"], read(self.root / "cases.json"))
        self.assertFalse(read(packet.parent / "answers-template.json")["actual_human_attestation"])
        with self.assertRaises(ValueError):
            import_human(self.root, packet.parent / "answers-template.json", "not_real")

    def test_reused_person_pair_and_example_are_all_excluded(self) -> None:
        for key, value in (
            ("group_id", "previous_person"),
            ("pair_id", "previous_pair"),
            ("example_ids", ["previous_example"]),
        ):
            with self.subTest(key=key):
                rows = read(self.selection)
                rows[0][key] = value
                path = self.tmp / f"excluded-{key}.json"
                write_new(path, rows)
                with self.assertRaisesRegex(ValueError, "Прежний"):
                    freeze(
                        self.tmp / f"root-{key}",
                        path,
                        self.exclusions,
                        self.protocol,
                        development_only=True,
                    )

    def test_legacy_inventory_needs_explicit_development_and_cannot_claim_holdout(self) -> None:
        with self.assertRaisesRegex(ValueError, "producer registry"):
            freeze(self.tmp / "legacy-default", self.selection, self.exclusions, self.protocol)
        self.assertEqual(
            read(self.root / "manifest.json")["holdout_status"], "development_only_not_holdout"
        )
        report = read(analyze(self.root, self.tmp / "development-analysis.json", resamples=5))
        self.assertEqual(report["holdout_status"], "development_only_not_holdout")

    def test_lightweight_lookup_projection_cannot_replace_a_full_producer_inventory(self) -> None:
        projection = self.tmp / "lookup-only.json"
        write_new(
            projection,
            {
                "schema": "nir_prior_inventory_v1",
                "completeness": {"complete": True, "gaps": []},
                "lookup": {
                    "identity_keys": [],
                    "pair_keys": [],
                    "casefold_pair_keys": [],
                    "document_urls": [],
                    "document_sha256": {"body": [], "decoded": [], "text": []},
                    "example_keys": [],
                },
            },
        )
        target = self.tmp / "projection-bypass"
        with self.assertRaises(ValueError):
            freeze(target, self.selection, projection, self.protocol)
        self.assertFalse((target / "manifest.json").exists())

    def test_full_producer_allows_only_recorded_overlap_claim_for_new_declared_identity(
        self,
    ) -> None:
        inventory, _ = self.full_prior_inventory()
        target = self.tmp / "guarded-new-frame"
        path = freeze(target, self.real_selection(), inventory, self.protocol)
        manifest = read(path)
        self.assertEqual(manifest["holdout_status"], "recorded_prior_overlap_checked")
        self.assertIn("new-frame identity/coherence requires verification", manifest["warning"])
        self.assertFalse(manifest["launch_authorized"])

    def test_diagnostic_shortfall_is_explicit_and_exports_remain_blind(self) -> None:
        inventory, _ = self.full_prior_inventory(capture_gaps=2)
        selection = self.real_selection()
        decision = self.diagnostic_decision(inventory, selection)
        root = self.tmp / "diagnostic"
        manifest = read(
            freeze(root, selection, inventory, self.protocol, diagnostic_decision=decision)
        )
        self.assertEqual(manifest["holdout_status"], DIAGNOSTIC_STATUS)
        self.assertFalse(read(root / "exclusions.json")["completeness"]["complete"])
        self.assertEqual(sha(root / "exclusions.json"), sha(inventory))
        self.assertEqual(sha(root / "protocol.json"), sha(self.protocol))
        self.assertEqual(manifest["diagnostic_scope"]["planned_n"], 30)
        self.assertEqual(manifest["diagnostic_scope"]["actual_n"], 1)
        self.assertEqual(manifest["diagnostic_scope"]["sample_status"], "shortfall")
        for annotator in ("adelina", "sasha"):
            packet = read(export(root, annotator))
            self.assertEqual(packet["holdout_status"], DIAGNOSTIC_STATUS)
            self.assertEqual(packet["diagnostic_scope"], manifest["diagnostic_scope"])
            serialized = json.dumps(packet)
            for forbidden in ("accepted_capture_limits", "instructions_C", "authorization", "A606"):
                self.assertNotIn(forbidden, serialized)
        prepared = read(prepare_model(root))
        self.assertEqual(len(prepared["requests"]), 2)
        self.assertEqual(prepared["diagnostic_scope"], manifest["diagnostic_scope"])
        for request_id in prepared["order"]:
            request = prepared_request(root, request_id)
            self.assertFalse(request["launch_authorized"])
            self.assertEqual(request["diagnostic_scope"], manifest["diagnostic_scope"])
        report = read(analyze(root, self.tmp / "diagnostic-analysis.json", resamples=5))
        self.assertEqual(report["holdout_status"], DIAGNOSTIC_STATUS)
        self.assertEqual(report["diagnostic_scope"], manifest["diagnostic_scope"])
        self.assertEqual(report["human_status_counts"], {"human_missing": 1})
        self.assertIsNone(report["intention_to_process"]["B"]["R_resolved"])

    def test_diagnostic_does_not_weaken_ordinary_or_legacy_guards(self) -> None:
        inventory, _ = self.full_prior_inventory(capture_gaps=2)
        selection = self.real_selection()
        decision = self.diagnostic_decision(inventory, selection)
        with self.assertRaisesRegex(ValueError, "Неполный реестр"):
            freeze(self.tmp / "ordinary-capture", selection, inventory, self.protocol)
        with self.assertRaisesRegex(ValueError, "несовместима"):
            freeze(
                self.tmp / "diagnostic-development",
                selection,
                inventory,
                self.protocol,
                diagnostic_decision=decision,
                development_only=True,
            )
        with self.assertRaisesRegex(ValueError, "producer registry"):
            freeze(
                self.tmp / "diagnostic-legacy",
                selection,
                self.exclusions,
                self.protocol,
                diagnostic_decision=decision,
            )

    def test_diagnostic_human_exports_import_and_analyze_end_to_end(self) -> None:
        inventory, _ = self.full_prior_inventory(capture_gaps=2)
        rows = read(self.selection)[:3]
        for index, row in enumerate(rows):
            row["group_id"] = f"new_group{index}"
            row["profile"] = {"name": "Synthetic new target", "id": f"A90{index}"}
        selection = self.tmp / "diagnostic-human-roundtrip.json"
        write_new(selection, rows)
        self.root = self.tmp / "diagnostic-human-roundtrip"
        manifest = read(
            freeze(
                self.root,
                selection,
                inventory,
                self.protocol,
                diagnostic_decision=self.diagnostic_decision(inventory, selection),
            )
        )
        labels: list[str | None] = ["supported", "refuted", "insufficient"]
        for annotator in ("adelina", "sasha"):
            record = read(self.humans(annotator, labels))
            self.assertEqual(record["answers"]["annotator"], annotator)
            self.assertEqual(record["answers"]["answers"][1]["label"], "refuted")
        self.models("B", ["supported", "supported", "supported"])
        self.models("C", labels)
        report = read(analyze(self.root, self.tmp / "diagnostic-human-analysis.json", resamples=5))
        self.assertEqual(report["holdout_status"], DIAGNOSTIC_STATUS)
        self.assertEqual(report["diagnostic_scope"], manifest["diagnostic_scope"])
        self.assertEqual(report["human_status_counts"], {"agreement": 3})
        self.assertEqual(report["unknown_human_case_ids"], [])
        self.assertEqual(report["intention_to_process"]["B"]["R_resolved"], 2 / 3)
        self.assertEqual(report["intention_to_process"]["C"]["R_resolved"], 0)

    def test_diagnostic_human_import_rejects_changed_scope_even_with_updated_packet_hash(
        self,
    ) -> None:
        inventory, _ = self.full_prior_inventory(capture_gaps=2)
        selection = self.real_selection()
        root = self.tmp / "diagnostic-human-scope-tamper"
        freeze(
            root,
            selection,
            inventory,
            self.protocol,
            diagnostic_decision=self.diagnostic_decision(inventory, selection),
        )
        packet_path = export(root, "adelina")
        packet = read(packet_path)
        packet["holdout_status"] = "recorded_prior_overlap_checked"
        packet["diagnostic_scope"]["sample_status"] = "complete_planned_count"
        packet_path.write_bytes(encoded(packet))
        answers = read(packet_path.parent / "answers-template.json")
        answers["packet_sha256"] = sha(packet_path)
        answers_path = self.tmp / "diagnostic-human-tampered-answer.json"
        write_new(answers_path, answers)
        with self.assertRaisesRegex(ValueError, "Нейтральный пакет изменён"):
            import_human(root, answers_path, "initial")

    def test_diagnostic_rejects_other_gaps_and_changed_provenance(self) -> None:
        selection = self.real_selection()
        cases: tuple[dict[str, Any], ...] = (
            {"capture_gaps": 3},
            {"capture_gaps": 1},
            {"capture_gaps": 2, "incomplete": True},
            {},
        )
        for index, arguments in enumerate(cases):
            inventory, _ = self.full_prior_inventory(**arguments)
            decision = self.diagnostic_decision(inventory, selection)
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                freeze(
                    self.tmp / f"diagnostic-wrong-gaps-{index}",
                    selection,
                    inventory,
                    self.protocol,
                    diagnostic_decision=decision,
                )
        inventory, metadata = self.full_prior_inventory(capture_gaps=2)
        decision = self.diagnostic_decision(inventory, selection)
        metadata.write_bytes(metadata.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "hash changed"):
            freeze(
                self.tmp / "diagnostic-changed-provenance",
                selection,
                inventory,
                self.protocol,
                diagnostic_decision=decision,
            )

    def test_diagnostic_decision_binds_exact_inputs_gaps_and_preliminary_scope(self) -> None:
        inventory, _ = self.full_prior_inventory(capture_gaps=2)
        selection = self.real_selection()
        good = read(self.diagnostic_decision(inventory, selection))
        changes = [
            {"inventory_sha256": "0" * 64},
            {"selection_sha256": "0" * 64},
            {"protocol_sha256": "0" * 64},
            {"advisor_agreement": "approved"},
            {"maximum_n": 31},
            {"limitation_acknowledged": False},
            {"accepted_blocking_gaps": good["accepted_blocking_gaps"][:1]},
            {"accepted_capture_limits": []},
        ]
        wrong_selector = json.loads(json.dumps(good["accepted_blocking_gaps"]))
        wrong_selector[0]["selector"] = "$.rows[5]"
        changes.append({"accepted_blocking_gaps": wrong_selector})
        for index, change in enumerate(changes):
            decision = self.tmp / f"wrong-decision-{index}.json"
            write_new(decision, good | change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                freeze(
                    self.tmp / f"diagnostic-invalid-decision-{index}",
                    selection,
                    inventory,
                    self.protocol,
                    diagnostic_decision=decision,
                )

    def test_diagnostic_retains_canonical_identity_document_and_fragment_exclusions(self) -> None:
        inventory, _ = self.full_prior_inventory(capture_gaps=2)
        base = read(self.real_selection())[0]
        variants = [
            ({"profile": {"name": "Alias", "id": "https://openalex.org/A606"}}, None),
            ({"profile": {"name": "Alias", "id": "A123"}, "email": "OLD@example.invalid"}, None),
            ({}, {"url": "https://ARCHIVE.invalid/paper#other"}),
            ({}, {"url": "https://user@institute.invalid/page"}),
            ({}, {"excerpt": "Old synthetic excerpt"}),
        ]
        self.source.write_text(self.source.read_text() + " Old synthetic excerpt")
        for index, (case_change, evidence_change) in enumerate(variants):
            row = json.loads(json.dumps(base)) | case_change
            if evidence_change:
                row["evidence"][0].update(evidence_change)
            selection = self.tmp / f"diagnostic-overlap-{index}.json"
            write_new(selection, [row])
            decision = self.diagnostic_decision(inventory, selection)
            with self.subTest(index=index), self.assertRaises(ValueError):
                freeze(
                    self.tmp / f"diagnostic-overlap-root-{index}",
                    selection,
                    inventory,
                    self.protocol,
                    diagnostic_decision=decision,
                )
        inventory, _ = self.full_prior_inventory(capture_gaps=2, document_hash=sha(self.source))
        selection = self.real_selection()
        with self.assertRaisesRegex(ValueError, "document_bytes_overlap"):
            freeze(
                self.tmp / "diagnostic-body-overlap",
                selection,
                inventory,
                self.protocol,
                diagnostic_decision=self.diagnostic_decision(inventory, selection),
            )

    def test_diagnostic_count_cap_and_one_pair_per_person(self) -> None:
        inventory, _ = self.full_prior_inventory(capture_gaps=2)
        base = read(self.real_selection())[0]
        rows = []
        for index in range(31):
            row = json.loads(json.dumps(base))
            row.update(case_id=f"case{index}", group_id=f"group{index}", pair_id=f"pair{index}")
            row["profile"] = {"name": "Synthetic new target", "id": f"A90{index}"}
            rows.append(row)
        for name, selected in (
            ("over-cap", rows),
            ("same-group", rows[:2]),
            ("same-person", rows[:2]),
        ):
            selected = json.loads(json.dumps(selected))
            if name == "same-group":
                selected[1]["group_id"] = selected[0]["group_id"]
            elif name == "same-person":
                selected[1]["profile"] = selected[0]["profile"]
            selection = self.tmp / f"diagnostic-{name}.json"
            write_new(selection, selected)
            with self.subTest(name=name), self.assertRaises(ValueError):
                freeze(
                    self.tmp / f"diagnostic-{name}-root",
                    selection,
                    inventory,
                    self.protocol,
                    diagnostic_decision=self.diagnostic_decision(inventory, selection),
                )
        selection = self.tmp / "diagnostic-30.json"
        write_new(selection, rows[:30])
        root = self.tmp / "diagnostic-30-root"
        manifest = read(
            freeze(
                root,
                selection,
                inventory,
                self.protocol,
                diagnostic_decision=self.diagnostic_decision(inventory, selection),
            )
        )
        self.assertEqual(manifest["diagnostic_scope"]["sample_status"], "complete_planned_count")
        self.assertEqual(len(read(prepare_model(root))["requests"]), 60)

    def test_diagnostic_frozen_decision_and_status_cannot_be_downgraded(self) -> None:
        inventory, _ = self.full_prior_inventory(capture_gaps=2)
        selection = self.real_selection()
        decision = self.diagnostic_decision(inventory, selection)
        for index, mutation in enumerate(("decision", "status", "scope", "launch")):
            root = self.tmp / f"diagnostic-tamper-{index}"
            manifest_path = freeze(
                root,
                selection,
                inventory,
                self.protocol,
                diagnostic_decision=decision,
            )
            manifest = read(manifest_path)
            if mutation == "decision":
                path = root / "diagnostic-decision.json"
                path.write_bytes(path.read_bytes() + b"\n")
            elif mutation == "status":
                manifest["holdout_status"] = "recorded_prior_overlap_checked"
                manifest.pop("diagnostic_decision_sha256")
            elif mutation == "scope":
                manifest["diagnostic_scope"]["actual_n"] = 30
            else:
                manifest["launch_authorized"] = True
            manifest_path.write_bytes(encoded(manifest))
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                checked(root)

    def test_diagnostic_prepared_request_cannot_grant_live_permission(self) -> None:
        inventory, _ = self.full_prior_inventory(capture_gaps=2)
        selection = self.real_selection()
        root = self.tmp / "diagnostic-request-tamper"
        freeze(
            root,
            selection,
            inventory,
            self.protocol,
            diagnostic_decision=self.diagnostic_decision(inventory, selection),
        )
        prepared_path = prepare_model(root)
        prepared = read(prepared_path)
        request_id = prepared["order"][0]
        path = root / prepared["requests"][request_id]["path"]
        request = read(path)
        request["launch_authorized"] = True
        path.write_bytes(encoded(request))
        prepared["requests"][request_id]["sha256"] = sha(path)
        prepared_path.write_bytes(encoded(prepared))
        with self.assertRaisesRegex(ValueError, "диагностическое ограничение"):
            prepared_request(root, request_id)

    def test_historical_identity_aliases_cannot_be_hidden_by_fresh_group_or_pair_ids(self) -> None:
        inventory, _ = self.full_prior_inventory()
        profiles: list[dict[str, Any]] = [
            {"name": "Renamed synthetic target", "author_id": "https://openalex.org/A123"},
            {"name": "Renamed synthetic target", "identifiers": {"aliases": ["A123"]}},
            {
                "name": "Renamed synthetic target",
                "identifiers": {"openalex": "A900"},
                "orcid": "https://orcid.org/0000-0000-0000-0001",
            },
            {
                "name": "Renamed synthetic target",
                "identifiers": {"openalex": "A900"},
                "aliases": ["Arbitrary name", "orcid:0000-0000-0000-0001"],
            },
        ]
        for index, profile in enumerate(profiles):
            with (
                self.subTest(index=index),
                self.assertRaisesRegex(ValueError, "researcher_alias_overlap"),
            ):
                freeze(
                    self.tmp / f"alias-bypass-{index}",
                    self.real_selection(profile=profile),
                    inventory,
                    self.protocol,
                )
        mismatched = {
            "name": "Synthetic conflicting aliases",
            "author_id": "A123",
            "orcid": "0000-0000-0000-001X",
        }
        with self.assertRaisesRegex(ValueError, "identity_alias_conflict"):
            freeze(
                self.tmp / "alias-mismatch",
                self.real_selection(profile=mismatched),
                inventory,
                self.protocol,
            )

    def test_real_guard_detects_canonical_person_email_even_after_id_renaming(self) -> None:
        inventory, _ = self.full_prior_inventory()
        for index, (address, reason) in enumerate(
            [
                (" old @ example.invalid ", "researcher_email_pair_overlap"),
                ("OLD@example.invalid", "conservative_email_casefold_collision"),
            ]
        ):
            rows = read(self.real_selection(profile={"name": "Synthetic", "id": "A123"}))
            rows[0].update(group_id="fresh_group", pair_id=f"fresh_pair_{index}", email=address)
            path = self.tmp / f"renamed-pair-selection-{index}.json"
            write_new(path, rows)
            with self.assertRaisesRegex(ValueError, reason):
                freeze(self.tmp / f"canonical-pair-bypass-{index}", path, inventory, self.protocol)

    def test_actual_new_snapshot_is_compared_to_each_recorded_hash_namespace(self) -> None:
        for representation in ("body", "decoded", "text"):
            inventory, _ = self.full_prior_inventory(
                representation=representation, document_hash=sha(self.source)
            )
            with (
                self.subTest(representation=representation),
                self.assertRaisesRegex(ValueError, "document_bytes_overlap:" + representation),
            ):
                freeze(
                    self.tmp / f"document-{representation}",
                    self.real_selection(),
                    inventory,
                    self.protocol,
                )

    def test_document_url_collision_ignores_fragment_and_hostname_case(self) -> None:
        inventory, _ = self.full_prior_inventory()
        selection = self.real_selection(source_url="https://ARCHIVE.invalid/paper#renamed")
        with self.assertRaisesRegex(ValueError, "document_url_overlap"):
            freeze(self.tmp / "same-url-new-bytes", selection, inventory, self.protocol)
        for index, invalid in enumerate(
            ("https:///missing-host", "https://user@archive.invalid/paper")
        ):
            with self.assertRaisesRegex(ValueError, "публичный URL"):
                freeze(
                    self.tmp / f"invalid-public-url-{index}",
                    self.real_selection(source_url=invalid),
                    inventory,
                    self.protocol,
                )

    def test_old_evidence_excerpt_cannot_be_reused_under_a_larger_body_and_new_url(self) -> None:
        inventory, _ = self.full_prior_inventory()
        self.source.write_text("New synthetic context. Old synthetic excerpt. More new context.")
        rows = read(self.real_selection())
        rows[0]["evidence"][0]["excerpt"] = "Old synthetic excerpt"
        path = self.tmp / "reused-fragment-new-document.json"
        write_new(path, rows)
        with self.assertRaisesRegex(ValueError, "evidence_excerpt_overlap:excerpt"):
            freeze(self.tmp / "fragment-reuse", path, inventory, self.protocol)

    def test_real_guard_rejects_missing_identity_and_split_researcher_groups(self) -> None:
        inventory, _ = self.full_prior_inventory()
        selection = self.real_selection(
            profile={"name": "No ID", "identifiers": {"openalex": None}}
        )
        with self.assertRaisesRegex(ValueError, "сильный идентификатор"):
            freeze(self.tmp / "no-identity", selection, inventory, self.protocol)
        rows = read(self.selection)[:2]
        for index, row in enumerate(rows):
            row.update(group_id=f"split_group_{index}")
            row["profile"] = {"name": "Same synthetic researcher", "id": "A900"}
        path = self.tmp / "split-groups.json"
        write_new(path, rows)
        with self.assertRaisesRegex(ValueError, "разные group_id"):
            freeze(self.tmp / "split-current-researcher", path, inventory, self.protocol)

    def test_incomplete_full_registry_and_changed_provenance_hash_are_rejected(self) -> None:
        inventory, _ = self.full_prior_inventory(incomplete=True)
        with self.assertRaisesRegex(ValueError, "Неполный реестр"):
            freeze(
                self.tmp / "incomplete-full-registry",
                self.real_selection(),
                inventory,
                self.protocol,
            )
        inventory, metadata = self.full_prior_inventory()
        metadata.write_bytes(metadata.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "hash changed"):
            freeze(
                self.tmp / "changed-source-metadata",
                self.real_selection(),
                inventory,
                self.protocol,
            )

    def test_cleared_recordsets_with_consistent_lookup_cannot_bypass_source_derivation(
        self,
    ) -> None:
        inventory_path, _ = self.full_prior_inventory()
        forged = read(inventory_path)
        for table in ("people", "pairs", "documents", "examples"):
            forged[table] = []
        forged["lookup"] = make_lookup([], [], [], [])
        projection = self.tmp / "cleared-recordsets.json"
        write_new(projection, forged)
        with self.assertRaises(ValueError):
            freeze(self.tmp / "recordset-erasure", self.real_selection(), projection, self.protocol)

    def test_empty_historical_metadata_cannot_certify_a_new_holdout(self) -> None:
        inventory_path, metadata = self.full_prior_inventory()
        metadata.write_text("{}")
        (metadata.parent / "sample.json").write_text("[]")
        empty_inventory = build_inventory(read(inventory_path)["plan"])
        self.assertFalse(empty_inventory["completeness"]["complete"])
        path = self.tmp / "empty-historical-metadata.json"
        write_new(path, empty_inventory)
        with self.assertRaises(ValueError):
            freeze(self.tmp / "zero-history-bypass", self.real_selection(), path, self.protocol)

    def test_model_or_human_answer_fields_cannot_enter_source_input(self) -> None:
        rows = read(self.selection)
        rows[0]["model_prediction"] = "supported"
        path = self.tmp / "leaked.json"
        write_new(path, rows)
        with self.assertRaisesRegex(ValueError, "раскрыть ответы"):
            freeze(
                self.tmp / "leaked-root",
                path,
                self.exclusions,
                self.protocol,
                development_only=True,
            )

    def test_duplicate_person_email_cannot_be_renamed_into_a_new_observation(self) -> None:
        rows = read(self.selection)
        rows.append(
            {
                **rows[0],
                "case_id": "another_case",
                "pair_id": "another_pair",
                "email": "  " + rows[0]["email"] + "  ",
            }
        )
        path = self.tmp / "renamed-pair.json"
        write_new(path, rows)
        with self.assertRaisesRegex(ValueError, "group_id/email"):
            freeze(
                self.tmp / "duplicate-pair-root",
                path,
                self.exclusions,
                self.protocol,
                development_only=True,
            )

    def test_source_or_common_input_tampering_stops_imports(self) -> None:
        for source in (self.root / "sources").glob("*.txt"):
            source.write_text("Modified source")
        with self.assertRaisesRegex(ValueError, "источника изменён"):
            checked(self.root)

    def test_packet_snapshot_tampering_stops_human_import(self) -> None:
        packet = export(self.root, "adelina")
        answers = read(packet.parent / "answers-template.json")
        answers.update(
            reviewed_at="2026-10-31T11:00:00+03:00", minutes=1, actual_human_attestation=True
        )
        for path in (packet.parent / "sources").glob("*.txt"):
            path.write_text("Changed displayed source")
        path = self.tmp / "bad-packet-answers.json"
        write_new(path, answers)
        with self.assertRaisesRegex(ValueError, "разметчика изменён"):
            import_human(self.root, path, "bad")

    def test_unresolved_and_technical_skips_are_not_insufficient(self) -> None:
        self.humans("adelina", ["supported", "refuted", "insufficient", "supported"])
        self.humans("sasha", ["supported", "refuted", "insufficient", "refuted"])
        self.models("B", ["supported"] * 4)
        self.models("C", ["supported", "refuted", None, "supported"])
        out = analyze(self.root, self.tmp / "analysis.json", resamples=200)
        report = read(out)
        self.assertEqual(report["human_status_counts"], {"agreement": 3, "unresolved": 1})
        b, c = (report["intention_to_process"][arm] for arm in ("B", "C"))
        self.assertAlmostEqual(b["R_resolved"], 2 / 3)
        self.assertEqual(c["R_resolved"], 0)
        self.assertEqual((b["T"], c["T"]), (1, 1))
        self.assertEqual((b["coverage"], c["coverage"]), (1, 0.5))
        self.assertEqual(b["R_all_accepted_bounds"], [0.5, 0.75])
        self.assertEqual(c["R_all_accepted_bounds"], [0, 0.5])
        self.assertEqual(c["technical_missing"], 1)
        self.assertEqual(c["insufficient"], 0)
        self.assertEqual(report["paired_valid_diagnostic"]["cases"], 3)
        self.assertEqual(report["resources"]["C"]["cost_usd"]["unknown_attempts"], 4)
        self.assertEqual(report["bootstrap"]["clusters"], 3)
        self.assertEqual(report["R_B_minus_C_all_accepted_conservative_bounds"], [0, 0.75])
        self.assertEqual(b["refuted_accepted_resolved"], 1)
        self.assertEqual(b["insufficient_accepted_resolved"], 1)
        self.assertEqual(report["human_initial_agreement"]["agreement"], 0.75)
        self.assertAlmostEqual(report["human_initial_agreement"]["kappa_unweighted"], 7 / 11)
        self.assertEqual(report["per_annotator_sensitivity"]["adelina"]["B"]["R_resolved"], 0.5)
        self.assertEqual(report["per_annotator_sensitivity"]["sasha"]["B"]["R_resolved"], 0.75)
        cells = report["paired_acceptance_by_human_class"]
        self.assertEqual(sum(sum(c.values()) for c in cells.values()), 4)
        self.assertEqual(cells["unknown_human"]["B1_C1"], 1)

    def test_real_adjudication_does_not_rewrite_original_answers(self) -> None:
        first = self.humans("adelina", ["supported", "refuted", "insufficient", "supported"])
        original_hash = sha(first)
        self.humans("sasha", ["supported", "refuted", "insufficient", "refuted"])
        value = {
            "schema": "nir_adjudication_v1",
            "manifest_sha256": sha(self.root / "manifest.json"),
            "adjudicator": "Synthetic adjudicator",
            "actual_human_attestation": True,
            "reviewed_at": "2026-10-31T12:00:00+03:00",
            "decisions": [
                {
                    "case_id": "c4",
                    "label": "refuted",
                    "reason": "Explicit contradiction",
                    "source_ids": ["s1"],
                }
            ],
        }
        path = self.tmp / "adjudication.json"
        write_new(path, value)
        adjudicate(self.root, path, "first")
        report = read(analyze(self.root, self.tmp / "adjudicated.json", resamples=5))
        self.assertEqual(report["human_status_counts"], {"agreement": 3, "adjudicated": 1})
        self.assertEqual(sha(first), original_hash)
        with self.assertRaisesRegex(ValueError, "неразрешённого"):
            adjudicate(self.root, path, "duplicate")

    def test_duplicate_model_results_are_rejected_before_polluting_analysis(self) -> None:
        self.models("B", ["supported"] * 4)
        with self.assertRaisesRegex(ValueError, "Повторный модельный"):
            import_model(self.root, self.tmp / "model-B.json", "duplicate")
        self.assertEqual(len(list((self.root / "model-records" / "B").glob("*.json"))), 1)

    def test_wrong_arm_prompt_or_case_hash_is_rejected(self) -> None:
        self.models("B", ["supported"] * 4)
        value = read(self.tmp / "model-B.json")
        value["prompt_sha256"] = sha(self.root / "prompt-C.json")
        path = self.tmp / "wrong-prompt.json"
        write_new(path, value)
        with self.assertRaisesRegex(ValueError, "инструкции"):
            import_model(self.root, path, "wrong")
        value["prompt_sha256"] = sha(self.root / "prompt-B.json")
        value["results"][0]["case_input_sha256"] = "wrong"
        path = self.tmp / "wrong-case.json"
        write_new(path, value)
        with self.assertRaisesRegex(ValueError, "общему входу"):
            import_model(self.root, path, "wrong-case")

    def test_unknown_and_mismatching_receipts_are_reported_honestly(self) -> None:
        record = self.models("B", ["supported"] * 4)
        first = read(record)["results"][0]
        self.assertIsNone(first["observed_model"])
        self.assertIsNone(first["receipt_sha256"])
        self.assertIn("not independently verified", first["provenance"])
        value = read(self.tmp / "model-B.json")
        manifest = read(self.root / "manifest.json")
        value.update(arm="C", prompt_sha256=manifest["prompt_sha256"]["C"])
        for result in value["results"]:
            result["observed_model"] = "different-model"
            result["observed_effort"] = "synthetic-effort"
            result["receipt"] = {"model": "different-model", "usage": {"input_tokens": 100}}
            result["raw_response"] = json.dumps(
                {
                    "identity": "supported",
                    "object_relation": "supported",
                    "reason": "Synthetic",
                    "source_ids": ["s1"],
                }
            )
        path = self.tmp / "mismatching-C.json"
        write_new(path, value)
        import_model(self.root, path, "mismatching")
        report = read(analyze(self.root, self.tmp / "mismatch.json", resamples=5))
        self.assertEqual(report["configuration_status"], "mismatch")
        self.assertEqual(report["resources"]["C"]["configuration_mismatches"], 4)
        self.assertIsNone(report["resources"]["C"]["cost_usd"]["total"])

    def test_template_versions_cannot_be_frozen_as_actual_metadata(self) -> None:
        protocol = read(self.protocol)
        protocol["runtime_version"] = "TEMPLATE replace actual"
        path = self.tmp / "template-protocol.json"
        write_new(path, protocol)
        with self.assertRaisesRegex(ValueError, "TEMPLATE"):
            freeze(
                self.tmp / "template-root",
                self.selection,
                self.exclusions,
                path,
                development_only=True,
            )

    def test_no_labels_or_no_acceptance_are_undefined_not_zero_risk(self) -> None:
        report = read(analyze(self.root, self.tmp / "empty.json", resamples=10))
        self.assertEqual(report["human_status_counts"], {"human_missing": 4})
        for arm in ("B", "C"):
            metrics = report["intention_to_process"][arm]
            self.assertIsNone(metrics["R_resolved"])
            self.assertIsNone(metrics["T"])
            self.assertEqual(metrics["technical_missing"], 4)
            self.assertEqual(metrics["R_all_accepted_bounds"], [None, None])
        interval = report["bootstrap"]["intervals"]["R_B_minus_C"]
        self.assertEqual(
            interval,
            {
                "valid_draws": 0,
                "undefined_draws": 10,
                "interval_95": None,
                "conditional_on_defined_draws": True,
                "degenerate": False,
            },
        )

    def test_analysis_keeps_shared_parent_mode_and_creates_private_output(self) -> None:
        shared = self.tmp / "shared-parent"
        shared.mkdir()
        shared.chmod(0o755)
        output = analyze(self.root, shared / "analysis.json", resamples=5)
        self.assertEqual(stat.S_IMODE(shared.stat().st_mode), 0o755)
        self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
        with (
            patch(
                "sys.argv",
                [
                    "nir",
                    "analyze",
                    "--root",
                    str(self.root),
                    "--out",
                    str(shared / "cli.json"),
                    "--resamples",
                    "5",
                ],
            ),
            patch("builtins.print"),
        ):
            main()
        self.assertEqual(stat.S_IMODE(shared.stat().st_mode), 0o755)
        self.assertEqual(stat.S_IMODE((shared / "cli.json").stat().st_mode), 0o600)

    def test_analysis_new_parents_are_private_and_git_outputs_are_rejected(self) -> None:
        new_parent = self.tmp / "new-private" / "nested"
        analyze(self.root, new_parent / "analysis.json", resamples=5)
        self.assertEqual(stat.S_IMODE(new_parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(new_parent.parent.stat().st_mode), 0o700)
        repository = self.tmp / "repository"
        repository.mkdir()
        (repository / ".git").write_text("gitdir: synthetic-worktree-marker")
        with self.assertRaisesRegex(ValueError, "вне git"):
            analyze(self.root, repository / "new-directory" / "analysis.json", resamples=5)
        self.assertFalse((repository / "new-directory").exists())

    def test_shared_cluster_resampling_recalculates_arm_denominators(self) -> None:
        rows: list[dict[str, Any]] = [
            {
                "group_id": "g1",
                "human_label": "refuted",
                "B": "supported",
                "C": "supported",
                "B_technical": False,
                "C_technical": False,
            },
            {
                "group_id": "g1",
                "human_label": "supported",
                "B": "supported",
                "C": "supported",
                "B_technical": False,
                "C_technical": False,
            },
            {
                "group_id": "g2",
                "human_label": "supported",
                "B": "insufficient",
                "C": "insufficient",
                "B_technical": False,
                "C_technical": False,
            },
        ]
        report = paired_bootstrap(rows, 154, 100)
        self.assertEqual(report, paired_bootstrap(rows, 154, 100))
        self.assertEqual(report["clusters"], 2)
        self.assertEqual(report["intervals"]["T_C_minus_B"]["interval_95"], [0, 0])
        self.assertEqual(report["intervals"]["R_B_minus_C"]["interval_95"], [0, 0])
        self.assertGreater(report["intervals"]["R_B_minus_C"]["undefined_draws"], 0)
        self.assertEqual(arm_metrics(rows, "B")["T"], 0.5)

    def test_composition_preserves_explicit_refutation_and_abstention(self) -> None:
        self.assertEqual(compose("supported", "supported"), "supported")
        self.assertEqual(compose("insufficient", "supported"), "insufficient")
        self.assertEqual(compose("supported", "refuted"), "refuted")
        self.assertEqual(compose("refuted", "insufficient"), "refuted")
        with self.assertRaises(ValueError):
            compose("conflict_between_people", "supported")


if __name__ == "__main__":
    unittest.main()
