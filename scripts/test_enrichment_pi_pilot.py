"""Регрессии границ свежего пилота без сети и LLM."""

import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock, patch

from enrichment_batch import Batch, encoded, immutable
from enrichment_experiment import FIELDS, read, sha
from enrichment_native import schema
from enrichment_pi_pilot import (
    HIGH_CONFIGS,
    HIGH_METHOD,
    HIGH_SEED,
    bind_sources,
    checkpoint,
    collector_schema,
    event,
    final_json,
    freeze,
    import_pi,
    policy,
    reader_body,
    reserve,
    run,
    run_pi,
    select_profiles,
    stage_config,
    validate_collection,
)


class PilotTests(unittest.TestCase):
    def fixture(self, root: Path) -> Batch:
        immutable(root / "sample.json", encoded([{"id": "A1"}, {"id": "A2"}]))
        immutable(root / "manifest.json", encoded({"sample_sha256": sha(root / "sample.json")}))
        immutable(root / "rules.md", b"fixed rules")
        batch = Batch.create(
            root / "batches" / "01", root, ["A1"], root / "rules.md", concurrency=1
        )
        batch.ticket("A1", "collect")
        return batch

    def test_high_config_missing_or_wrong_stops_before_launch(self) -> None:
        for configs in (
            None,
            HIGH_CONFIGS | {"collector": HIGH_CONFIGS["collector"] | {"effort": "low"}},
        ):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                immutable(
                    root / "manifest.json",
                    encoded({"method": HIGH_METHOD, "stage_configs": configs}),
                )
                with patch("enrichment_pi_pilot.subprocess.Popen") as launch:
                    with self.assertRaisesRegex(ValueError, "матрица"):
                        run_pi(root, cast(Batch, None), "A1", "collector", {}, "rules", {})
                    launch.assert_not_called()

    def test_high_freeze_fixture_locks_112_exclusions_and_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            index, old, previous, root = [
                base / name for name in ("index", "old", "previous", "high")
            ]
            docs = [
                {"id": f"A{i:04d}", "name": "Тест", "h_index": 1, "institution": f"I{i % 12:02d}"}
                for i in range(9002)
            ]
            immutable(index / "docs.json", encoded(docs))
            immutable(index / "meta.json", encoded({"corpus_sha": "fixture"}))
            hashes = {name: sha(index / name) for name in ("docs.json", "meta.json")}
            immutable(
                old / "manifest.json", encoded({"index_hashes": hashes, "index_version": "fixture"})
            )
            immutable(old / "sample.json", encoded(docs[:100]))
            immutable(previous / "sample.json", encoded(docs[100:112]))
            preserved = {
                path: sha(path)
                for path in (old / "sample.json", previous / "sample.json", index / "docs.json")
            }
            db = base / "fixture.sqlite"
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "CREATE TABLE institutions(id INTEGER PRIMARY KEY, openalex_id TEXT, "
                    "name_ru TEXT, name_en TEXT)"
                )
                conn.execute(
                    "CREATE TABLE authors(openalex_id TEXT, orcid TEXT, display_name TEXT, "
                    "h_index INTEGER, last_known_institution_id INTEGER, "
                    "merged_into_id TEXT, suspect_merge INTEGER)"
                )
                conn.executemany(
                    "INSERT INTO institutions VALUES(?,?,?,?)",
                    [(i, f"I{i:02d}", f"I{i:02d}", None) for i in range(12)],
                )
                conn.executemany(
                    "INSERT INTO authors VALUES(?,?,?,?,?,?,?)",
                    [(row["id"], None, "Тест", 1, i % 12, None, 0) for i, row in enumerate(docs)],
                )
            freeze(root, index, db, old, method=HIGH_METHOD, exclude_pilot=previous)
            manifest = read(root / "manifest.json")
            self.assertEqual(manifest["stage_configs"], HIGH_CONFIGS)
            self.assertEqual(manifest["seed"], HIGH_SEED)
            self.assertEqual(manifest["excluded_profiles"], 112)
            self.assertEqual(manifest["sample_sha256"], sha(root / "sample.json"))
            self.assertFalse(
                {p["id"] for p in read(root / "sample.json")} & {p["id"] for p in docs[:112]}
            )
            self.assertEqual(len(list((root / "batches").glob("*/batch.json"))), 12)
            self.assertEqual({path: sha(path) for path in preserved}, preserved)

    def test_high_import_rejects_mismatched_runtime_without_relaunch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            immutable(directory / "request.json", encoded({"config": HIGH_CONFIGS["pi_verifier"]}))
            immutable(
                directory / "finished.json",
                encoded({"done": True, "exit_code": 0, "pending_operations": []}),
            )
            immutable(
                directory / "pi" / "000001-session-event.json",
                encoded(
                    {
                        "type": "message_end",
                        "message": {
                            "role": "assistant",
                            "content": [{"type": "text", "text": '{"author_id":"A1"}'}],
                        },
                    }
                ),
            )
            immutable(
                directory / "pi" / "000002-runtime.json",
                encoded(HIGH_CONFIGS["pi_verifier"] | {"effort": "low"}),
            )
            with patch("enrichment_pi_pilot.subprocess.Popen") as launch:
                with self.assertRaisesRegex(ValueError, "runtime отличается"):
                    import_pi(directory, "A1", "pi_verifier")
                launch.assert_not_called()
            self.assertFalse((directory / "receipt.json").exists())

    def test_high_requires_explicit_exclusion_and_rejects_old_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ValueError, "exclude-pilot"):
                freeze(root, root, root, root, method=HIGH_METHOD)
            self.fixture(root)
            with patch("enrichment_pi_pilot.run_profile") as launch:
                with self.assertRaisesRegex(ValueError, "Метод root"):
                    run(root, 1, expected_method=HIGH_METHOD)
                launch.assert_not_called()

    def test_stable_selection_excludes_112_fixture_ids(self) -> None:
        docs = [{"id": f"A{i:04d}", "institution": f"I{i % 12:02d}"} for i in range(300)]
        excluded = {row["id"] for row in docs[:112]}
        selected = select_profiles(docs, excluded, HIGH_SEED)
        self.assertEqual(selected, select_profiles(list(reversed(docs)), excluded, HIGH_SEED))
        self.assertEqual(len({p["institution"] for p in selected}), 12)
        self.assertFalse({p["id"] for p in selected} & excluded)

    def test_high_pi_request_roundtrip_config_before_mock_transport(self) -> None:
        for stage in ("collector", "pi_verifier"):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                immutable(
                    root / "manifest.json",
                    encoded({"method": HIGH_METHOD, "stage_configs": HIGH_CONFIGS}),
                )
                process = Mock(stdout=['{"type":"done"}\n'])
                process.poll.return_value = 0
                process.wait.return_value = 0
                task = {"author_id": "A1", "input_sha256": "fixture-input"}
                directory = root / "runs" / "A1" / stage
                with (
                    patch("enrichment_pi_pilot.subprocess.Popen", return_value=process) as launch,
                    patch(
                        "enrichment_pi_pilot.import_pi",
                        return_value=(directory / "result.json", {}),
                    ),
                ):
                    run_pi(root, cast(Batch, None), "A1", stage, task, "rules", {})
                    self.assertEqual(launch.call_count, 1)
                request = read(directory / "request.json")
                self.assertEqual(request["config"], HIGH_CONFIGS[stage])
                self.assertEqual(request["task"], task)
                self.assertEqual(
                    read(directory / "started.json")["task_sha256"], sha(directory / "request.json")
                )
                self.assertEqual(request["method"], HIGH_METHOD)

    def test_high_cached_import_never_relaunches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            immutable(
                root / "manifest.json",
                encoded({"method": HIGH_METHOD, "stage_configs": HIGH_CONFIGS}),
            )
            directory = root / "runs" / "A1" / "collector"
            immutable(directory / "result.json", b"{}")
            receipt = {
                "result_sha256": sha(directory / "result.json"),
                "requested_config": HIGH_CONFIGS["collector"],
            }
            immutable(directory / "receipt.json", encoded(receipt))
            with patch("enrichment_pi_pilot.subprocess.Popen") as launch:
                self.assertEqual(
                    run_pi(root, cast(Batch, None), "A1", "collector", {}, "rules", {}),
                    (directory / "result.json", receipt),
                )
                launch.assert_not_called()
            self.assertEqual(stage_config(root, "native_verifier"), HIGH_CONFIGS["native_verifier"])

    def test_high_full_pair_uses_same_input_and_config(self) -> None:
        self.high_fixture = True
        self.test_full_pair_queue_import_with_unsupported_atom_and_no_network()

    def test_high_invalid_pi_stops_before_native(self) -> None:
        self.high_fixture = True
        self.pi_failure = True
        self.test_full_pair_queue_import_with_unsupported_atom_and_no_network()

    def test_high_known_invalid_outputs_remain_invalid_in_cards(self) -> None:
        self.high_fixture = True
        for failure in ("empty_level", "wrong_status", "wrong_version"):
            with self.subTest(failure=failure):
                self.high_failure = failure
                self.test_full_pair_queue_import_with_unsupported_atom_and_no_network()

    def test_high_literal_sources_flow_through_both_verifiers_and_cards(self) -> None:
        self.high_fixture = True
        self.literal_fixture = True
        self.test_full_pair_queue_import_with_unsupported_atom_and_no_network()

    def test_high_continues_nine_only_after_three_valid_pairs(self) -> None:
        self.high_fixture = True
        self.continue_nine = True
        self.test_full_pair_queue_import_with_unsupported_atom_and_no_network()

    def test_high_empty_collector_is_valid(self) -> None:
        self.high_fixture = True
        self.zero_items = True
        self.test_full_pair_queue_import_with_unsupported_atom_and_no_network()

    def test_json_extraction_rejects_ambiguous_and_nonobject(self) -> None:
        for text in ('{"author_id":"A1"} {"author_id":"A2"}', "[]", "broken text"):
            with self.assertRaises(ValueError):
                final_json(text)

    def test_high_bad_quote_stays_raw_and_blocks_new_evaluations(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            immutable(root / "manifest.json", encoded({"method": HIGH_METHOD}))
            raw = {
                "evidence_pool": {
                    "e1": {
                        "url": "https://official.test/person",
                        "excerpt": "Invented quote",
                        "resource_file": "https://official.test/person",
                    }
                }
            }
            immutable(root / "runs" / "A1" / "collector" / "result.json", encoded(raw))
            rawfile = "source.json"
            immutable(
                root / rawfile,
                encoded(
                    {
                        "message": {
                            "result": {
                                "content": [
                                    {
                                        "text": json.dumps(
                                            {
                                                "url": "https://official.test/person",
                                                "content": "Exact public source",
                                            }
                                        )
                                    }
                                ]
                            }
                        }
                    }
                ),
            )
            event(
                root,
                {
                    "action": "source_finished",
                    "author_id": "A1",
                    "kind": "zai_reader",
                    "outcome": "ok",
                    "raw_file": rawfile,
                    "arguments": {"url": "https://official.test/person"},
                },
            )
            before = sha(root / "runs" / "A1" / "collector" / "result.json")
            with self.assertRaisesRegex(ValueError, "цитата"):
                bind_sources(root, "A1", raw)
            self.assertEqual(sha(root / "runs" / "A1" / "collector" / "result.json"), before)
            binding = read(root / "source-bindings" / HIGH_METHOD / "A1.json")
            self.assertEqual(binding["bindings"][0]["collector_excerpt"], "Invented quote")
            self.assertFalse(binding["bindings"][0]["literal_quote_valid"])

    def test_high_failure_stops_following_profiles_and_reentry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profiles = [{"id": f"A{i}"} for i in range(12)]
            immutable(root / "sample.json", encoded(profiles))
            immutable(
                root / "manifest.json",
                encoded(
                    {
                        "method": HIGH_METHOD,
                        "stage_configs": HIGH_CONFIGS,
                        "sample_sha256": sha(root / "sample.json"),
                        "rules_hashes": {},
                    }
                ),
            )
            with (
                patch("enrichment_pi_pilot.Batch"),
                patch(
                    "enrichment_pi_pilot.run_profile", side_effect=ValueError("unknown request")
                ) as call,
            ):
                with self.assertRaisesRegex(ValueError, "остановлен"):
                    run(root, 3)
                self.assertEqual(call.call_count, 1)
                with self.assertRaisesRegex(ValueError, "остановлен"):
                    run(root, 3)
                self.assertEqual(call.call_count, 1)
            self.assertFalse(checkpoint(root)["succeeded"])

    def test_nested_json_body_excludes_metadata(self) -> None:
        result = {
            "content": [
                {
                    "text": json.dumps(
                        json.dumps(
                            {
                                "url": "https://official.test",
                                "content": "Exact\nquote",
                                "metadata": {"note": "not body"},
                            }
                        )
                    )
                }
            ]
        }
        self.assertEqual(reader_body(result), "Exact\nquote")
        self.assertNotIn("not body", reader_body(result))
        self.assertEqual(final_json('```json\n{"x":1}\n```'), {"x": 1})

    def test_global_counter_recovers_batch_charge_without_auxiliary_event(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            batch = self.fixture(root)
            operation = batch.reserve("A1-collect", "search", "first")
            batch.finish_operation(operation, "ok")
            with patch("enrichment_pi_pilot.events", return_value=[]):
                operation = reserve(root, batch, "A1", "search", "second")
            batch.finish_operation(operation, "ok")
            operation = reserve(root, batch, "A1", "search", "third")
            batch.finish_operation(operation, "ok")
            operation = reserve(root, batch, "A1", "search", "fourth")
            batch.finish_operation(operation, "ok")
            with self.assertRaisesRegex(ValueError, "Бюджет"):
                reserve(root, batch, "A1", "search", "fifth")

    def test_reader_refusal_survives_missing_ack(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            batch = self.fixture(root)
            directory = root / "runs" / "A1" / "collector" / "pi"
            immutable(
                directory / "000001-mcp-request.json",
                encoded(
                    {
                        "server": "zai_reader",
                        "message": {
                            "id": 7,
                            "method": "tools/call",
                            "params": {"arguments": {"url": "https://official.test/person"}},
                        },
                    }
                ),
            )
            immutable(
                directory / "000002-mcp-response.json",
                encoded(
                    {
                        "server": "zai_reader",
                        "message": {
                            "id": 7,
                            "result": {"isError": True, "content": [{"text": "403 forbidden"}]},
                        },
                    }
                ),
            )
            with self.assertRaisesRegex(ValueError, "остановлен"):
                reserve(root, batch, "A1", "page", "https://official.test/other")

    def test_unknown_attempt_never_relaunches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            batch = self.fixture(root)
            immutable(root / "runs" / "A1" / "collector" / "started.json", b"{}")
            with patch("enrichment_pi_pilot.subprocess.Popen") as launch:
                with self.assertRaisesRegex(ValueError, "Незавершённая"):
                    run_pi(root, batch, "A1", "collector", {}, "rules", {})
                launch.assert_not_called()

    def test_service_refusal_survives_next_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            batch = self.fixture(root)
            immutable(root / "pilot-events" / "000000.json", encoded({"action": "service_stopped"}))
            with patch("enrichment_pi_pilot.subprocess.Popen") as launch:
                with self.assertRaisesRegex(ValueError, "остановлен"):
                    run_pi(root, batch, "A2", "collector", {}, "rules", {})
                launch.assert_not_called()

    def test_private_dns_never_contacts_policy_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            batch = self.fixture(root)
            with (
                patch(
                    "enrichment_pi_pilot.socket.getaddrinfo",
                    return_value=[(2, 1, 6, "", ("10.2.3.4", 443))],
                ),
                patch("enrichment_pi_pilot.httpx.Client") as network,
            ):
                with self.assertRaisesRegex(ValueError, "непубличный"):
                    policy(root, batch, "A1", "https://official.test/person")
                network.assert_not_called()

    def test_found_requires_actual_atom(self) -> None:
        raw: dict[str, Any] = {
            "field_statuses": dict.fromkeys(FIELDS, "not_checked"),
            "items": [],
            "profile_evidence": {"identity": [], "current_affiliation": []},
            "evidence_pool": {},
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertEqual(validate_collection(root, "A1", raw), {})
            raw["field_statuses"]["workload"] = "found"
            self.assertEqual(validate_collection(root, "A1", raw), {})
            # Декларация found сама по себе не создаёт атом или покрытие.

    def test_failed_pi_import_is_not_success(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            immutable(
                root / "finished.json",
                encoded({"done": False, "exit_code": 0, "pending_operations": []}),
            )
            with self.assertRaisesRegex(ValueError, "не завершён"):
                import_pi(root, "A1", "collector")
            self.assertFalse((root / "receipt.json").exists())

    def test_http_capture_latches_without_auxiliary_event(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            batch = self.fixture(root)
            immutable(
                root / "runs" / "A1" / "collector" / "pi" / "000001-http.json",
                encoded({"status": 429}),
            )
            with patch("enrichment_pi_pilot.subprocess.Popen") as launch:
                with self.assertRaisesRegex(ValueError, "остановлен"):
                    run_pi(root, batch, "A2", "collector", {}, "rules", {})
                launch.assert_not_called()

    def test_mcp_refusal_search_latches_without_http_status(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            batch = self.fixture(root)
            operation = batch.reserve("A1-collect", "search", "search target has no domain")
            batch.finish_operation(operation, "429")
            with patch("enrichment_pi_pilot.subprocess.Popen") as launch:
                with self.assertRaisesRegex(ValueError, "остановлен"):
                    run_pi(root, batch, "A2", "collector", {}, "rules", {})
                launch.assert_not_called()

    def test_prefixed_json_import_without_another_call(self) -> None:
        self.assertEqual(
            final_json('Итоговый JSON:\n```json\n{"author_id":"A1"}\n```'), {"author_id": "A1"}
        )

    def test_raw_mcp_refusal_latches_before_operation_ack(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            batch = self.fixture(root)
            immutable(
                root / "runs" / "A1" / "collector" / "pi" / "000003-mcp-response.json",
                encoded(
                    {
                        "server": "zai_search",
                        "message": {
                            "result": {"isError": True, "content": [{"text": "Quota exceeded 429"}]}
                        },
                    }
                ),
            )
            with patch("enrichment_pi_pilot.subprocess.Popen") as launch:
                with self.assertRaisesRegex(ValueError, "остановлен"):
                    run_pi(root, batch, "A2", "collector", {}, "rules", {})
                launch.assert_not_called()

    def test_full_pair_queue_import_with_unsupported_atom_and_no_network(self) -> None:
        from enrichment_pi_pilot import finish_artifacts, run_profile

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            profiles = [
                {"id": f"A{i}", "name": "Тест", "institution": "Тест", "institution_id": "I1"}
                for i in range(1, 13)
            ]
            immutable(root / "sample.json", encoded(profiles))
            manifest: dict[str, Any] = {"sample_sha256": sha(root / "sample.json")}
            if getattr(self, "high_fixture", False):
                manifest.update(
                    method=HIGH_METHOD,
                    stage_configs=HIGH_CONFIGS,
                    rules_hashes={},
                    stage_configs_sha256=hashlib.sha256(encoded(HIGH_CONFIGS)).hexdigest(),
                    output_schema_hashes={
                        "collector": hashlib.sha256(encoded(collector_schema())).hexdigest(),
                        "verifier": hashlib.sha256(
                            encoded(schema("verify", strict_levels=True))
                        ).hexdigest(),
                    },
                )
            immutable(root / "manifest.json", encoded(manifest))
            from enrichment_pi_pilot import COLLECT_RULES

            batches = [
                Batch.create(
                    root / "batches" / f"{i + 1:02d}", root, [p["id"]], COLLECT_RULES, concurrency=1
                )
                for i, p in enumerate(profiles)
            ]

            def assessment(task: dict[str, Any]) -> dict[str, Any]:
                source = task["semantic_input"]
                axis: dict[str, Any] = {
                    "verdict": "insufficient",
                    "evidence_refs": [],
                    "information_date": None,
                    "date_basis": "unknown",
                    "explanation": "Нет оснований.",
                }
                return {
                    k: task[k]
                    for k in ("author_id", "batch_ticket_id", "batch_input_sha256", "input_sha256")
                } | {
                    "rules_version": "semantic-v3",
                    "items": [
                        {
                            "item_id": item["item_id"],
                            "text_verdict": "insufficient",
                            "identity_verdict": "insufficient",
                            "field_verdict": "insufficient",
                            "corrected_field": None,
                            "fact_kind": "literal",
                            "object_type": "scientist",
                            "object_relation": "insufficient",
                            "student_level": ["unknown"],
                            "information_date": None,
                            "date_basis": "unknown",
                            "current_applicability": "unknown",
                            "evidence_refs": [],
                            "explanation": "Нет прочитанного доказательства.",
                            "question": "Есть ли первоисточник?",
                        }
                        for item in source["items"]
                    ],
                    "profile_assessments": {
                        "identity": axis,
                        "current_affiliation": axis,
                        "activity": axis | {"status": "unknown"},
                    },
                    "summary": dict.fromkeys(
                        ("known", "unknown", "identity", "current_opportunity"),
                        "Основания не установлены.",
                    ),
                }

            def pi_call(
                root: Path, batch: Batch, aid: str, stage: str, task: dict[str, Any], *args: Any
            ) -> Any:
                if stage == "collector":
                    value = {
                        k: task[k] for k in ("author_id", "batch_ticket_id", "batch_input_sha256")
                    } | {
                        "items": [
                            {
                                "item_id": aid + "_1",
                                "field": "personal_contact",
                                "value": "Неподтверждённый кандидат",
                                "evidence_refs": [],
                            }
                        ],
                        "evidence_pool": {},
                        "profile_evidence": {"identity": [], "current_affiliation": []},
                        "field_statuses": dict.fromkeys(FIELDS, "not_checked"),
                    }
                    if getattr(self, "literal_fixture", False):
                        url = "https://official.test/" + aid
                        quote = "Contract duration: six months.\nForeign citizenship is permitted."
                        rawfile = f"runs/{aid}/collector/pi/000001-mcp-response.json"
                        immutable(
                            root / rawfile,
                            encoded(
                                {
                                    "message": {
                                        "result": {
                                            "content": [
                                                {
                                                    "text": json.dumps(
                                                        json.dumps(
                                                            {
                                                                "url": url,
                                                                "content": quote,
                                                                "metadata": {
                                                                    "note": "not evidence"
                                                                },
                                                            }
                                                        )
                                                    )
                                                }
                                            ]
                                        }
                                    }
                                }
                            ),
                        )
                        event(
                            root,
                            {
                                "action": "source_finished",
                                "author_id": aid,
                                "kind": "zai_reader",
                                "outcome": "ok",
                                "raw_file": rawfile,
                                "arguments": {"url": url},
                                "checked_at": "2026-10-09T00:00:00Z",
                            },
                        )
                        value["evidence_pool"] = {
                            "e1": {
                                "url": url,
                                "excerpt": quote,
                                "resource_file": url,
                                "object_type": "offer",
                                "information_date": None,
                            }
                        }
                        value["items"][0].update(
                            field="workload",
                            value="Контракт на шесть месяцев",
                            evidence_refs=["e1"],
                        )
                else:
                    value = assessment(task)
                    failure = "empty_level" if getattr(self, "pi_failure", False) else None
                    if failure == "empty_level":
                        value["items"][0]["student_level"] = []
                    elif failure == "wrong_status":
                        value["profile_assessments"]["activity"]["status"] = "alive"
                    elif failure == "wrong_version":
                        value["rules_version"] = "semantic-v2"
                if stage == "collector" and getattr(self, "zero_items", False):
                    value["items"] = []
                path = root / "runs" / aid / stage / "result.json"
                immutable(path, encoded(value))
                directory = path.parent
                config = HIGH_CONFIGS[stage]
                request = {"task": task, "config": config}
                immutable(directory / "request.json", encoded(request))
                immutable(
                    directory / "started.json",
                    encoded({"task_sha256": sha(directory / "request.json")}),
                )
                receipt = {
                    "agent_id": aid + "-" + stage,
                    "model": "zai/glm-5.3-flash",
                    "effort": "high",
                    "runtime_status": "recorded",
                    "tokens": 0,
                    "cost_usd": None,
                    "requested_config": config,
                    "effective_sdk_config": config,
                    "effective_settings": {
                        "cache_warming": "off",
                        "automatic_llm_retries": 0,
                        "retry_enabled": False,
                        "provider_retries": 0,
                        "timeout_ms": 600000,
                    },
                    "backend": {"provider": None, "model": None, "effort": None, "exposed": False},
                    "result_sha256": sha(path),
                    "automatic_retries": 0,
                }
                immutable(directory / "receipt.json", encoded(receipt))
                return path, receipt

            def native_call(directory: Path, prompt: str, *args: Any, **kwargs: Any) -> Any:
                task = json.loads(prompt.split("\nВХОД:\n")[-1])
                path = directory / "raw-result.json"
                value = assessment(task)
                failure = getattr(self, "high_failure", None)
                if failure == "empty_level":
                    value["items"][0]["student_level"] = []
                elif failure == "wrong_status":
                    value["profile_assessments"]["activity"]["status"] = "alive"
                elif failure == "wrong_version":
                    value["rules_version"] = "semantic-v2"
                immutable(path, encoded(value))
                immutable(directory / "prompt.txt", prompt.encode())
                immutable(directory / "events.jsonl", b"fixture events")
                immutable(
                    directory / "requested-config.json", encoded(HIGH_CONFIGS["native_verifier"])
                )
                immutable(
                    directory / "command.json",
                    encoded(
                        [
                            "codex",
                            "exec",
                            "-m",
                            "gpt-6.1-sol",
                            "-c",
                            'model_provider="openai"',
                            "-c",
                            'model_reasoning_effort="high"',
                            "-c",
                            'web_search="disabled"',
                            "-c",
                            "features.shell_tool=false",
                            "-c",
                            "features.unified_exec=false",
                        ]
                    ),
                )
                receipt = {
                    "agent_id": task["author_id"] + "-native",
                    "runtime_status": "runtime_not_exposed",
                    "model": None,
                    "effort": None,
                    "tokens": {"input_tokens": 1, "output_tokens": 1},
                    "cost_usd": None,
                    "requested_model": "gpt-6.1-sol",
                    "requested_effort": "high",
                    "automatic_cli_retries": 0,
                    "tool_calls": 0,
                    "raw_result_sha256": sha(path),
                    "prompt_sha256": sha(directory / "prompt.txt"),
                    "events_sha256": sha(directory / "events.jsonl"),
                }
                immutable(directory / "receipt.json", encoded(receipt))
                return path, receipt

            with (
                patch("enrichment_pi_pilot.run_pi", side_effect=pi_call) as pi,
                patch("enrichment_pi_pilot.execute", side_effect=native_call) as native,
            ):
                if getattr(self, "pi_failure", False):
                    with self.assertRaisesRegex(ValueError, "Pi ответ невалиден"):
                        run_profile(root, profiles[0], batches[0])
                    self.assertEqual(pi.call_count, 2)
                    native.assert_not_called()
                    raw = read(root / "runs" / "A1" / "pi_verifier" / "result.json")
                    self.assertEqual(raw["items"][0]["student_level"], [])
                    wrapper = read(
                        next(
                            (
                                root
                                / "semantics"
                                / "semantic-v3"
                                / "control-runs"
                                / HIGH_METHOD
                                / "outputs"
                                / (HIGH_METHOD + "-pi")
                            ).glob("A1.json")
                        )
                    )
                    self.assertFalse(wrapper["validation"]["succeeded"])
                    self.assertIsNone(wrapper["classifications"])
                    return
                for p, b in zip(profiles[:3], batches[:3], strict=True):
                    run_profile(root, p, b)
                finish_artifacts(root)
                self.assertEqual(pi.call_count, 6)
                self.assertEqual(native.call_count, 3)
                pi_inputs = [
                    call.args[4]["input_sha256"]
                    for call in pi.call_args_list
                    if call.args[3] == "pi_verifier"
                ]
                native_inputs = [
                    json.loads(call.args[1].split("\nВХОД:\n")[-1])["input_sha256"]
                    for call in native.call_args_list
                ]
                self.assertEqual(pi_inputs, native_inputs)
                if getattr(self, "high_fixture", False):
                    for call in native.call_args_list:
                        self.assertEqual(
                            call.kwargs["required_config"], HIGH_CONFIGS["native_verifier"]
                        )
                        self.assertEqual(
                            call.args[2]["properties"]["items"]["items"]["properties"][
                                "student_level"
                            ]["minItems"],
                            1,
                        )
                if getattr(self, "continue_nine", False):
                    run(root, 12, expected_method=HIGH_METHOD)
                    finish_artifacts(root)
                    self.assertEqual(pi.call_count, 24)
                    self.assertEqual(native.call_count, 12)
                    self.assertTrue(checkpoint(root, 12)["succeeded"])
            self.assertTrue((root / "paired-human" / "packets" / "pi12-01" / "cards.html").exists())
            if getattr(self, "high_fixture", False):
                inventory = {
                    str(p.relative_to(root)): sha(p) for p in root.rglob("*") if p.is_file()
                }
                with (
                    patch("enrichment_pi_pilot.subprocess.Popen") as launch,
                    patch("enrichment_pi_pilot.execute") as native,
                ):
                    gate = checkpoint(root, 3)
                    self.assertEqual(
                        gate["succeeded"], not bool(getattr(self, "high_failure", None)), gate
                    )
                    launch.assert_not_called()
                    native.assert_not_called()
                self.assertEqual(
                    inventory,
                    {str(p.relative_to(root)): sha(p) for p in root.rglob("*") if p.is_file()},
                )
                card = root / "paired-human" / "compact-v3" / "pi12-01" / "cards.html"
                self.assertTrue(card.exists())
                if getattr(self, "high_failure", None):
                    self.assertIn("Исходный ответ с ошибками", card.read_text())
                    wrapper = read(
                        Path(read(root / "paired" / "A1.json")["result_paths"]["native"])
                    )
                    self.assertFalse(wrapper["validation"]["succeeded"])
                    self.assertIsNone(wrapper["classifications"])
                else:
                    self.assertEqual(len(gate["profiles"]), 3)
                    self.assertEqual(len(gate["backend_unknown"]), 9)
                    receipt_path = root / "runs" / "A1" / "pi_verifier" / "receipt.json"
                    before = receipt_path.read_bytes()
                    wrong = read(receipt_path)
                    wrong["effective_sdk_config"] = HIGH_CONFIGS["pi_verifier"] | {"effort": "low"}
                    receipt_path.write_bytes(encoded(wrong))
                    with patch("enrichment_pi_pilot.run_profile") as launch:
                        self.assertFalse(checkpoint(root, 3)["succeeded"])
                        with self.assertRaisesRegex(ValueError, "checkpoint3"):
                            run(root, 12)
                        launch.assert_not_called()
                    receipt_path.write_bytes(before)
                    self.assertTrue(checkpoint(root, 3)["succeeded"])
            for batch in batches[:3]:
                with batch.locked() as log:
                    completed = batch.completed(log, batch.config["ids"][0], "metrics")
                    if getattr(self, "high_failure", None):
                        self.assertIsNone(completed)
                    else:
                        self.assertIsNotNone(completed)
