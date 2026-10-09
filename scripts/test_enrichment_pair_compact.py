"""Отдельное представление сохраняет дословные цитаты и механизм разметки."""

import html
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from enrichment_experiment import read, sha, write_new
from enrichment_pair_compact import QuoteSpans, render, transform


class CompactTests(unittest.TestCase):
    def source(self, quote: str = "A & B <tag> " * 100) -> str:
        escaped = html.escape(quote)
        return (
            '<!doctype html><html><meta charset="utf-8"><article><h2>Человек</h2>'
            '<a href="https://example.org/source?a=1&amp;b=2">Источник</a>'
            "<p>Дата сведений: 2022. Дата проверки: 2026.</p>"
            f'<div class="proof"><blockquote>{escaped}</blockquote></div>'
            "<p>Вопрос: принадлежит ли вам ORCID?</p>"
            '<select data-key="same"><option value="">Не просмотрено</option></select>'
            '</article><script>const cfg={packet_sha256:"original"};'
            'function save(){return "A/B";}</script></html>'
        )

    def test_long_quote_escaped_and_script_are_exactly_preserved(self) -> None:
        original = self.source()
        result, stats = transform(original)
        before, after = QuoteSpans(original), QuoteSpans(result)
        before.finish()
        after.finish()
        self.assertEqual(before.scripts, after.scripts)
        self.assertEqual(
            [original[a:b] for a, b in before.quotes], [result[a:b] for a, b in after.quotes]
        )
        self.assertEqual(stats["collapsed_quote_count"], 1)
        self.assertIn("&amp; B &lt;tag&gt;", result)
        self.assertIn("не отвечать от имени учёного", result)
        self.assertIn('<select data-key="same">', result)
        self.assertIn("Дата сведений: 2022. Дата проверки: 2026.", result)
        self.assertIn('href="https://example.org/source?a=1&amp;b=2"', result)
        self.assertIn("Вопрос: принадлежит ли вам ORCID?", result)

    def test_short_first_quote_visible_but_repeat_is_collapsed(self) -> None:
        source = self.source("Короткая точная цитата")
        source = source.replace(
            "</article>", "<blockquote>Короткая точная цитата</blockquote></article>"
        )
        result, stats = transform(source)
        self.assertEqual(stats["quote_count"], 2)
        self.assertEqual(stats["collapsed_quote_count"], 1)
        self.assertEqual(stats["repeated_collapsed_quote_count"], 1)
        self.assertIn("повтор источника", result)

    def test_output_is_immutable_and_originals_unchanged(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            packet = root / "paired-human/packets/packet1"
            packet.mkdir(parents=True)
            page = packet / "cards.html"
            page.write_text(self.source())
            manifest = packet / "manifest.json"
            write_new(
                manifest,
                {
                    "schema": "paired_human_packet_v1",
                    "packet_id": "packet1",
                    "human_reviewed": False,
                },
            )
            original_shas = (sha(page), sha(manifest))
            output = render(root, "packet1")
            self.assertEqual(output, render(root, "packet1"))
            self.assertEqual((sha(page), sha(manifest)), original_shas)
            receipt = read(output.parent / "receipt.json")
            self.assertEqual(receipt["source_html_sha256"], sha(page))
            self.assertEqual(receipt["manifest_sha256"], sha(manifest))
            self.assertEqual(receipt["compact_html_sha256"], sha(output))
            self.assertFalse(receipt["human_review_records_changed"])
            with self.assertRaises(ValueError):
                render(root, "packet1", threshold=2000)
            self.assertFalse((root / "paired-human/records").exists())

    def test_malformed_html_and_unsafe_packet_rejected(self) -> None:
        for source in (
            "<blockquote>Unclosed",
            "<article><blockquote>nested<blockquote>x</blockquote></blockquote></article>",
            "<article></blockquote></article>",
        ):
            with self.subTest(source=source), self.assertRaises(ValueError):
                transform(source)
        with TemporaryDirectory() as temp, self.assertRaises(ValueError):
            render(Path(temp), "../other")
        with self.assertRaises(ValueError):
            transform(self.source(), threshold=True)


if __name__ == "__main__":
    unittest.main()
