"""Synthetic acquisition-only tests: MockTransport, no live HTTP or model calls."""

import asyncio
import fcntl
import json
import ssl
import tempfile
import unittest
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx

from sfr_enrichment.common import read, sha
from sfr_enrichment.evidence import immutable_json
from sfr_enrichment.nir_acquisition import (
    MAXIMA,
    RECOVERY_FILES,
    RECOVERY_SCHEMA,
    REDIRECT_REVISION,
    REDIRECT_SCHEMA,
    REVISION,
    CampaignLoader,
    checked,
    code_hashes,
    collect_person,
    continue_redirect_cycle,
    continue_ssl_abort,
    initialize,
    prepare,
    preserved_snapshot,
    register_redirect_cycle,
    register_ssl_abort,
    run,
    validate_recovery,
    validate_recovery_decision,
    validate_redirect_decision,
    validate_redirect_recovery,
)
from sfr_enrichment.sources import PublicLoader, SourceUnavailable


class AcquisitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "campaign"
        self.profiles = [{"id": f"A{i}", "name": f"Synthetic Person {i}"} for i in range(1, 13)]
        self.scope: dict[str, Any] = MAXIMA | {
            "authorization_reference": "synthetic-test-only-no-live",
            "live_authorized": True,
            "deadline_acquisition": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            "model_job_cap": 0,
        }

    def init(self) -> None:
        immutable_json(self.base / "profiles.json", self.profiles)
        immutable_json(self.base / "scope.json", self.scope)
        initialize(self.root, self.base / "profiles.json", self.base / "scope.json")

    def row(self, index: int, *, sources: bool = True) -> dict[str, Any]:
        url = f"https://source{index}.example/person"
        return {
            "author_id": f"A{index}",
            "search_queries": ["synthetic scientist"],
            "sources": [
                {
                    "url": url,
                    "kind": "direct_http",
                    "discovery": {
                        "method": "agent_search",
                        "observed_url": url,
                        "query": "synthetic scientist",
                        "note": "Mock-only observed URL",
                    },
                }
            ]
            if sources
            else [],
        }

    def batch(self, name: str, rows: list[dict[str, Any]]) -> Path:
        path = self.base / (name + ".json")
        immutable_json(path, {"profiles": rows})
        return prepare(self.root, name, path)

    def invoke(
        self,
        name: str,
        *,
        body: str | None = None,
        status: int = 200,
        ssl_failure: bool = False,
        continuation: bool = False,
        redirect_person: str | None = None,
        redirect_continuation: bool = False,
    ) -> tuple[list[str], AsyncMock]:
        calls: list[str] = []

        def response(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            if request.url.path == "/robots.txt":
                return httpx.Response(
                    200, text="User-agent: *\nAllow: /", headers={"content-type": "text/plain"}
                )
            if ssl_failure:
                raise ssl.SSLError("synthetic record layer failure")
            if request.url.host == redirect_person:
                return httpx.Response(302, headers={"location": str(request.url)})
            return httpx.Response(
                status,
                text=body
                if body is not None
                else '<h1>Synthetic Person</h1><a href="mailto:person@example.org">'
                "person@example.org</a>",
                headers={"content-type": "text/html; charset=utf-8"},
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
            patch("sfr_enrichment.nir_acquisition.asyncio.sleep", new_callable=AsyncMock) as wait,
            patch("sfr_enrichment.native.execute", side_effect=AssertionError("No model")) as model,
            patch(
                "sfr_enrichment.contacts.verify_contact_input",
                side_effect=AssertionError("No verifier"),
            ) as verify,
        ):
            if redirect_continuation:
                asyncio.run(continue_redirect_cycle(self.root, live=True))
            elif continuation:
                asyncio.run(continue_ssl_abort(self.root, live=True))
            else:
                asyncio.run(run(self.root, name, live=True))
            model.assert_not_called()
            verify.assert_not_called()
        return calls, wait

    def test_offline_init_prepare_empty_sources_and_no_resubmission(self) -> None:
        self.init()
        self.batch("first", [self.row(1, sources=False)])
        calls, _ = self.invoke("first")
        self.assertEqual(calls, [])
        person = self.root / "batches/first/people/A1"
        self.assertEqual(read(person / "result.json")["status"], "no_usable_source")
        self.assertEqual(read(person / "corpus.json")["sources"], [])
        self.assertEqual(read(person / "collector.json")["candidates"], [])
        with self.assertRaisesRegex(ValueError, "already attempted"):
            self.invoke("first")
        with self.assertRaisesRegex(ValueError, "already prepared"):
            prepare(self.root, "first", self.base / "first.json")

    def test_candidates_are_literals_full_sources_saved_without_labels(self) -> None:
        self.init()
        self.batch("first", [self.row(1)])
        calls, wait = self.invoke("first")
        self.assertEqual(len(calls), 2)
        self.assertTrue(wait.await_count)
        person = self.root / "batches/first/people/A1"
        collector = read(person / "collector.json")
        self.assertEqual([c["email"] for c in collector["candidates"]], ["person@example.org"])
        self.assertEqual(collector["model_jobs"], 0)
        corpus = read(person / "corpus.json")
        self.assertEqual(len(corpus["sources"]), 1)
        self.assertTrue(corpus["fragments"])
        self.assertFalse(any("label" in c or "verdict" in c for c in collector["candidates"]))
        self.assertEqual(len(list((self.root / "HTTP-ledger").glob("*-finished.json"))), 2)

    def test_no_candidate_retains_identity_evidence_and_http_failure_receipt(self) -> None:
        self.init()
        self.batch("first", [self.row(1)])
        self.invoke("first", body="<h1>Synthetic Person with no email</h1>")
        person = self.root / "batches/first/people/A1"
        self.assertEqual(read(person / "result.json")["status"], "no_candidate")
        self.assertTrue(read(person / "corpus.json")["fragments"])
        self.batch("second", [self.row(2)])
        self.invoke("second", status=404)
        failure = next((self.root / "batches/second/failures/A2").glob("*.json"))
        self.assertTrue(Path(read(failure)["receipt_path"]).exists())
        self.assertEqual(read(failure)["retries"], 0)

    def test_global_http_cap_across_batches_and_failed_batch_cannot_repeat(self) -> None:
        self.scope["HTTP_total_cap"] = 2
        self.init()
        self.batch("first", [self.row(1)])
        self.batch("second", [self.row(2)])
        self.invoke("first")
        with self.assertRaisesRegex(ValueError, "Frozen HTTP budget"):
            self.invoke("second")
        self.assertEqual(len(list((self.root / "HTTP-ledger").glob("*-reserved.json"))), 2)
        failure = read(self.root / "batches/second/failure.json")
        self.assertFalse(failure["retry_allowed"])
        with self.assertRaisesRegex(ValueError, "already attempted"):
            self.invoke("second")

    def test_batch_cap_and_person_cap_are_separate(self) -> None:
        self.scope["HTTP_batch_cap"] = 1
        self.init()
        self.batch("first", [self.row(1)])
        with self.assertRaisesRegex(ValueError, "batch HTTP budget"):
            self.invoke("first")
        self.assertEqual(len(list((self.root / "HTTP-ledger").glob("*-reserved.json"))), 1)

    def test_person_cap_failure_is_saved_and_next_person_is_allowed(self) -> None:
        self.scope["HTTP_per_profile_cap"] = 1
        self.init()
        self.batch("first", [self.row(1), self.row(2)])
        self.invoke("first")
        results = read(self.root / "batches/first/result.json")["people"]
        self.assertEqual([r["status"] for r in results], ["no_usable_source"] * 2)
        self.assertEqual(len(list((self.root / "HTTP-ledger").glob("*-reserved.json"))), 2)

    def test_unknown_attempt_stops_new_requests(self) -> None:
        self.init()
        self.batch("first", [self.row(1)])
        immutable_json(
            self.root / "HTTP-ledger/0000-reserved.json",
            {"author_id": "A1", "url": "https://unknown.example/", "kind": "robots"},
        )
        with self.assertRaisesRegex(ValueError, "Unfinished HTTP"):
            self.invoke("first")
        self.assertEqual(len(list((self.root / "HTTP-ledger").glob("*-reserved.json"))), 1)

    def test_disk_cap_checked_before_physical_request(self) -> None:
        self.scope["disk_byte_cap"] = 100000
        self.init()
        self.batch("first", [self.row(1)])
        with self.assertRaisesRegex(ValueError, "Frozen disk budget"):
            self.invoke("first")
        self.assertEqual(list((self.root / "HTTP-ledger").glob("*-reserved.json")), [])
        self.assertTrue((self.root / "batches/first/failure.json").exists())

    def test_queue_sequence_batch_limit_query_limit_and_provenance(self) -> None:
        self.init()
        for name, rows, message in [
            ("skip", [self.row(2)], "frozen queue"),
            ("large", [self.row(i) for i in range(1, 12)], "1–10"),
            ("queries", [self.row(1) | {"search_queries": ["a", "b", "c", "d"]}], "queries"),
            ("provenance", [self.row(1) | {"search_queries": ["different"]}], "discovery log"),
            ("sources", [self.row(1) | {"sources": self.row(1)["sources"] * 4}], "source count"),
        ]:
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, message):
                self.batch(name, rows)
        self.batch("first", [self.row(1)])
        self.batch("second", [self.row(2)])
        with self.assertRaisesRegex(ValueError, "Previous batch"):
            self.invoke("second")

    def test_mutation_and_nonzero_model_budget_rejected(self) -> None:
        self.scope["model_job_cap"] = 1
        with self.assertRaisesRegex(ValueError, "zero model"):
            self.init()
        self.scope["model_job_cap"] = 0
        (self.base / "scope.json").write_text(json.dumps(self.scope))
        initialize(self.root, self.base / "profiles.json", self.base / "scope.json")
        self.batch("first", [self.row(1)])
        (self.root / "batches/first/plan.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "Frozen batch plan"):
            self.invoke("first")

    def test_authorization_deadline_stop_and_writer_exclusion(self) -> None:
        self.init()
        self.batch("first", [self.row(1, sources=False)])
        with self.assertRaisesRegex(ValueError, "authorization"):
            asyncio.run(run(self.root, "first"))
        with (self.root / "acquisition.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(ValueError, "writer is already active"):
                self.invoke("first")
        immutable_json(self.root / "stopped.json", {"reason": "synthetic stop"})
        with self.assertRaisesRegex(ValueError, "STOP"):
            self.invoke("first")

    def test_expired_campaign_cannot_start(self) -> None:
        self.scope["deadline_acquisition"] = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        self.init()
        self.batch("first", [self.row(1, sources=False)])
        with self.assertRaisesRegex(ValueError, "deadline"):
            self.invoke("first")
        self.assertFalse((self.root / "batches/first/started.json").exists())

    def test_tampered_batch_sequence_cannot_skip_queue(self) -> None:
        self.init()
        path = self.batch("first", [self.row(1, sources=False)])
        item = read(path)
        item["start_index"] = 1
        path.write_text(json.dumps(item))
        with self.assertRaisesRegex(ValueError, "sequence changed"):
            self.invoke("first")

    def test_ssl_failure_keeps_error_receipt_without_retry_or_disabling_tls(self) -> None:
        self.init()
        self.batch("first", [self.row(1)])
        calls, _ = self.invoke("first", ssl_failure=True)
        self.assertEqual(len(calls), 2)
        ledger = self.root / "HTTP-ledger"
        self.assertEqual(len(list(ledger.glob("*-reserved.json"))), 2)
        self.assertEqual(len(list(ledger.glob("*-finished.json"))), 2)
        receipts = list((self.root / "batches/first/sources/A1").glob("request-result-*.json"))
        errors = [read(p) for p in receipts if read(p).get("error")]
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["error"], "SSLError")
        self.assertFalse(errors[0]["complete"])
        self.assertTrue(errors[0]["HTTP_started"])
        self.assertEqual(
            read(self.root / "batches/first/people/A1/result.json")["status"], "no_usable_source"
        )

    def test_redirect_cycle_is_a_saved_source_failure_not_a_batch_abort(self) -> None:
        self.init()
        self.batch("first", [self.row(1), self.row(2)])
        calls, _ = self.invoke("first", redirect_person="source1.example")
        self.assertEqual(sum(url == "https://source1.example/person" for url in calls), 1)
        rows = read(self.root / "batches/first/result.json")["people"]
        self.assertEqual([r["status"] for r in rows], ["no_usable_source", "candidates"])
        failure = read(next((self.root / "batches/first/failures/A1").glob("*.json")))
        self.assertEqual(failure["error"], "Redirect cycle")
        self.assertEqual(read(Path(failure["receipt_path"]))["status"], 302)


class SourceDeadlineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = AcquisitionTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.current = [datetime.now(UTC)]
        self.deadline = self.current[0] + timedelta(seconds=5)
        self.fixture.scope["deadline_acquisition"] = self.deadline.isoformat()
        self.fixture.init()
        self.url = "https://synthetic.example/source"
        self.loader = PublicLoader(self.root / "source-fixture", [self.url], self.root, "A1")
        self.calls: list[httpx.Request] = []
        self.outer_timeouts: list[float | None] = []

    def request(self, mode: str) -> dict[str, Any]:
        current, deadline = self.current, self.deadline

        class Stream(httpx.AsyncByteStream):
            async def __aiter__(self) -> AsyncIterator[bytes]:
                yield b"first"
                current[0] = deadline
                yield b"late"

        async def wait(url: str, delay: float) -> None:
            if mode == "expired_wait":
                current[0] = deadline
            elif mode == "stop_wait":
                immutable_json(self.root / "stopped.json", {"synthetic_stop": True})
            else:
                current[0] += timedelta(seconds=2)

        def response(request: httpx.Request) -> httpx.Response:
            self.calls.append(request)
            if mode == "expired_stream":
                return httpx.Response(200, stream=Stream(), headers={"content-type": "text/plain"})
            return httpx.Response(200, content=b"synthetic", headers={"content-type": "text/plain"})

        async def invoke() -> dict[str, Any]:
            async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
                return await self.loader.request(client, self.url, "direct_http", 1024)

        original_timeout = asyncio.timeout

        def timeout(delay: float | None) -> asyncio.Timeout:
            self.outer_timeouts.append(delay)
            return original_timeout(delay)

        with (
            patch("sfr_enrichment.sources.datetime") as clock,
            patch(
                "sfr_enrichment.sources.socket.getaddrinfo",
                return_value=[(0, 0, 0, "", ("8.8.8.8", 443))],
            ),
            patch.object(self.loader.budget, "wait", side_effect=wait),
            patch("sfr_enrichment.sources.asyncio.timeout", side_effect=timeout),
        ):
            clock.fromisoformat.side_effect = datetime.fromisoformat
            clock.now.side_effect = lambda tz: current[0]
            return asyncio.run(invoke())

    def receipt(self) -> dict[str, Any]:
        paths = list(self.loader.root.glob("request-result-*.json"))
        self.assertEqual(len(paths), 1)
        self.assertEqual(len(list((self.root / "HTTP-ledger").glob("*-finished.json"))), 1)
        return dict(read(paths[0]))

    def test_expiry_during_rate_wait_never_starts_get_and_preserves_receipt(self) -> None:
        with self.assertRaisesRegex(ValueError, "Acquisition deadline"):
            self.request("expired_wait")
        self.assertEqual(self.calls, [])
        receipt = self.receipt()
        self.assertFalse(receipt["HTTP_started"])
        self.assertFalse(receipt["complete"])
        self.assertEqual(receipt["error"], "ValueError")

    def test_remaining_timeout_bounds_whole_request_and_transport(self) -> None:
        result = self.request("remaining_timeout")
        self.assertTrue(result["complete"])
        self.assertEqual(self.outer_timeouts, [5.0])
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(set(self.calls[0].extensions["timeout"].values()), {3.0})

    def test_stream_crossing_deadline_keeps_only_pre_deadline_bytes(self) -> None:
        with self.assertRaisesRegex(ValueError, "Acquisition deadline"):
            self.request("expired_stream")
        self.assertEqual(len(self.calls), 1)
        receipt = self.receipt()
        self.assertTrue(receipt["HTTP_started"])
        self.assertFalse(receipt["complete"])
        self.assertEqual((self.loader.root / receipt["body_path"]).read_bytes(), b"first")

    def test_stop_during_rate_wait_never_starts_get(self) -> None:
        with self.assertRaisesRegex(ValueError, "STOP"):
            self.request("stop_wait")
        self.assertEqual(self.calls, [])
        self.assertFalse(self.receipt()["HTTP_started"])


class SSLRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = AcquisitionTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root, self.base = self.fixture.root, self.fixture.base
        self.old = code_hashes()
        originals = {}
        for name in RECOVERY_FILES:
            path = self.base / ("old-" + name)
            path.write_text("# synthetic prior runtime " + name)
            self.old[name] = sha(path)
            originals[name] = str(path)

        async def abort_on_second(*args: Any) -> dict[str, Any]:
            root, directory, profile, _, _ = args
            if profile["id"] == "A2":
                reservation = {
                    "author_id": "A2",
                    "url": "https://source2.example/person",
                    "kind": "direct_http",
                    "at": "2026-10-31T00:00:00Z",
                }
                immutable_json(root / "HTTP-ledger/0002-reserved.json", reservation)
                immutable_json(directory / "sources/A2/requests/0002.json", reservation)
                raise ssl.SSLError("synthetic unhandled transport failure")
            return await collect_person(*args)

        with patch("sfr_enrichment.nir_acquisition.code_hashes", return_value=self.old):
            self.fixture.init()
            self.fixture.batch("first", [self.fixture.row(i) for i in (1, 2, 3)])
            with (
                patch("sfr_enrichment.nir_acquisition.collect_person", side_effect=abort_on_second),
                self.assertRaises(ssl.SSLError),
            ):
                self.fixture.invoke("first")
        (self.root / "batches/first/console.log").write_text("SYNTHETIC ssl.SSLError; no real HTTP")
        self.decision: dict[str, Any] = {
            "schema": RECOVERY_SCHEMA,
            "authorization_reference": "synthetic repair authorization",
            "independent_review_reference": "synthetic review only",
            "batch": "first",
            "reserved_ticket": "0002",
            "aborted_author_id": "A2",
            "aborted_queue_index": 1,
            "resume_author_ids": ["A3"],
            "campaign_manifest_sha256": sha(self.root / "manifest.json"),
            "original_code_sha256": self.old,
            "replacement_code_sha256": code_hashes(),
            "preserved_files_sha256": preserved_snapshot(self.root),
            "original_runtime_files": originals,
            "reserved_requests_before": 3,
            "finished_requests_before": 2,
        }
        self.path = self.base / "decision.json"
        immutable_json(self.path, self.decision)

    def test_exact_tail_preserves_old_records_unknown_outcome_and_budgets(self) -> None:
        before = self.decision["preserved_files_sha256"]
        register_ssl_abort(self.root, self.path)
        self.assertEqual(validate_recovery(self.root), self.decision)
        abort = read(self.root / "batches/first/people/A2/result.json")
        self.assertEqual(abort["status"], "technical_abort")
        self.assertIsNone(abort["candidates"])
        self.assertFalse((self.root / "HTTP-ledger/0002-finished.json").exists())
        with self.assertRaisesRegex(ValueError, "already attempted"):
            self.fixture.invoke("first")
        calls, _ = self.fixture.invoke("first", continuation=True)
        self.assertTrue(calls)
        self.assertTrue(all("source3.example" in url for url in calls))
        self.assertEqual(len(list((self.root / "HTTP-ledger").glob("*-reserved.json"))), 5)
        self.assertEqual(len(list((self.root / "HTTP-ledger").glob("*-finished.json"))), 4)
        self.assertTrue(all(sha(self.root / name) == value for name, value in before.items()))
        self.assertEqual(
            [r["status"] for r in read(self.root / "batches/first/result.json")["people"]],
            ["candidates", "technical_abort", "candidates"],
        )
        with self.assertRaisesRegex(ValueError, "already attempted"):
            self.fixture.invoke("first", continuation=True)
        self.fixture.batch("second", [self.fixture.row(4)])
        self.fixture.invoke("second")
        checked(self.root)

    def test_review_exact_tail_ticket_code_and_snapshot_negative_cases(self) -> None:
        changes: list[dict[str, Any]] = [
            {"independent_review_reference": None},
            {"reserved_ticket": "0001"},
            {"resume_author_ids": ["A2", "A3"]},
            {"aborted_queue_index": 2},
            {"reserved_requests_before": 2},
            {"finished_requests_before": 3},
            {"campaign_manifest_sha256": "0" * 64},
            {
                "preserved_files_sha256": {
                    k: v
                    for k, v in self.decision["preserved_files_sha256"].items()
                    if not k.endswith("failure.json")
                }
            },
            {"replacement_code_sha256": self.old},
            {"original_runtime_files": {}},
        ]
        for change in changes:
            with self.subTest(fields=list(change)), self.assertRaises(ValueError):
                validate_recovery_decision(self.root, self.decision | change, initial=True)

    def test_retirement_tampering_and_a_second_unknown_attempt_block(self) -> None:
        register_ssl_abort(self.root, self.path)
        retired = self.root / "HTTP-ledger/0002-retired.json"
        original = retired.read_bytes()
        retired.write_text(json.dumps(read(retired) | {"retry_allowed": True}))
        with self.assertRaisesRegex(ValueError, "Retired outcome"):
            checked(self.root)
        retired.write_bytes(original)
        immutable_json(
            self.root / "HTTP-ledger/0003-reserved.json",
            {
                "author_id": "A3",
                "url": "https://source3.example/unknown",
                "kind": "direct_http",
            },
        )
        with self.assertRaisesRegex(ValueError, "Unfinished HTTP"):
            self.fixture.invoke("first", continuation=True)
        self.assertEqual(len(list((self.root / "HTTP-ledger").glob("*-reserved.json"))), 4)

    def test_no_recovery_without_revision_and_no_second_registration(self) -> None:
        with self.assertRaisesRegex(ValueError, "Frozen acquisition"):
            checked(self.root)
        register_ssl_abort(self.root, self.path)
        with self.assertRaises(ValueError):
            register_ssl_abort(self.root, self.path)
        manifest = self.root / REVISION / "manifest.json"
        manifest.write_text(json.dumps(read(manifest) | {"predecessor_manifest_sha256": "0" * 64}))
        with self.assertRaisesRegex(ValueError, "revision binding"):
            validate_recovery(self.root)

    def test_fabricated_finished_receipt_is_rejected(self) -> None:
        register_ssl_abort(self.root, self.path)
        immutable_json(self.root / "HTTP-ledger/0002-finished.json", {"synthetic_fake": True})
        with self.assertRaisesRegex(ValueError, "finished receipt"):
            checked(self.root)

    def test_non_ssl_error_cannot_be_retired(self) -> None:
        failure = self.root / "batches/first/failure.json"
        failure.write_text(json.dumps(read(failure) | {"error_type": "ValueError"}))
        decision = self.decision | {"preserved_files_sha256": preserved_snapshot(self.root)}
        with self.assertRaisesRegex(ValueError, "SSL transport abort"):
            validate_recovery_decision(self.root, decision, initial=True)


class RedirectRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        v1dir = Path(temporary.name)
        v1hashes = code_hashes()
        runtime_dir = Path(__file__).parents[1] / "src/sfr_enrichment"
        for name in v1hashes:
            if name.endswith(".py"):
                (v1dir / name).write_bytes((runtime_dir / name).read_bytes())
        for name in RECOVERY_FILES:
            (v1dir / name).write_text("# synthetic reviewed v1 runtime " + name)
            v1hashes[name] = sha(v1dir / name)
        self.v1hashes = v1hashes
        self.prior = SSLRecoveryTests()

        async def abort_old_redirect(*args: Any) -> dict[str, Any]:
            root, directory, profile, plan, ids = args
            if profile["id"] != "A5":
                return await collect_person(*args)
            spec = plan["sources"][0]
            loader = CampaignLoader(directory / "sources/A5", [spec["url"]], root, "A5", ids)
            with self.assertRaises(SourceUnavailable):
                await loader.load(spec["url"], kind=spec["kind"])
            # Reproduce only the old uncaught classification after a fully saved 302.
            raise ValueError("Redirect cycle")

        with (
            patch("sfr_enrichment.nir_acquisition.code_hashes", return_value=v1hashes),
            patch("sfr_enrichment.nir_acquisition.__file__", str(v1dir / "nir_acquisition.py")),
        ):
            self.prior.setUp()
            self.addCleanup(self.prior.doCleanups)
            self.fixture, self.root, self.base = (
                self.prior.fixture,
                self.prior.root,
                self.prior.base,
            )
            register_ssl_abort(self.root, self.prior.path)
            self.fixture.invoke("first", continuation=True)
            self.fixture.batch("second", [self.fixture.row(i) for i in (4, 5, 6)])
            with (
                patch(
                    "sfr_enrichment.nir_acquisition.collect_person", side_effect=abort_old_redirect
                ),
                self.assertRaisesRegex(ValueError, "Redirect cycle"),
            ):
                self.fixture.invoke("second", redirect_person="source5.example")
        source_dir = self.root / "batches/second/sources/A5"
        redirect = next(source_dir.glob("redirect-*.json"))
        receipt = next(
            p for p in source_dir.glob("request-result-*.json") if read(p)["status"] == 302
        )
        self.decision: dict[str, Any] = {
            "schema": REDIRECT_SCHEMA,
            "authorization_reference": "synthetic approved repair",
            "independent_review_reference": "synthetic review",
            "batch": "second",
            "predecessor_revision_sha256": sha(self.root / REVISION / "manifest.json"),
            "original_code_sha256": v1hashes,
            "replacement_code_sha256": code_hashes(),
            "preserved_files_sha256": preserved_snapshot(self.root),
            "original_runtime_files": {n: str(v1dir / n) for n in RECOVERY_FILES},
            "aborted_author_id": "A5",
            "aborted_queue_index": 4,
            "resume_author_ids": ["A6"],
            "self_redirect_path": str(redirect.relative_to(self.root)),
            "request_receipt_path": str(receipt.relative_to(self.root)),
            "reserved_requests_before": len(
                list((self.root / "HTTP-ledger").glob("*-reserved.json"))
            ),
            "finished_requests_before": len(
                list((self.root / "HTTP-ledger").glob("*-finished.json"))
            ),
        }
        self.path = self.base / "redirect-decision.json"
        immutable_json(self.path, self.decision)

    def test_second_fixed_revision_preserves_ssl_and_runs_only_tail(self) -> None:
        before = self.decision["preserved_files_sha256"]
        register_redirect_cycle(self.root, self.path)
        self.assertEqual(validate_redirect_recovery(self.root), self.decision)
        self.assertEqual(validate_recovery(self.root)["reserved_ticket"], "0002")
        calls, _ = self.fixture.invoke("second", redirect_continuation=True)
        self.assertTrue(calls)
        self.assertTrue(all("source6.example" in url for url in calls))
        self.assertTrue(all(sha(self.root / name) == digest for name, digest in before.items()))
        abort = read(self.root / "batches/second/people/A5/result.json")
        self.assertEqual(abort["reason"], "redirect_cycle_source_abort_no_retry")
        self.assertIsNone(abort["candidates"])
        self.assertEqual(len(list((self.root / "HTTP-ledger").glob("*-retired.json"))), 1)
        self.fixture.batch("third", [self.fixture.row(7)])
        self.fixture.invoke("third")
        checked(self.root)
        with self.assertRaisesRegex(ValueError, "already attempted"):
            self.fixture.invoke("second", redirect_continuation=True)

    def test_wrong_revision_tail_receipt_or_extra_unknown_is_rejected(self) -> None:
        changes: list[dict[str, Any]] = [
            {"independent_review_reference": None},
            {"predecessor_revision_sha256": "0" * 64},
            {"original_code_sha256": code_hashes()},
            {"resume_author_ids": ["A5", "A6"]},
            {"aborted_queue_index": 5},
            {"reserved_requests_before": 0},
            {"request_receipt_path": self.decision["self_redirect_path"]},
        ]
        for change in changes:
            with self.subTest(fields=list(change)), self.assertRaises((ValueError, KeyError)):
                validate_redirect_decision(self.root, self.decision | change, initial=True)
        immutable_json(
            self.root / "HTTP-ledger/9999-reserved.json",
            {"author_id": "A5", "url": "https://synthetic.example/unknown", "kind": "direct_http"},
        )
        extra = self.decision | {
            "preserved_files_sha256": preserved_snapshot(self.root),
            "reserved_requests_before": self.decision["reserved_requests_before"] + 1,
        }
        with self.assertRaisesRegex(ValueError, "additional unknown"):
            validate_redirect_decision(self.root, extra, initial=True)

    def test_predecessor_or_abort_proof_cannot_be_rewritten(self) -> None:
        register_redirect_cycle(self.root, self.path)
        proof = self.root / REDIRECT_REVISION / "abort.json"
        proof.write_text(json.dumps(read(proof) | {"candidate_outcome": "no_email"}))
        with self.assertRaisesRegex(ValueError, "abort proof"):
            checked(self.root)


if __name__ == "__main__":
    unittest.main()
