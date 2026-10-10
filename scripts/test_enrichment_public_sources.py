"""Офлайн: observed links, API policy, общий бюджет и literal source seals."""

import asyncio
import shutil
import socket
import tempfile
import unittest
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
from enrichment_compare_loading import extract
from enrichment_contact_first import check_quota, checked_source, contact_packet, digest
from enrichment_public_sources import (
    MATHNET_DECODER,
    PublicLoader,
    observed_links,
    render_mathnet_contacts,
)
from enrichment_verification import immutable_bytes, immutable_json

URL = "https://university.example/person"
API = "https://pub.orcid.org/v3.0/0000-0002-2614-0146/record"
PUBLIC = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]


class PublicSourceTests(unittest.TestCase):
    def prepare(self, root: Path, *, total: int = 20, per: int = 10) -> None:
        immutable_json(
            root / "manifest.json",
            {
                "HTTP_total_cap": total,
                "HTTP_per_profile_cap": per,
                "deadline_acquisition": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
            },
        )
        immutable_json(
            root / "official-ORCID-policy.json",
            {
                "source": "https://pub.orcid.org/v3.0",
                "access": "allowed",
            },
        )

    def load(
        self,
        root: Path,
        responder: Callable[[httpx.Request], httpx.Response],
        url: str = URL,
        kind: str = "direct_http",
    ) -> dict[str, Any]:
        client = httpx.AsyncClient
        with (
            patch(
                "enrichment_public_sources.httpx.AsyncClient",
                side_effect=lambda **kw: client(transport=httpx.MockTransport(responder), **kw),
            ),
            patch("enrichment_public_sources.socket.getaddrinfo", return_value=PUBLIC),
            patch("enrichment_compare_loading.Budget.wait", new_callable=AsyncMock),
        ):
            return asyncio.run(
                PublicLoader(root / "sources", [url], root, "a").load(url, kind=kind)
            )

    def test_links_preserve_literal_parent_and_reject_foreign_base_interpretation(self) -> None:
        body = '<a href="/p?x=1&amp;y=2"><b>Jane</b> Doe</a><a href="javascript:foo">x</a>'
        rows = observed_links(URL, body)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["url"], "https://university.example/p?x=1&y=2")
        self.assertEqual(rows[0]["anchor"], "Jane Doe")
        self.assertIn(rows[0]["start_tag"], body)
        self.assertEqual(observed_links(URL, '<base href="https://other.example">' + body), [])

    def test_manual_redirect_records_exact_destination_and_literal_source(self) -> None:
        calls = []

        def respond(req: httpx.Request) -> httpx.Response:
            calls.append(str(req.url))
            if req.url.path == "/robots.txt":
                return httpx.Response(
                    200, text="User-agent: *\nAllow: /", headers={"content-type": "text/plain"}
                )
            if req.url.path == "/person":
                return httpx.Response(302, headers={"location": "/people/jane"})
            return httpx.Response(
                200,
                text='<h1>Jane Doe</h1><a href="mailto:jane@example.edu">Email</a>',
                headers={"content-type": "text/html"},
            )

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.prepare(root)
            source = self.load(root, respond)
            self.assertEqual(
                calls,
                [
                    "https://university.example/robots.txt",
                    URL,
                    "https://university.example/people/jane",
                ],
            )
            self.assertEqual(source["url"], calls[-1])
            packet = contact_packet(root / "sources", {"id": "a"}, [source])
            self.assertEqual(packet["items"][0]["value"], "jane@example.edu")
            self.assertEqual(len(list((root / "HTTP-ledger").glob("*-reserved.json"))), 3)
            (root / "sources" / source["text_path"]).write_text("changed")
            with self.assertRaises(ValueError):
                checked_source(root / "sources", source)

    def test_public_API_uses_official_policy_and_no_HTML_robots(self) -> None:
        calls = []

        def respond(req: httpx.Request) -> httpx.Response:
            calls.append(str(req.url))
            return httpx.Response(
                200,
                json={
                    "person": {
                        "name": {"given-names": {"value": "Jane"}},
                        "emails": {
                            "email": [{"email": "jane@example.edu", "visibility": "PUBLIC"}]
                        },
                    }
                },
            )

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.prepare(root)
            source = self.load(root, respond, API, "structured_orcid")
            self.assertEqual(calls, [API])
            self.assertEqual(source["robots_basis"], "official_public_API_policy")
            packet = contact_packet(root / "sources", {"id": "a"}, [source])
            self.assertEqual(len(packet["profile_evidence"]["identity"]), 2)
            self.assertEqual(packet["items"][0]["value"], "jane@example.edu")
            (root / "official-ORCID-policy.json").unlink()
            with self.assertRaises(FileNotFoundError):
                self.load(root, respond, API, "structured_orcid")

    def test_shared_per_author_budget_and_STOP_reserve_before_network(self) -> None:
        for mode in ("total", "author", "stop"):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.prepare(
                    root, total=0 if mode == "total" else 20, per=0 if mode == "author" else 10
                )
                if mode == "stop":
                    immutable_json(root / "stopped.json", {"status": "STOP"})
                with self.assertRaises(ValueError):
                    self.load(root, lambda req: (_ for _ in ()).throw(AssertionError("network")))
                self.assertFalse(list((root / "HTTP-ledger").glob("*-reserved.json")))

    def test_private_IP_and_protection_location_refuse_without_followup(self) -> None:
        def respond(req: httpx.Request) -> httpx.Response:
            if req.url.path == "/robots.txt":
                return httpx.Response(404)
            return httpx.Response(302, headers={"location": "/captcha"})

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.prepare(root)
            with self.assertRaisesRegex(ValueError, "Protection"):
                self.load(root, respond)
            self.assertEqual(len(list((root / "HTTP-ledger").glob("*-reserved.json"))), 2)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.prepare(root)
            with patch(
                "enrichment_public_sources.socket.getaddrinfo",
                return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))],
            ):
                loader = PublicLoader(root / "sources", [URL], root, "a")

                async def run() -> dict[str, Any]:
                    async with httpx.AsyncClient(
                        transport=httpx.MockTransport(
                            lambda req: (_ for _ in ()).throw(AssertionError("network"))
                        )
                    ) as client:
                        return await loader.request(client, URL, "direct_http", 100)

                result = asyncio.run(run())
            self.assertFalse(result["HTTP_started"])

    def test_no_quota_reserve_applies_only_manifest_choice_legacy_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            immutable_json(root / "manifest.json", {"remaining_stop": 0})
            check_quota(root, 0, "verify")
            check_quota(root, 13, "verify")
        with tempfile.TemporaryDirectory() as temp, self.assertRaises(ValueError):
            check_quota(Path(temp), 13, "verify")

    def test_public_decoder_derivation_is_reproducible_and_tamper_blocks(self) -> None:
        rendered = '<a href="mailto:jane@example.edu">jane@example.edu</a>'
        encoded = "".join(chr(65 + ord(c) // 16) + chr(65 + ord(c) % 16) for c in rendered)
        tag = '<script src="/js/func_string.js?v=8.7"></script>'
        body = (
            "<h1>Jane Doe</h1>"
            + tag
            + ("<script>document.write(decode_email('" + encoded + "'));</script>")
        )
        js_bytes = MATHNET_DECODER.encode()
        self.assertIn(rendered, render_mathnet_contacts(body, js_bytes))
        with self.assertRaises(ValueError):
            render_mathnet_contacts(body, js_bytes.replace(b"16", b"15"))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.prepare(root)
            source = self.load(
                root,
                lambda req: httpx.Response(
                    404 if req.url.path == "/robots.txt" else 200,
                    text=body,
                    headers={"content-type": "text/html"},
                ),
            )
            original = root / "sources" / f"source-{digest(URL.encode())}.json"
            target = root / "rendered"
            shutil.copytree(root / "sources", target)
            (target / original.name).unlink()
            js_path = root / "decoder-receipt.json"
            immutable_bytes(root / "decoder.js", js_bytes)
            immutable_json(
                js_path,
                {
                    "url": "https://university.example/js/func_string.js?v=8.7",
                    "status": 200,
                    "complete": True,
                    "content_type": "application/javascript",
                    "body_path": "decoder.js",
                    "body_sha256": digest(js_bytes),
                },
            )
            static = extract(render_mathnet_contacts(body, js_bytes), URL)["text"]
            (target / source["text_path"]).write_text(static)
            derived = source | {
                "rendering_method": "mathnet-email-v1",
                "parent_source_path": str(original),
                "parent_source_sha256": digest(original.read_bytes()),
                "decoder_receipt_path": str(js_path),
                "decoder_receipt_sha256": digest(js_path.read_bytes()),
                "decoder_literal_tag": tag,
                "decoder_literal_src": "/js/func_string.js?v=8.7",
                "text_sha256": digest(static.encode()),
            }
            immutable_json(target / original.name, derived)
            packet = contact_packet(target, {"id": "a"}, [derived], candidate_cap=32)
            self.assertEqual(packet["items"][0]["value"], "jane@example.edu")
            (root / "decoder.js").write_bytes(b"changed")
            with self.assertRaises(ValueError):
                checked_source(target, derived)
