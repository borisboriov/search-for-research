"""Synthetic acquisition-only tests: MockTransport, no live HTTP or model calls."""

import asyncio
import fcntl
import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx

from sfr_enrichment.common import read
from sfr_enrichment.evidence import immutable_json
from sfr_enrichment.nir_acquisition import MAXIMA, initialize, prepare, run


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
        self, name: str, *, body: str | None = None, status: int = 200
    ) -> tuple[list[str], AsyncMock]:
        calls: list[str] = []

        def response(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            if request.url.path == "/robots.txt":
                return httpx.Response(
                    200, text="User-agent: *\nAllow: /", headers={"content-type": "text/plain"}
                )
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


if __name__ == "__main__":
    unittest.main()
