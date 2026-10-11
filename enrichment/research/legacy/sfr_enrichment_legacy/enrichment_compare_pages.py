"""Сравнение экстракции одного сохранённого HTML, без повторного доступа к сайту.

Это не тест браузерной загрузки динамических страниц. Crawl4AI устанавливается
в отдельную среду; генератор Markdown не использует LLM, stealth или прокси.
"""

import argparse
import importlib
import json
import re
import time
from pathlib import Path

from sfr_enrichment.http_policy import (
    SimpleHTML as SimpleHTML,
)
from sfr_enrichment_legacy.enrichment_experiment import private_root, read, sha, write_new


def compare(pages: Path, out: Path) -> None:
    out = private_root(out)
    generator_module = importlib.import_module("crawl4ai.markdown_generation_strategy")
    generator = generator_module.DefaultMarkdownGenerator()
    metrics = []
    for path in sorted(pages.glob("*.html")):
        metadata = read(path.with_suffix(".json"))
        html = path.read_text(encoding="utf-8")
        start = time.monotonic()
        baseline = SimpleHTML(metadata["url"])
        baseline.feed(html)
        text = "\n".join(baseline.text)
        baseline_seconds = time.monotonic() - start
        start = time.monotonic()
        markdown = generator.generate_markdown(html, base_url=metadata["url"]).raw_markdown
        crawl_seconds = time.monotonic() - start
        write_new(
            out / f"{path.stem}-outputs.json",
            {
                "url": metadata["url"],
                "html_sha256": sha(path),
                "baseline_text": text,
                "baseline_links": baseline.links,
                "crawl4ai_markdown": markdown,
                "reviewed_by": None,
                "human_reviewed": False,
            },
        )
        dates = sorted(set(re.findall(r"\b(?:19|20)\d{2}\b", text)))
        attachments = [
            url
            for url in baseline.links
            if re.search(r"\.(?:pdf|docx?|xlsx?|pptx?)(?:[?#]|$)", url, re.I)
        ]
        metrics.append(
            {
                "page": path.stem,
                "html_sha256": sha(path),
                "baseline_seconds": round(baseline_seconds, 6),
                "crawl4ai_seconds": round(crawl_seconds, 6),
                "baseline_chars": len(text),
                "crawl4ai_chars": len(markdown),
                "baseline_links": len(set(baseline.links)),
                "baseline_links_in_markdown": sum(url in markdown for url in set(baseline.links)),
                "html_table_count": baseline.tables,
                "table_semantics_reviewed": False,
                "year_tokens": len(dates),
                "year_tokens_preserved": sum(d in markdown for d in dates),
                "attachment_links": len(set(attachments)),
                "attachments_in_markdown": sum(url in markdown for url in set(attachments)),
                "attachment_contents_tested": False,
                "text_completeness_reviewed": False,
                "manual_correction_minutes": None,
                "live_browser_loading_tested": False,
            }
        )
    write_new(
        out / "metrics.json",
        {
            "mode": "same cached HTML, extraction only",
            "crawl4ai_version": "0.9.4",
            "llm_calls": 0,
            "pages": metrics,
            "note": "Counts and lengths are diagnostics, not measured extraction accuracy",
        },
    )
    print(json.dumps(metrics, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pages", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    compare(args.pages, args.out)


if __name__ == "__main__":
    main()
