"""Переносимый assisted pipeline: mock HTTP/native, binding, resume и selected human scope."""

import asyncio
import fcntl
import json
import tempfile
import unittest
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
from test_enrichment_semantics import assessment, fixture

from sfr_enrichment.evidence import immutable_json
from sfr_enrichment.review import human_metrics, import_human
from sfr_enrichment.runner import (
    METHOD,
    checked_index,
    frozen,
    prepare,
    progress,
    run,
    validate_plan,
)
from sfr_enrichment.sources import MATHNET_DECODER
from sfr_enrichment_legacy.enrichment_contact_first import verify_contact_input
from sfr_enrichment_legacy.enrichment_experiment import read, sha

URL = "https://university.example/person"


class AssistedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "new"
        self.profiles = [
            {"id": "A1", "name": "Jane", "institution": "Example"},
            {"id": "A2", "name": "No accepted contact", "institution": "Example"},
        ]
        self.plan: dict[str, Any] = {
            "schema": METHOD,
            "requested_search_model": "gpt-6.1-sol",
            "requested_search_effort": "high",
            "profiles": [
                {
                    "author_id": p["id"],
                    "sources": [
                        {
                            "url": URL + p["id"],
                            "kind": "direct_http",
                            "discovery": {
                                "method": "agent_search",
                                "observed_url": URL + p["id"],
                                "query": "Jane scientist",
                                "note": "fixture",
                            },
                        }
                    ],
                }
                for p in self.profiles
            ],
        }
        deadline = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        self.scope: dict[str, Any] = {
            "live_authorized": True,
            "authorization_reference": "fixture-only-mock-no-live",
            "deadline_acquisition": deadline,
            "deadline_verification": deadline,
            "HTTP_total_cap": 8,
            "HTTP_per_profile_cap": 4,
            "remaining_stop": 15,
        }
        for name, value in (
            ("profiles", self.profiles),
            ("plan", self.plan),
            ("scope", self.scope),
        ):
            immutable_json(self.base / (name + ".json"), value)
        prepare(
            self.root,
            self.base / "profiles.json",
            self.base / "plan.json",
            self.base / "scope.json",
        )

    def test_prepare_and_dry_run_are_offline_and_freeze_plan(self) -> None:
        with (
            patch("sfr_enrichment.runner.PublicLoader") as loader,
            patch("sfr_enrichment.native.execute") as model,
        ):
            self.assertEqual(frozen(self.root)[0], self.profiles)
            report = progress(self.root)
            self.assertEqual(report["native_jobs_started"], 0)
            self.assertEqual(report["source_reservations"], 0)
            self.assertIsNone(report["subscription_debit"])
            loader.assert_not_called()
            model.assert_not_called()
        self.plan["profiles"][0]["sources"][0]["url"] += "/changed"
        (self.root / "search-plan.json").write_text(json.dumps(self.plan))
        with self.assertRaisesRegex(ValueError, "Frozen"):
            frozen(self.root)

    def test_invalid_plan_and_duplicate_profiles_rejected(self) -> None:
        for change in ("invented_url", "no_query", "duplicate", "wrong_model"):
            plan = json.loads(json.dumps(self.plan))
            profiles = list(self.profiles)
            if change == "invented_url":
                plan["profiles"][0]["sources"][0]["url"] += "/guess"
            if change == "no_query":
                del plan["profiles"][0]["sources"][0]["discovery"]["query"]
            if change == "duplicate":
                profiles[1] = profiles[0]
            if change == "wrong_model":
                plan["requested_search_model"] = "glm"
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_plan(profiles, plan)

    def fake_native(
        self, directory: Path, prompt: str, *args: object, **kwargs: object
    ) -> tuple[Path, dict[str, Any]]:
        task = json.loads(prompt)["task"]
        source = task["semantic_input"]
        _, result = fixture("personal_contact")
        del result["provenance"]
        result.update(
            {
                k: task[k]
                for k in ("author_id", "input_sha256", "batch_input_sha256", "batch_ticket_id")
            }
        )
        result["profile_assessments"]["identity"].update(
            verdict="supported", evidence_refs=["E0001"]
        )
        result["items"] = [
            assessment(i["item_id"], evidence_refs=i["evidence_refs"], student_level=["unknown"])
            for i in source["items"]
        ]
        if source["author_id"] == "A2":
            for item in result["items"]:
                item["identity_verdict"] = "insufficient"
        immutable_json(directory / "started.json", {"fixture": True})
        immutable_json(directory / "finished.json", {"fixture": True})
        path = directory / "raw-result.json"
        immutable_json(path, result)
        receipt = {
            "agent_id": "independent-fixture",
            "runtime_status": "runtime_not_exposed",
            "model": None,
            "effort": None,
            "tokens": {"input_tokens": 100, "output_tokens": 20, "cached_input_tokens": 0},
            "cost_usd": None,
            "raw_result_sha256": sha(path),
            "requested_model": "gpt-6.1-sol",
            "requested_effort": "high",
        }
        immutable_json(directory / "receipt.json", receipt)
        self.assertIsNotNone(kwargs["deadline_epoch"])
        return path, receipt

    def mocked_run(
        self,
        *,
        native: Callable[..., Any] | None = None,
        body: str | None = None,
        author_ids: list[str] | None = None,
    ) -> tuple[Path, int]:
        def response(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/robots.txt":
                return httpx.Response(
                    200, text="User-agent: *\nAllow: /", headers={"content-type": "text/plain"}
                )
            if request.url.path.endswith("func_string.js"):
                return httpx.Response(
                    200, text=MATHNET_DECODER, headers={"content-type": "application/javascript"}
                )
            return httpx.Response(
                200,
                text=body or '<h1>Jane Example</h1><a href="mailto:jane@example.edu">Email</a>',
                headers={"content-type": "text/html;charset=utf-8"},
            )

        client = httpx.AsyncClient
        with (
            patch(
                "sfr_enrichment.sources.socket.getaddrinfo",
                return_value=[(0, 0, 0, "", ("8.8.8.8", 443))],
            ),
            patch(
                "sfr_enrichment.sources.httpx.AsyncClient",
                side_effect=lambda **kw: client(transport=httpx.MockTransport(response), **kw),
            ),
            patch("sfr_enrichment.contacts.Budget.wait", new_callable=AsyncMock),
            patch(
                "sfr_enrichment.native.execute", side_effect=native or self.fake_native
            ) as execute,
        ):
            cards = asyncio.run(run(self.root, 90, author_ids))
            return cards, execute.call_count

    def test_smoke_selector_keeps_frozen_sample_then_completes_remaining(self) -> None:
        cards, calls = self.mocked_run(author_ids=["A1"])
        self.assertEqual(calls, 1)
        self.assertFalse((self.root / "entries.json").exists())
        self.assertEqual(frozen(self.root)[0], self.profiles)
        self.assertIn("smoke-A1", str(cards))
        cards, calls = self.mocked_run()
        self.assertEqual(calls, 1)
        self.assertEqual(progress(self.root)["validated_results"], 2)
        self.assertTrue((self.root / "entries.json").exists())

    def test_selector_rechecks_date_gate_of_other_saved_results(self) -> None:
        self.mocked_run()
        from sfr_enrichment.fragments import check_dates

        def gate(corpus: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
            if result["author_id"] == "A2":
                raise ValueError("Saved profile date gate failed")
            return check_dates(corpus, result)

        with (
            patch("sfr_enrichment.runner.check_dates", side_effect=gate),
            self.assertRaisesRegex(ValueError, "Saved profile date gate"),
        ):
            self.mocked_run(author_ids=["A1"])

    def test_selector_rejects_foreign_profile_before_calls(self) -> None:
        with self.assertRaisesRegex(ValueError, "selector"):
            asyncio.run(run(self.root, 90, ["A999"]))

    def test_same_address_in_two_sources_preserves_both_refs(self) -> None:
        for row in self.plan["profiles"]:
            source = dict(row["sources"][0])
            source["url"] += "/second"
            source["discovery"] = dict(source["discovery"], observed_url=source["url"])
            row["sources"].append(source)
        # Test-only fixture root regenerated; production frozen plans are never mutated.
        immutable_json(self.base / "plan-two.json", self.plan)
        self.root = self.base / "two"
        prepare(
            self.root,
            self.base / "profiles.json",
            self.base / "plan-two.json",
            self.base / "scope.json",
        )
        _, calls = self.mocked_run()
        self.assertEqual(calls, 2)
        collector = read(self.root / "normalized/A1/collector.json")
        self.assertEqual(len(collector["items"]), 1)
        refs = collector["items"][0]["evidence_refs"]
        urls = {collector["evidence_pool"][r]["url"] for r in refs}
        self.assertEqual(len(urls), 2)
        self.assertFalse(collector["provenance"]["model_called"])

    def test_pipeline_binding_full_context_reuse_and_contact_packet(self) -> None:
        cards, calls = self.mocked_run()
        self.assertEqual(calls, 2)
        self.assertEqual(progress(self.root)["validated_results"], 2)
        manifest = read(cards.parent / "manifest.json")
        self.assertEqual([len(p["review_claim_ids"]) for p in manifest["profiles"]], [1, 0])
        html = cards.read_text()
        self.assertIn("не доказательство", html) if "не доказательство" in html else self.assertIn(
            "а не доказательство", html
        )
        self.assertEqual(html.count("<article id="), 2)
        self.assertIn("Четыре отдельные проверки контакта", html)
        self.assertIn("Исправить категорию (необязательно)", html)
        self.assertIn("просто живая персональная страница", html)
        self.assertIn("Самостоятельно проверять работу адреса не требуется", html)
        self.assertEqual(manifest["schema"], "human_packet_v4")
        self.assertIn(URL + "A1", html)
        before = {
            str(p.relative_to(self.root)): sha(p) for p in self.root.rglob("*") if p.is_file()
        }
        with (
            patch("sfr_enrichment.runner.PublicLoader") as loader,
            patch("sfr_enrichment.native.execute") as execute,
        ):
            self.assertEqual(asyncio.run(run(self.root, 90)), cards)
            loader.assert_not_called()
            execute.assert_not_called()
        self.assertEqual(
            before,
            {str(p.relative_to(self.root)): sha(p) for p in self.root.rglob("*") if p.is_file()},
        )
        pool = read(Path(read(self.root / "prepared/A1.json")["input_path"]))["evidence_pool"]
        self.assertTrue(any("-F" in ref for ref in pool))

    def test_selected_human_scope_four_axes_required_and_hidden_claim_rejected(self) -> None:
        cards, _ = self.mocked_run()
        manifest = cards.parent / "manifest.json"
        claim = read(manifest)["profiles"][0]["review_claim_ids"][0]
        answer: dict[str, Any] = {
            "schema": "human_answers_v4",
            "packet_id": "assisted-contacts",
            "packet_sha256": sha(manifest),
            "human_name": "Synthetic test fixture",
            "reviewed_at": "2026-10-11T12:00:00Z",
            "minutes": 1,
            "actual_human_attestation": True,
            "answers": [
                {
                    "author_id": "A1",
                    "claim_id": claim,
                    "decision": "uncertain",
                    "note": "synthetic, never baseline human result",
                    "dimensions": {
                        "text": "agree",
                        "identity": "uncertain",
                        "source_date": "agree",
                        "current": "uncertain",
                    },
                }
            ],
        }
        path = self.base / "synthetic-answers.json"
        path.write_text(json.dumps(answer))
        record = read(
            import_human(self.base / "synthetic-records", manifest, path, "fixture-record")
        )
        self.assertEqual(record["reviewed_claims"], 1)
        self.assertEqual(record["schema"], "human_record_v4")
        self.assertEqual(record["review_scope"], "selected_personal_contacts")
        self.assertFalse(record["profile_review"][1]["human_reviewed"])
        del answer["answers"][0]["dimensions"]["current"]
        path.write_text(json.dumps(answer))
        with self.assertRaisesRegex(ValueError, "text/identity/source_date/current"):
            import_human(self.base / "bad", manifest, path, "bad")
        answer["answers"][0]["author_id"] = "A2"
        path.write_text(json.dumps(answer))
        with self.assertRaisesRegex(ValueError, "Неизвестное"):
            import_human(self.base / "hidden", manifest, path, "hidden")

    def test_legacy_contact_answers_remain_separate_from_new_current_axis(self) -> None:
        cards, _ = self.mocked_run()
        packet = read(cards.parent / "manifest.json")
        packet["schema"] = "human_packet_v3"
        manifest = self.base / "legacy-manifest.json"
        immutable_json(manifest, packet)
        answers = {
            "schema": "human_answers_v3",
            "packet_id": packet["packet_id"],
            "packet_sha256": sha(manifest),
            "human_name": "Synthetic test fixture",
            "reviewed_at": "2026-10-11T12:00:00Z",
            "minutes": 1,
            "actual_human_attestation": True,
            "answers": [
                {
                    "author_id": "A1",
                    "claim_id": packet["profiles"][0]["review_claim_ids"][0],
                    "decision": "agree",
                    "note": "synthetic compatibility test",
                    "dimensions": {"text": "agree", "identity": "agree", "current": "uncertain"},
                }
            ],
        }
        path = self.base / "legacy-answers.json"
        immutable_json(path, answers)
        record = import_human(self.base / "compatibility", manifest, path, "legacy")
        self.assertEqual(read(record)["comparisons"][0]["human"], answers["answers"][0])
        metrics = human_metrics([record])["strata"]["targeted"]
        self.assertEqual(metrics["legacy_contact_current_v3_uncertain"], 1)
        self.assertNotIn("current_agree", metrics)
        self.assertNotIn("source_date_reviewed", metrics)
        answers["schema"] = "human_answers_v4"
        path.write_text(json.dumps(answers))
        with self.assertRaisesRegex(ValueError, "другому пакету"):
            import_human(self.base / "cross-version", manifest, path, "bad")

    def test_parent_stop_and_concurrent_run_do_not_touch_http_or_model(self) -> None:
        with (self.root / "run.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(ValueError, "Другой run"):
                asyncio.run(run(self.root, 90))
        immutable_json(self.base / "stopped.json", {"fixture": True})
        with (
            patch("sfr_enrichment.runner.PublicLoader") as loader,
            patch("sfr_enrichment.native.execute") as model,
        ):
            with self.assertRaisesRegex(ValueError, "STOP root"):
                asyncio.run(run(self.root, 90))
            loader.assert_not_called()
            model.assert_not_called()

    def test_transfer_index_rejects_modified_and_escaping_files(self) -> None:
        archive = self.base / "archive"
        archive.mkdir()
        (archive / "body").write_text("exact")
        index = archive / "index.json"
        immutable_json(index, {"private_file_sha256": {"body": sha(archive / "body")}})
        self.assertEqual(checked_index(archive, index, sha(index))["checked_files"], 1)
        (archive / "body").write_text("changed")
        with self.assertRaisesRegex(ValueError, "evidence SHA"):
            checked_index(archive, index, sha(index))
        escaped = archive / "escaped.json"
        immutable_json(
            escaped, {"private_file_sha256": {"../profiles.json": sha(self.base / "profiles.json")}}
        )
        with self.assertRaisesRegex(ValueError, "evidence SHA"):
            checked_index(archive, escaped, sha(escaped))

    def test_source_and_raw_result_tamper_prevent_reuse(self) -> None:
        self.mocked_run()
        raw = self.root / "runs/A1/native_verifier/raw-result.json"
        original = raw.read_bytes()
        raw.write_bytes(original + b" ")
        with patch("sfr_enrichment.native.execute") as model:
            with self.assertRaisesRegex(ValueError, "binding изменён"):
                asyncio.run(run(self.root, 90))
            model.assert_not_called()
        raw.write_bytes(original)
        input_path = Path(read(self.root / "prepared/A1.json")["input_path"])
        pool = read(input_path)["evidence_pool"]
        source_path = Path(pool["E0001"]["source_record_path"])
        source_path.write_bytes(source_path.read_bytes() + b" ")
        with patch("sfr_enrichment.native.execute") as model:
            with self.assertRaisesRegex(ValueError, "source registry"):
                asyncio.run(run(self.root, 90))
            model.assert_not_called()

    def test_unknown_started_native_attempt_is_never_retried(self) -> None:
        from sfr_enrichment_legacy.enrichment_native import execute

        with self.assertRaisesRegex(RuntimeError, "fixture interruption"):
            self.mocked_run(
                native=lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("fixture interruption"))
            )
        directory = self.root / "runs/A1/native_verifier"
        immutable_json(directory / "started.json", {"unknown": True})
        with patch("sfr_enrichment.native.isolation_probe") as probe:
            with self.assertRaisesRegex(ValueError, "автоматический повтор запрещён"):
                self.mocked_run(native=execute)
            probe.assert_not_called()
        self.assertEqual(
            progress(self.root)["unknown_started_jobs_no_retry"], ["runs/A1/native_verifier"]
        )

    def test_deadline_and_quota_prevent_native_start(self) -> None:
        with patch("sfr_enrichment.runner.PublicLoader") as loader:
            with self.assertRaisesRegex(ValueError, "≤15%"):
                asyncio.run(run(self.root, 15))
            loader.assert_not_called()
        scope = read(self.root / "scope.json")
        scope["deadline_verification"] = "2000-01-01T00:00:00+00:00"
        new = self.base / "expired"
        (self.base / "expired-scope.json").write_text(json.dumps(scope))
        prepare(
            new,
            self.base / "profiles.json",
            self.base / "plan.json",
            self.base / "expired-scope.json",
        )
        self.root = new
        with self.assertRaisesRegex(ValueError, "Verification deadline"):
            self.mocked_run()
        self.assertFalse((new / "runs").exists())

    def test_failed_date_guard_preserves_raw_and_reuses_without_model_retry(self) -> None:
        def wrong_date(
            directory: Path, prompt: str, *args: object, **kwargs: object
        ) -> tuple[Path, dict[str, Any]]:
            path, receipt = self.fake_native(directory, prompt, *args, **kwargs)
            raw = read(path)
            raw["items"][0].update(
                information_date="1999", date_basis="content", current_applicability="historical"
            )
            path.write_text(json.dumps(raw))
            receipt["raw_result_sha256"] = sha(path)
            (directory / "receipt.json").write_text(json.dumps(receipt))
            return path, receipt

        with self.assertRaisesRegex(ValueError, "Date year absent"):
            self.mocked_run(native=wrong_date)
        raw_path = self.root / "runs/A1/native_verifier/raw-result.json"
        raw_sha = sha(raw_path)
        self.assertEqual(progress(self.root)["validated_results"], 0)
        with patch("sfr_enrichment.native.execute") as model:
            with self.assertRaisesRegex(ValueError, "Date year absent"):
                asyncio.run(run(self.root, 90))
            model.assert_not_called()
        self.assertEqual(sha(raw_path), raw_sha)

    def test_offline_authorization_cannot_start_sources_or_models(self) -> None:
        scope = dict(self.scope, live_authorized=False)
        path = self.base / "offline-scope.json"
        path.write_text(json.dumps(scope))
        root = self.base / "offline"
        prepare(root, self.base / "profiles.json", self.base / "plan.json", path)
        with (
            patch("sfr_enrichment.runner.PublicLoader") as loader,
            patch("sfr_enrichment.native.execute") as model,
        ):
            with self.assertRaisesRegex(ValueError, "Offline scope"):
                asyncio.run(run(root, 90))
            loader.assert_not_called()
            model.assert_not_called()

    def test_spaced_at_and_contiguous_context_are_source_bound(self) -> None:
        self.mocked_run(body="<h1>Jane Example</h1><p>Personal contact jane @ example.edu</p>")
        source = read(Path(read(self.root / "prepared/A1.json")["input_path"]))
        self.assertEqual(source["items"][0]["value"], "jane@example.edu")
        ref = source["items"][0]["evidence_refs"][0]
        self.assertIn("jane @ example.edu", source["evidence_pool"][ref]["excerpt"])
        self.assertIn("Jane Example", source["evidence_pool"][ref]["excerpt"])

    def test_supported_renderer_uses_observed_decoder_and_remains_bound(self) -> None:
        for row in self.plan["profiles"]:
            row["sources"][0]["render_mathnet"] = True
        plan_path = self.base / "render-plan.json"
        plan_path.write_text(json.dumps(self.plan))
        self.root = self.base / "render"
        prepare(self.root, self.base / "profiles.json", plan_path, self.base / "scope.json")
        rendered = '<a href="mailto:jane@example.edu">jane@example.edu</a>'
        encoded = "".join(chr(65 + ord(c) // 16) + chr(65 + ord(c) % 16) for c in rendered)
        body = (
            "<h1>Jane Example</h1><script src='/func_string.js'></script>"
            + "<script>document.write(decode_email('"
            + encoded
            + "'));</script>"
        )
        self.mocked_run(body=body)
        source = read(Path(read(self.root / "prepared/A1.json")["input_path"]))
        self.assertEqual(source["items"][0]["value"], "jane@example.edu")
        self.assertTrue(
            any(
                "rendered-sources" in row["source_record_path"]
                for row in source["evidence_pool"].values()
            )
        )
        self.assertEqual(progress(self.root)["source_reservations"], 6)

    def test_full_prompt_cap_includes_rubric_and_never_invokes_model(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "fixture interruption"):
            self.mocked_run(
                native=lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("fixture interruption"))
            )
        source_path = Path(read(self.root / "prepared/A1.json")["input_path"])
        with patch("sfr_enrichment.native.execute") as model:
            with self.assertRaisesRegex(ValueError, "Полный prompt"):
                verify_contact_input(
                    self.root, source_path, remaining_percent=90, prompt_byte_cap=1
                )
            model.assert_not_called()
