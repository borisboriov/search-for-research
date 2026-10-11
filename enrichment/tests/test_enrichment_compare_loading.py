"""Бюджет, fail-closed правила источников и пределы диагностики загрузки."""

import asyncio
import importlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

from sfr_enrichment_legacy.enrichment_compare_loading import (
    Budget,
    DomainStops,
    extract,
    policy,
    run,
)


class LoadingTests(unittest.TestCase):
    def test_attempt_limit_and_methods(self) -> None:
        budget = Budget()
        budget.reserve("httpx", "https://example.org/a")
        budget.reserve("httpx", "https://example.org/a")
        with self.assertRaises(ValueError):
            budget.reserve("httpx", "https://example.org/a")
        budget.reserve("robots", "https://example.org/robots.txt")
        with self.assertRaises(ValueError):
            budget.reserve("robots", "https://example.org/robots.txt")
        with self.assertRaises(ValueError):
            budget.reserve("browser", "https://example.org/a")

    def test_domain_stop_survives_restart_and_blocks_other_paths(self) -> None:
        for status in (403, 429):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                stops = DomainStops(root)
                stops.observe("https://example.org/a", status)
                self.assertTrue(stops.blocked("https://example.org/b"))
                self.assertFalse(stops.blocked("https://other.org/a"))
                restarted = DomainStops(root)
                self.assertTrue(restarted.blocked("https://example.org/robots.txt"))
                restarted.observe("https://example.org/b", status)
                self.assertEqual(len(list(root.glob("domain-stop-*.json"))), 1)

    def test_live_loop_stops_second_method_and_same_domain_url(self) -> None:
        calls = []

        class Client:
            async def __aenter__(self) -> Any:
                return self

            async def __aexit__(self, *args: Any) -> None:
                return None

            async def get(self, url: str) -> SimpleNamespace:
                calls.append(url)
                if url.endswith("robots.txt"):
                    return SimpleNamespace(status_code=200, text="User-agent: *\nAllow: /")
                return SimpleNamespace(status_code=403, text="Forbidden")

        class Strategy(Client):
            async def crawl(self, *args: Any, **kwargs: Any) -> None:
                raise AssertionError("Crawl4AI must not request a stopped domain")

        real_import = importlib.import_module

        def module(name: str) -> Any:
            if name == "sfr_core.settings":
                return SimpleNamespace(
                    Settings=lambda **kw: SimpleNamespace(openalex_mailto="test@example.org")
                )
            if name == "crawl4ai.async_crawler_strategy":
                return SimpleNamespace(AsyncHTTPCrawlerStrategy=lambda **kw: Strategy())
            if name == "crawl4ai.async_configs":
                return SimpleNamespace(
                    HTTPCrawlerConfig=lambda **kw: None, CrawlerRunConfig=lambda **kw: None
                )
            if name == "crawl4ai.markdown_generation_strategy":
                return SimpleNamespace(DefaultMarkdownGenerator=lambda: None)
            return real_import(name)

        with (
            tempfile.TemporaryDirectory() as temporary,
            patch(
                "sfr_enrichment_legacy.enrichment_compare_loading.importlib.import_module",
                side_effect=module,
            ),
            patch(
                "sfr_enrichment_legacy.enrichment_compare_loading.httpx.AsyncClient",
                return_value=Client(),
            ),
            patch("sfr_enrichment_legacy.enrichment_compare_loading.Budget.wait", new=AsyncMock()),
            patch(
                "sfr_enrichment_legacy.enrichment_compare_loading.URLS",
                ("https://example.org/a", "https://example.org/b"),
            ),
        ):
            summary = asyncio.run(run(Path(temporary), Path("unused")))
        self.assertEqual(calls, ["https://example.org/robots.txt", "https://example.org/a"])
        self.assertEqual(
            [row["status"] for row in summary["rows"]],
            ["http_failure", "domain_stopped", "domain_stopped", "domain_stopped"],
        )

    def test_crawl_stop_precedes_unavailable_markdown(self) -> None:
        calls = []

        class Client:
            async def __aenter__(self) -> Any:
                return self

            async def __aexit__(self, *args: Any) -> None:
                return None

            async def get(self, url: str) -> SimpleNamespace:
                calls.append(url)
                if url.endswith("robots.txt"):
                    return SimpleNamespace(status_code=200, text="User-agent: *\nAllow: /")
                return SimpleNamespace(status_code=200, text="<p>ok</p>")

        class Strategy(Client):
            async def crawl(self, url: str, **kwargs: Any) -> SimpleNamespace:
                calls.append("crawl:" + url)
                return SimpleNamespace(status_code=429, html="Forbidden")

        real_import = importlib.import_module

        def module(name: str) -> Any:
            if name == "sfr_core.settings":
                return SimpleNamespace(
                    Settings=lambda **kw: SimpleNamespace(openalex_mailto="test@example.org")
                )
            if name == "crawl4ai.async_crawler_strategy":
                return SimpleNamespace(AsyncHTTPCrawlerStrategy=lambda **kw: Strategy())
            if name == "crawl4ai.async_configs":
                return SimpleNamespace(
                    HTTPCrawlerConfig=lambda **kw: None, CrawlerRunConfig=lambda **kw: None
                )
            if name == "crawl4ai.markdown_generation_strategy":
                return SimpleNamespace(DefaultMarkdownGenerator=lambda: None)
            return real_import(name)

        with (
            tempfile.TemporaryDirectory() as temporary,
            patch(
                "sfr_enrichment_legacy.enrichment_compare_loading.importlib.import_module",
                side_effect=module,
            ),
            patch(
                "sfr_enrichment_legacy.enrichment_compare_loading.httpx.AsyncClient",
                return_value=Client(),
            ),
            patch("sfr_enrichment_legacy.enrichment_compare_loading.Budget.wait", new=AsyncMock()),
            patch(
                "sfr_enrichment_legacy.enrichment_compare_loading.URLS",
                ("https://example.org/a", "https://example.org/b"),
            ),
        ):
            summary = asyncio.run(run(Path(temporary), Path("unused")))
        self.assertEqual(
            calls,
            [
                "https://example.org/robots.txt",
                "https://example.org/a",
                "crawl:https://example.org/a",
            ],
        )
        self.assertEqual(
            [row["status"] for row in summary["rows"]],
            ["ok", "http_failure", "domain_stopped", "domain_stopped"],
        )

    def test_policy_unknown_is_not_permission(self) -> None:
        self.assertEqual(policy("", "https://example.org/a", 503), (False, 1))
        self.assertEqual(
            policy("User-agent: *\nDisallow: /", "https://example.org/a", 200), (False, 1)
        )
        self.assertEqual(
            policy("User-agent: *\nAllow: /\nCrawl-delay: 3", "https://example.org/a", 200),
            (True, 3),
        )

    def test_wildcard_query_does_not_disallow_plain_path(self) -> None:
        robots = "User-agent: *\nDisallow: *?\nAllow: *?page=\nDisallow: /private/"
        self.assertEqual(policy(robots, "https://example.org/a", 200), (True, 1))
        self.assertEqual(policy(robots, "https://example.org/a?tag=x", 200), (False, 1))
        self.assertEqual(policy(robots, "https://example.org/a?page=1", 200), (True, 1))
        self.assertEqual(policy(robots, "https://example.org/private/a", 200), (False, 1))

    def test_extraction_does_not_claim_zero_fixture_quality(self) -> None:
        result = extract('<p>2022 content</p><a href="/a.pdf">PDF</a>', "https://example.org/page")
        self.assertEqual(result["year_tokens"], ["2022"])
        self.assertEqual(result["attachment_links"], ["https://example.org/a.pdf"])
        self.assertEqual(result["attachment_contents_status"], "not_tested")
        self.assertEqual(result["table_quality_status"], "no_fixture")
        self.assertIsNone(result["human_review_minutes"])
        self.assertFalse(result["text_completeness_reviewed"])


if __name__ == "__main__":
    unittest.main()
