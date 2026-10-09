"""Отдельное компактное представление слепого пакета без изменения исходников.

Сохраняет исходный HTML дословно внутри добавленных раскрывающихся блоков.
Не извлекает фактов и не меняет решения, вопросы, разметку или JavaScript.
"""

import argparse
import hashlib
import html
import json
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from enrichment_experiment import private_root, sha
from enrichment_verification import identifier, immutable_bytes

VERSION = "compact-v1"
NOTICE = (
    '<aside class="compact-notice"><p><strong>Как читать вопросы:</strong> '
    "вопросы агентов могут быть сформулированы как обращение к учёному. "
    "Вам нужно оценить корректность ответов по сохранённым источникам, "
    "а не отвечать от имени учёного. Исходные вопросы и ответы сохранены. "
    "Длинные и повторяющиеся цитаты раскрываются отдельно и приведены полностью.</p></aside>"
)


class QuoteSpans(HTMLParser):
    """Фиксирует смещения в исходной строке, не пересериализуя HTML."""

    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=False)
        self.source = source
        self.lines = [0]
        for line in source.splitlines(keepends=True):
            self.lines.append(self.lines[-1] + len(line))
        self.stack: list[int] = []
        self.quotes: list[tuple[int, int]] = []
        self.article: int | None = None
        self.scripts: list[str] = []
        self.script_start: int | None = None

    def position(self) -> int:
        line, column = self.getpos()
        return self.lines[line - 1] + column

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "blockquote":
            if self.stack:
                raise ValueError("Вложенные blockquote не поддерживаются")
            self.stack.append(self.position())
        if tag == "article" and self.article is None:
            self.article = self.position()
        if tag == "script":
            if self.script_start is not None:
                raise ValueError("Вложенный script")
            self.script_start = self.position()

    def handle_endtag(self, tag: str) -> None:
        end = self.source.index(">", self.position()) + 1
        if tag == "blockquote":
            if not self.stack:
                raise ValueError("Закрывающий blockquote без начала")
            self.quotes.append((self.stack.pop(), end))
        if tag == "script" and self.script_start is not None:
            self.scripts.append(self.source[self.script_start : end])
            self.script_start = None

    def finish(self) -> None:
        self.feed(self.source)
        self.close()
        if self.stack or self.script_start is not None:
            raise ValueError("Незавершённая цитата или script")


def transform(source: str, *, threshold: int = 600) -> tuple[str, dict[str, Any]]:
    """Не сокращает исходные цитаты: меняет только их начальную видимость."""
    if isinstance(threshold, bool) or not isinstance(threshold, int) or threshold < 1:
        raise ValueError("Нужен положительный предел длины")
    parser = QuoteSpans(source)
    parser.finish()
    if parser.article is None:
        raise ValueError("В исходном пакете нет карточек article")
    insertions: list[tuple[int, str]] = [(parser.article, NOTICE)]
    seen: set[str] = set()
    wrapped = 0
    repeated = 0
    for start, end in parser.quotes:
        raw = source[start:end]
        text = html.unescape(raw[raw.index(">") + 1 : raw.rindex("</")])
        digest = hashlib.sha256(text.encode()).hexdigest()
        duplicate = digest in seen
        seen.add(digest)
        if len(text) <= threshold and not duplicate:
            continue
        repeated += int(duplicate)
        wrapped += 1
        prefix = (
            '<details class="compact-source"><summary>Полная дословная цитата '
            f"({len(text)} символов" + ("; повтор источника" if duplicate else "") + ")</summary>"
        )
        insertions.extend(((start, prefix), (end, "</details>")))
    result = source
    for offset, value in sorted(insertions, key=lambda item: item[0], reverse=True):
        result = result[:offset] + value + result[offset:]
    check = QuoteSpans(result)
    check.finish()
    if check.scripts != parser.scripts:
        raise ValueError("JavaScript изменился")
    if [result[a:b] for a, b in check.quotes] != [source[a:b] for a, b in parser.quotes]:
        raise ValueError("Исходная цитата изменилась")
    return result, {
        "quote_count": len(parser.quotes),
        "collapsed_quote_count": wrapped,
        "repeated_collapsed_quote_count": repeated,
        "threshold_characters": threshold,
        "scripts_unchanged": True,
    }


def render(root: Path, packet_id: str, *, threshold: int = 600) -> Path:
    root = private_root(root)
    identifier(packet_id)
    original = root / "paired-human" / "packets" / packet_id
    source_path, manifest_path = original / "cards.html", original / "manifest.json"
    payload = source_path.read_bytes()
    manifest_bytes = manifest_path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
    manifest = json.loads(manifest_bytes)
    if manifest.get("schema") != "paired_human_packet_v1" or manifest.get("packet_id") != packet_id:
        raise ValueError("Другой исходный пакет")
    compact, stats = transform(payload.decode("utf-8"), threshold=threshold)
    destination = root / "paired-human" / VERSION / packet_id
    receipt = {
        "schema": "paired_human_representation_v1",
        "representation_version": VERSION,
        "packet_id": packet_id,
        "source_html_sha256": digest,
        "manifest_sha256": manifest_digest,
        "compact_html_sha256": hashlib.sha256(compact.encode()).hexdigest(),
        "source_html_path": str(source_path),
        "manifest_path": str(manifest_path),
        "human_review_records_changed": False,
        "source_records_changed": False,
        **stats,
    }
    # Check originals again before publishing, including a concurrently modified packet.
    if sha(source_path) != digest or sha(manifest_path) != manifest_digest:
        raise ValueError("Исходный пакет изменился во время преобразования")
    immutable_bytes(destination / "cards.html", compact.encode())
    immutable_bytes(
        destination / "receipt.json",
        (json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode(),
    )
    return destination / "cards.html"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--packet-id", required=True)
    parser.add_argument("--threshold", type=int, default=600)
    args = parser.parse_args()
    print(render(args.root, args.packet_id, threshold=args.threshold))


if __name__ == "__main__":
    main()
