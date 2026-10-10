"""Отказы доступа, seals и извлечение атрибутов: полностью офлайн."""

import asyncio
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import httpx
from enrichment_contact_first import (
    ContactsHTML,
    Loader,
    check_contact_input,
    checked_source,
    collect_fallback,
    contact_packet,
    prepare_contact_input,
    verify_contact_input,
)
from enrichment_experiment import public_candidates

URL = "https://university.example/person/1"
HTML = "<h1>Jane Researcher</h1><p>University / plasma</p>"


class ContactFirstTests(unittest.TestCase):
    def run_source(
        self, root: Path, body: str, *, status: int = 200, robots_status: int = 200
    ) -> dict[str, Any]:
        client = httpx.AsyncClient

        def response(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/robots.txt":
                return httpx.Response(
                    robots_status,
                    text="User-agent: *\nAllow: /",
                    headers={"content-type": "text/plain"},
                )
            return httpx.Response(
                status, text=body, headers={"content-type": "text/html;charset=utf-8"}
            )

        transport = httpx.MockTransport(response)
        with (
            patch(
                "enrichment_contact_first.httpx.AsyncClient",
                side_effect=lambda **kw: client(transport=transport, **kw),
            ),
            patch("enrichment_contact_first.Budget.wait", new_callable=AsyncMock),
        ):
            return asyncio.run(Loader(root, [URL]).load(URL))

    def test_mailto_image_parameter_and_visible_text_are_distinct_quotes(self) -> None:
        html = (
            HTML + '<a href="mailto:jane%40example.edu">Email</a>'
            '<img src="/mail.php?mail=other%40example.edu"><p>footer@example.edu</p>'
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.run_source(root, html)
            packet = contact_packet(root, {"id": "a"}, [source])
            self.assertEqual(
                [p["value"] for p in packet["items"]],
                ["jane@example.edu", "other@example.edu", "footer@example.edu"],
            )
            self.assertTrue(all(p["field"] == "personal_contact" for p in packet["items"]))
            for row in packet["evidence_pool"].values():
                body = (
                    html
                    if row["representation"].startswith("html_")
                    else checked_source(root, source)[1]
                )
                self.assertEqual(body[row["start"] : row["end"]], row["excerpt"])
                self.assertEqual(row["source_kind"], "direct_http")
            self.assertEqual(packet["profile_evidence"]["current_affiliation"], [])
            self.assertFalse(packet["provenance"]["model_called"])

    def test_third_party_image_and_arbitrary_parameter_not_contact(self) -> None:
        parser = ContactsHTML(URL)
        parser.feed(
            '<img src="https://tracker.example/mail.php?mail=other@example.edu">'
            '<img src="/image?tracking=other@example.edu">'
        )
        self.assertEqual(parser.image_contacts, [])

    def test_sealed_source_rejects_changed_text_and_url(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.run_source(root, HTML)
            with self.assertRaises(ValueError):
                checked_source(root, source | {"url": URL + "/forged"})
            (root / source["text_path"]).write_text("changed")
            with self.assertRaisesRegex(ValueError, "отпечаток"):
                checked_source(root, source)

    def test_saved_source_cache_needs_no_network(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.run_source(root, HTML)
            with patch(
                "enrichment_contact_first.httpx.AsyncClient", side_effect=AssertionError("network")
            ):
                self.assertEqual(asyncio.run(Loader(root, [URL]).load(URL)), source)
            self.assertEqual(len(list((root / "requests").glob("*.json"))), 2)

    def test_crlf_in_source_is_not_normalized_before_seal_check(self) -> None:
        html = HTML + '<p>line1\r\nline2</p><a href="mailto:jane@example.edu">Email</a>'
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.run_source(root, html)
            decoded, _ = checked_source(root, source)
            self.assertEqual(decoded, html)
            self.assertEqual(len(contact_packet(root, {"id": "a"}, [source])["items"]), 1)

    def test_missing_robots_404_permits_but_failures_and_login_do_not(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = self.run_source(Path(temp), HTML, robots_status=404)
            self.assertEqual(source["robots_status"], 404)
            self.assertIn("robots_missing", source["robots_basis"])
        for status in (301, 401, 403, 429, 500):
            with tempfile.TemporaryDirectory() as temp, self.assertRaises(ValueError):
                self.run_source(Path(temp), HTML, robots_status=status)

    def test_redirect_rejected_without_followup_or_empty_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(ValueError, "HTTP200"):
                self.run_source(root, HTML, status=301)
            self.assertFalse(list(root.glob("source-*.json")))
            self.assertEqual(len(list((root / "requests").glob("*.json"))), 2)
            self.assertTrue(any(p.stat().st_size == 0 for p in root.glob("body-*.bin")))

    def test_403_persists_and_prevents_new_network_request(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(ValueError):
                self.run_source(root, "blocked", status=403)
            client = httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda r: (_ for _ in ()).throw(AssertionError("network"))
                )
            )
            try:
                with self.assertRaisesRegex(ValueError, "403/429"):
                    asyncio.run(Loader(root, [URL]).request(client, URL, "direct_http", 100))
            finally:
                asyncio.run(client.aclose())

    def test_unfinished_reservation_cannot_retry(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            from enrichment_verification import immutable_json

            root = Path(temp)
            (root / "requests").mkdir()
            immutable_json(root / "requests" / "01.json", {"url": URL, "kind": "direct_http"})
            client = httpx.AsyncClient()
            try:
                with self.assertRaisesRegex(ValueError, "автоматический повтор"):
                    asyncio.run(Loader(root, [URL]).request(client, URL, "direct_http", 100))
            finally:
                asyncio.run(client.aclose())

    def test_public_orcid_case_and_absence_is_not_global_contact_absence(self) -> None:
        record = {
            "person": {
                "emails": {
                    "email": [
                        {"email": "jane@example.edu", "visibility": "PUBLIC"},
                        {"email": "private@example.edu", "visibility": "LIMITED"},
                    ]
                },
                "researcher-urls": {
                    "researcher-url": [
                        {"url": {"value": URL}, "visibility": "PUBLIC"},
                        {"url": {"value": URL + "/private"}, "visibility": "private"},
                    ]
                },
            }
        }
        result = public_candidates(record)
        self.assertEqual(len(result["emails"]), 1)
        self.assertEqual(len(result["links"]), 1)
        self.assertEqual(result["identity_verdict"], "not_checked")

    def test_semantic_input_cannot_change_candidate_or_source_after_prepare(self) -> None:
        import json

        from enrichment_experiment import sha
        from enrichment_verification import immutable_json

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source_root = root / "sources"
            profile = {"id": "a"}
            immutable_json(root / "sample.json", [profile])
            immutable_json(root / "manifest.json", {"sample_sha256": sha(root / "sample.json")})
            source = self.run_source(
                source_root, HTML + '<a href="mailto:jane@example.edu">Email</a>'
            )
            path = prepare_contact_input(root, profile, source_root, [source])
            task = check_contact_input(root, path)
            self.assertEqual(len(task["items"]), 1)
            task["items"][0]["value"] = "invented@example.edu"
            path.write_text(json.dumps(task))
            with self.assertRaisesRegex(ValueError, "frozen"):
                check_contact_input(root, path)

    def test_quota_stop_never_reaches_native_execution(self) -> None:
        for value in (15, 0, float("nan")):
            with self.assertRaisesRegex(ValueError, "GPT jobs"):
                verify_contact_input(
                    Path("/missing"), Path("/missing/input"), remaining_percent=value
                )

    def test_authorized_manifest_quota_floor_and_legacy_default(self) -> None:
        from enrichment_verification import immutable_json

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for value in (5, 0, float("nan")):
                immutable = root / str(value)
                immutable.mkdir()
                immutable_json(immutable / "manifest.json", {"remaining_stop": 5})
                with self.assertRaisesRegex(ValueError, "≤5%"):
                    verify_contact_input(immutable, immutable / "input", remaining_percent=value)
                with self.assertRaisesRegex(ValueError, "≤5%"):
                    collect_fallback(
                        immutable, {"id": "a"}, remaining_percent=value, stopped_domains=[]
                    )
            allowed = root / "allowed"
            allowed.mkdir()
            immutable_json(allowed / "manifest.json", {"remaining_stop": 5})
            with (
                patch(
                    "enrichment_contact_first.check_contact_input", side_effect=RuntimeError("gate")
                ),
                self.assertRaisesRegex(RuntimeError, "gate"),
            ):
                verify_contact_input(allowed, allowed / "input", remaining_percent=6)
            with self.assertRaisesRegex(ValueError, "≤15%"):
                verify_contact_input(root, root / "input", remaining_percent=6)
            for floor in (-1, 1, 4, 6, True):
                invalid = root / ("floor" + str(floor))
                invalid.mkdir()
                immutable_json(invalid / "manifest.json", {"remaining_stop": floor})
                with self.assertRaisesRegex(ValueError, "Неподдерживаемый"):
                    verify_contact_input(invalid, invalid / "input", remaining_percent=18)

    def test_stopped_parent_prevents_new_HTTP_and_model_jobs(self) -> None:
        from enrichment_verification import immutable_json

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            immutable_json(root / "stopped.json", {"reason": "done"})
            loader = Loader(root / "profile", [URL])
            client = httpx.AsyncClient()
            try:
                with self.assertRaisesRegex(ValueError, "STOP root"):
                    asyncio.run(loader.request(client, URL, "direct_http", 100))
            finally:
                asyncio.run(client.aclose())
            with self.assertRaisesRegex(ValueError, "STOP root"):
                verify_contact_input(root / "attemptN", root / "absent.json", remaining_percent=19)

    def test_parent_STOP_prevents_fallback_before_batch_or_Pi(self) -> None:
        from enrichment_verification import immutable_json

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            immutable_json(root / "stopped.json", {"reason": "done"})
            with (
                patch("enrichment_batch.Batch.create") as create,
                patch("enrichment_night.collect") as collect,
                self.assertRaisesRegex(ValueError, "STOP root"),
            ):
                collect_fallback(
                    root / "attemptN", {"id": "a"}, remaining_percent=19, stopped_domains=[]
                )
            create.assert_not_called()
            collect.assert_not_called()

    def test_parent_STOP_prevents_direct_collector_before_workspace(self) -> None:
        from datetime import UTC, datetime, timedelta

        from enrichment_night import collect
        from enrichment_verification import immutable_json

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            immutable_json(root / "stopped.json", {"reason": "done"})
            for deadline in (None, datetime.now(UTC) + timedelta(minutes=10)):
                with (
                    patch("enrichment_night.require_access") as access,
                    self.assertRaisesRegex(ValueError, "STOP root"),
                ):
                    collect(root / "attemptN", {"id": "a"}, Mock(), hard_stop=deadline)
                access.assert_not_called()
                self.assertFalse((root / "attemptN").exists())

    def test_daytime_deadline_cannot_resume_legacy_or_stopped_root(self) -> None:
        from datetime import UTC, datetime, timedelta

        from enrichment_night import collect
        from enrichment_verification import immutable_json

        deadline = datetime.now(UTC) + timedelta(minutes=10)
        for stopped in (False, True):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                immutable_json(
                    root / "manifest.json",
                    {
                        "method": "contact-first-v1" if stopped else "enrichment-cli-early-read-v6",
                        "fallback_deadline": deadline.isoformat(),
                    },
                )
                if stopped:
                    immutable_json(root / "stopped.json", {"reason": "done"})
                with self.assertRaisesRegex(
                    ValueError, "STOP root" if stopped else "нового contact-first"
                ):
                    collect(root, {"id": "a"}, Mock(), hard_stop=deadline)


if __name__ == "__main__":
    unittest.main()
