"""Отдельное представление сохраняет дословные цитаты и механизм разметки."""

import html
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from sfr_enrichment_legacy.enrichment_experiment import read, sha, write_new
from sfr_enrichment_legacy.enrichment_pair_compact import (
    QuoteSpans,
    readable_invalid,
    render,
    transform,
)


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

    def invalid_fixture(self) -> tuple[str, dict[str, object], str]:
        value = {
            "items": [
                {
                    "item_id": "i1",
                    "text_verdict": "supported",
                    "identity_verdict": "insufficient",
                    "field_verdict": "correct",
                    "student_level": [],
                    "evidence_refs": ["missing-source"],
                    "question": '<img src=x onerror="alert(1)">',
                    "explanation": "Дословное объяснение",
                    "fact_kind": "unrecognized_kind",
                }
            ],
            "profile_assessments": {},
            "summary": {
                "known": "Нет принятого результата",
                "unknown": "Неизвестно",
                "identity": "Не установлено",
                "current_opportunity": "Не установлено",
            },
        }
        response = value | {
            "validation": {"succeeded": False, "errors": ["Нужен уровень студента"]}
        }
        profile = {
            "author_id": "A1",
            "items": [{"item_id": "i1"}, {"item_id": "i2"}],
            "responses": {"A": response},
            "evidence_pool": {},
        }
        manifest = {
            "schema": "paired_human_packet_v1",
            "packet_id": "packet1",
            "profiles": [profile],
            "human_reviewed": False,
        }
        escaped = html.escape(json.dumps(value, ensure_ascii=False, indent=2))
        original_pre = (
            "<details><summary>Исходный ответ с ошибками</summary><pre>"
            + escaped
            + "</pre></details>"
        )
        source = self.source().replace("</article>", original_pre + "</article>")
        return source, manifest, original_pre

    def test_invalid_answer_readable_in_russian_and_original_json_unmodified(self) -> None:
        source, manifest, original_pre = self.invalid_fixture()
        result, stats = transform(source, manifest=manifest)
        self.assertIn(original_pre, result)
        self.assertEqual(stats["invalid_responses_rendered"], 1)
        self.assertIn("Оригинальный ответ: НЕ ПРИНЯТ", result)
        self.assertIn("Не указан (ошибка ответа)", result)
        self.assertIn("Подтверждение текстом", result)
        self.assertIn("Подтверждено", result)
        self.assertIn("Неизвестный код: unrecognized_kind", result)
        self.assertIn("Неизвестная ссылка; отсутствует в общем пакете: missing-source", result)
        self.assertIn("Пропущены оценки атомов:</strong> i2", result)
        self.assertIn("Отсутствует (ошибка ответа)", result)
        self.assertNotIn("<img src=x onerror=", result)
        before, after = QuoteSpans(source), QuoteSpans(result)
        before.finish()
        after.finish()
        self.assertEqual(before.scripts, after.scripts)
        self.assertEqual(before.invalid_pres[0][1], after.invalid_pres[0][1])

    def test_missing_references_and_empty_references_remain_absent(self) -> None:
        rendered = readable_invalid(
            {"items": [{"item_id": "missing"}, {"item_id": "empty", "evidence_refs": []}]}
        )
        self.assertIn("Ссылки не приведены", rendered)
        self.assertIn("Отсутствует (ошибка ответа)", rendered)
        self.assertNotIn("Статус: Не установлено", rendered)

    def test_invalid_code_is_not_translated_as_valid_in_another_dimension(self) -> None:
        rendered = readable_invalid(
            {
                "items": [
                    {"item_id": "i1", "student_level": ["supported"], "corrected_field": "masters"}
                ]
            }
        )
        self.assertIn("Неизвестный код: supported", rendered)
        self.assertIn("Неизвестный код: masters", rendered)

    def test_new_representation_keeps_v1_v2_and_binds_manifest_before_output(self) -> None:
        source, manifest, _ = self.invalid_fixture()
        with TemporaryDirectory() as temp:
            root = Path(temp)
            packet = root / "paired-human/packets/packet1"
            packet.mkdir(parents=True)
            (packet / "cards.html").write_text(source)
            write_new(packet / "manifest.json", manifest)
            v1 = root / "paired-human/compact-v1/packet1/cards.html"
            v1.parent.mkdir(parents=True)
            v1.write_text("Unchanged v1")
            original_hash = sha(v1)
            v2 = root / "paired-human/compact-v2/packet1/cards.html"
            v2.parent.mkdir(parents=True)
            v2.write_text("Unchanged v2")
            v2_hash = sha(v2)
            output = render(root, "packet1")
            self.assertIn("compact-v3", str(output))
            self.assertEqual(original_hash, sha(v1))
            self.assertEqual(v2_hash, sha(v2))
            self.assertEqual(render(root, "packet1"), output)
            receipt = read(output.parent / "receipt.json")
            self.assertEqual(receipt["invalid_responses_rendered"], 1)
            self.assertEqual(
                receipt["script_sha256"],
                sha(
                    Path(__file__).parents[1]
                    / "research/legacy/sfr_enrichment_legacy/enrichment_pair_compact.py"
                ),
            )
            wrong = dict(manifest, profiles=[])
            with self.assertRaises(ValueError):
                transform(source, manifest=wrong)

    def test_unicode_line_separators_do_not_corrupt_raw_html_positions(self) -> None:
        source, manifest, original_pre = self.invalid_fixture()
        # Reader text can include PDF/control separators which HTMLParser does
        # not treat as new lines. Their presence before a later pre previously
        # shifted offsets and lost its invalid-response marker.
        separators = "\u2028\u2029\x85\v\f\r"
        source = source.replace("<article>", "<article><p>" + separators + "</p>")
        result, stats = transform(source, manifest=manifest)
        self.assertEqual(stats["invalid_responses_rendered"], 1)
        self.assertIn(original_pre, result)
        before, after = QuoteSpans(source), QuoteSpans(result)
        before.finish()
        after.finish()
        self.assertEqual(before.scripts, after.scripts)
        self.assertEqual(before.invalid_pres[0][1], after.invalid_pres[0][1])
        self.assertIn(separators, result)

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
