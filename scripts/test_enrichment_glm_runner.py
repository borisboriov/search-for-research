"""Offline source boundaries and lossless comparison projection."""

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

from enrichment_contact_first import digest
from enrichment_experiment import sha
from enrichment_glm_compare import compact, legacy_pdf_text
from enrichment_glm_tools import SourceHost, search_links
from enrichment_verification import immutable_json


class GLMRunnerTests(unittest.TestCase):
    def test_search_requires_actual_title_link_rows_not_snippets(self) -> None:
        raw = {
            "message": {
                "result": {
                    "content": [
                        {
                            "text": json.dumps(
                                [
                                    {"title": "Institute", "link": "https://example.org/"},
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

    def test_live_gets_only_known_orcid_and_cannot_open_guessed_page(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch("enrichment_glm_tools.read", side_effect=AssertionError("baseline leak")):
                host = SourceHost(root, {"id": "A1", "orcid": "0000-0002-2614-0146"}, "live")
            self.assertEqual(
                list(host.allowed), ["https://pub.orcid.org/v3.0/0000-0002-2614-0146/record"]
            )
            with patch("enrichment_glm_tools.PublicLoader") as loader:
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
            with patch("enrichment_glm_tools.PublicLoader") as loader:
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
            with patch("enrichment_glm_compare.checked_source", return_value=(text, text)):
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
                patch("enrichment_glm_compare.checked_source", return_value=(text, text)),
                self.assertRaisesRegex(ValueError, "quote changed"),
            ):
                compact(inp)

    def test_historical_parser_refuses_fresh_pdf_before_subprocess(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            immutable_json(root / "manifest.json", {"baseline_pdf_body_sha256": []})
            with patch("enrichment_glm_compare.subprocess.run") as run:
                with self.assertRaisesRegex(ValueError, "cannot process a new PDF"):
                    legacy_pdf_text(root, b"%PDF-new")
                run.assert_not_called()

    def test_public_search_challenge_stops_domain_and_is_not_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = SourceHost(root, {"id": "A1"}, "live")
            with (
                patch("enrichment_glm_tools.PublicLoader") as loader,
                patch("enrichment_glm_tools.checked_source", return_value=("challenge-form", "")),
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

    def test_replay_has_no_live_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            immutable_json(root / "manifest.json", {"baseline_root": str(root / "fixtures")})
            host = SourceHost(root, {"id": "A1", "orcid": "0000-0002-2614-0146"}, "replay")
            with patch("enrichment_glm_tools.PublicLoader") as loader:
                with self.assertRaisesRegex(ValueError, "no live fallback"):
                    asyncio.run(host.source(next(iter(host.allowed))))
                loader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
