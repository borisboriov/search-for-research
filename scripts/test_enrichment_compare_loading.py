"""Бюджет, fail-closed правила источников и пределы диагностики загрузки."""

import unittest

from enrichment_compare_loading import Budget, extract, policy


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
