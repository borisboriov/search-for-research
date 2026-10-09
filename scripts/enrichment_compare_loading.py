"""Ограниченный live HTTP benchmark httpx / Crawl4AI HTTP, без браузера и LLM.

Crawl4AI 0.9.4 browser flags подавляют AutomationControlled: этот путь здесь
не запускается. Динамический браузер и качество таблиц/вложений не измерены.
"""

import argparse
import asyncio
import hashlib
import importlib
import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from enrichment_compare_pages import SimpleHTML
from enrichment_experiment import now, private_root, read, write_new

URLS = (
    "https://en.misis.ru/science/community/scientists/3578/",
    "https://aistudy.innopolis.university/symposium2022",
)
AGENT = "SFRExperiment"


class Budget:
    """Одна robots-загрузка/домен и максимум две document-загрузки/метод/URL."""

    def __init__(self) -> None:
        self.counts: dict[tuple[str, str], int] = {}
        self.last: dict[str, float] = {}

    def reserve(self, method: str, url: str) -> None:
        if method not in ("robots", "httpx", "crawl4ai_http"):
            raise ValueError("Неизвестный метод")
        key = (method, url)
        limit = 1 if method == "robots" else 2
        if self.counts.get(key, 0) >= limit:
            raise ValueError("Лимит benchmark исчерпан")
        self.counts[key] = self.counts.get(key, 0) + 1

    async def wait(self, url: str, delay: float) -> None:
        domain = urlparse(url).netloc
        remaining = self.last.get(domain, 0) + max(1, delay) - time.monotonic()
        if remaining > 0:
            await asyncio.sleep(remaining)
        self.last[domain] = time.monotonic()


class DomainStops:
    """Сохраняемая остановка домена после 403/429, включая возобновление."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.domains = {read(p)["domain"] for p in root.glob("domain-stop-*.json")}

    def blocked(self, url: str) -> bool:
        return urlparse(url).netloc in self.domains

    def observe(self, url: str, status_code: int | None) -> None:
        if status_code not in (403, 429) or self.blocked(url):
            return
        domain = urlparse(url).netloc
        name = hashlib.sha256(domain.encode()).hexdigest()
        write_new(
            self.root / f"domain-stop-{name}.json",
            {"domain": domain, "url": url, "status_code": status_code, "checked_at": now()},
        )
        self.domains.add(domain)


def policy(robots: str, url: str, status_code: int) -> tuple[bool, float]:
    if status_code != 200:
        return False, 1
    # RFC 9309 §§2.2.1–2.2.3: группировка, longest match, '*' и '$'.
    # urllib.robotparser превращает '*?' в '*' и запрещает весь MISIS ошибочно.
    groups: list[tuple[list[str], list[tuple[str, str]]]] = []
    agents: list[str] = []
    rules: list[tuple[str, str]] = []
    for line in robots.splitlines():
        line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            if rules:
                groups.append((agents, rules))
                agents, rules = [], []
            agents.append(value.lower())
        elif agents and key in ("allow", "disallow", "crawl-delay"):
            rules.append((key, value))
    groups.append((agents, rules))
    selected = [r for a, r in groups if AGENT.lower() in a]
    if not selected:
        selected = [r for a, r in groups if "*" in a]
    parsed = urlparse(url)
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    # Только ASCII fixture; сложную нормализацию не объявляем реализованной.
    if not path.isascii() or "%" in path:
        return False, 1
    matches: list[tuple[int, bool]] = []
    delay = 1.0
    for group in selected:
        for key, value in group:
            if key == "crawl-delay":
                try:
                    delay = max(delay, float(value))
                except ValueError:
                    return False, delay
            elif value:
                ending = "$" if value.endswith("$") else ""
                pattern = value[:-1] if ending else value
                regex = "^" + re.escape(pattern).replace(r"\*", ".*") + ending
                if re.search(regex, path):
                    matches.append((len(pattern.encode()), key == "allow"))
    return (max(matches)[1] if matches else True), delay


def extract(raw: str, url: str, markdown: str | None = None) -> dict[str, Any]:
    parser = SimpleHTML(url)
    parser.feed(raw)
    text = "\n".join(parser.text) if markdown is None else markdown
    links = sorted(set(parser.links))
    attachments = [u for u in links if re.search(r"\.(pdf|docx?|xlsx?|pptx?)(?:[?#]|$)", u, re.I)]
    return {
        "text": text,
        "links": links,
        "links_preserved_in_markdown": (
            sum(u in markdown for u in links) if markdown is not None else None
        ),
        "year_tokens": sorted(set(re.findall(r"\b(?:19|20)\d{2}\b", text))),
        "html_table_count": parser.tables,
        "attachment_links": attachments,
        "attachment_contents": [],
        "attachment_contents_status": "not_tested" if attachments else "no_fixture",
        "table_quality_status": "not_tested" if parser.tables else "no_fixture",
        "text_completeness_reviewed": False,
        "human_review_minutes": None,
    }


async def run(out: Path, settings_file: Path) -> dict[str, Any]:
    out = private_root(out)
    if (out / "metrics.json").exists():
        return dict(read(out / "metrics.json"))
    # Не выводить Settings: mailto используется только внутри User-Agent.
    settings = importlib.import_module("sfr_core.settings").Settings(_env_file=settings_file)
    headers = {"User-Agent": f"{AGENT}/2.0 (mailto:{settings.openalex_mailto})"}
    started = time.monotonic()
    crawl = importlib.import_module("crawl4ai.async_crawler_strategy")
    configs = importlib.import_module("crawl4ai.async_configs")
    generator = importlib.import_module(
        "crawl4ai.markdown_generation_strategy"
    ).DefaultMarkdownGenerator()
    strategy = crawl.AsyncHTTPCrawlerStrategy(
        browser_config=configs.HTTPCrawlerConfig(
            headers=headers, follow_redirects=False, verify_ssl=True
        ),
        max_connections=1,
    )
    setup_seconds = time.monotonic() - started
    budget = Budget()
    stops = DomainStops(out)
    results = []
    async with (
        httpx.AsyncClient(headers=headers, timeout=30, follow_redirects=False) as client,
        strategy,
    ):
        for index, url in enumerate(URLS):
            robots_url = f"https://{urlparse(url).netloc}/robots.txt"
            robots_path = out / f"robots-{index}.json"
            if robots_path.exists():
                saved = read(robots_path)
            elif stops.blocked(url):
                saved = {"text": "", "status_code": None}
            else:
                budget.reserve("robots", robots_url)
                write_new(
                    out / f"robots-{index}-request.json",
                    {"url": robots_url, "checked_at": now(), "method": "httpx"},
                )
                await budget.wait(robots_url, 1)
                start = time.monotonic()
                try:
                    response = await client.get(robots_url)
                    saved = {
                        "url": robots_url,
                        "checked_at": now(),
                        "status_code": response.status_code,
                        "text": response.text,
                        "elapsed_seconds": time.monotonic() - start,
                    }
                except httpx.HTTPError as exc:
                    saved = {
                        "url": robots_url,
                        "checked_at": now(),
                        "status_code": None,
                        "text": "",
                        "elapsed_seconds": time.monotonic() - start,
                        "error": type(exc).__name__,
                    }
                write_new(robots_path, saved)
            stops.observe(robots_url, saved["status_code"])
            allowed, delay = policy(saved["text"], url, saved["status_code"])
            for method in ("httpx", "crawl4ai_http"):
                result_path = out / f"page-{index}-{method}.json"
                if result_path.exists():
                    cached = read(result_path)
                    stops.observe(url, cached.get("status_code"))
                    results.append(cached)
                    continue
                item: dict[str, Any] = {
                    "page": index,
                    "method": method,
                    "url": url,
                    "checked_at": now(),
                    "robots_allowed": allowed,
                    "crawl_delay_seconds": delay,
                    "cost_usd": 0,
                    "human_review_minutes": None,
                    "elapsed_scope": (
                        "download_only" if method == "httpx" else "download_plus_markdown"
                    ),
                    "source_terms_status": (
                        "pilot_no_explicit_terms_located_current_terms_not_reverified"
                    ),
                }
                if stops.blocked(url):
                    item.update(status="domain_stopped", elapsed_seconds=None)
                elif not allowed:
                    item.update(status="policy_unavailable_or_disallowed", elapsed_seconds=None)
                else:
                    budget.reserve(method, url)
                    request_path = out / f"page-{index}-{method}-request.json"
                    if request_path.exists():
                        # Не повторять неизвестную попытку после аварии без отдельной версии.
                        raise ValueError(
                            "Незавершённая попытка; нужен новый out для повторного запуска"
                        )
                    write_new(
                        request_path,
                        {
                            "url": url,
                            "method": method,
                            "checked_at": now(),
                            "policy_sha": __import__("hashlib")
                            .sha256(saved["text"].encode())
                            .hexdigest(),
                        },
                    )
                    await budget.wait(url, delay)
                    start = time.monotonic()
                    try:
                        if method == "httpx":
                            response = await client.get(url)
                            raw, code = response.text, response.status_code
                            markdown = None
                        else:
                            response = await strategy.crawl(
                                url, config=configs.CrawlerRunConfig(page_timeout=30000)
                            )
                            raw, code = response.html, response.status_code
                            markdown = generator.generate_markdown(raw, base_url=url).raw_markdown
                        stops.observe(url, code)
                        item.update(
                            status="ok" if code == 200 else "http_failure",
                            status_code=code,
                            elapsed_seconds=time.monotonic() - start,
                        )
                        if code == 200:
                            item.update(
                                html=raw,
                                html_sha256=hashlib.sha256(raw.encode()).hexdigest(),
                                extraction=extract(raw, url, markdown),
                            )
                    except Exception as exc:
                        item.update(
                            status="technical_failure",
                            error_type=type(exc).__name__,
                            elapsed_seconds=time.monotonic() - start,
                        )
                write_new(result_path, item)
                results.append(item)
    summary = {
        "mode": "live httpx vs Crawl4AI AsyncHTTPCrawlerStrategy; static HTML only",
        "crawl4ai_version": "0.9.4",
        "document_urls": 2,
        "methods": 2,
        "setup_seconds": setup_seconds,
        "human_setup_minutes": None,
        "human_review_minutes": None,
        "llm_calls": 0,
        "paid_api_usd": 0,
        "elapsed_comparison_limit": (
            "httpx elapsed is download; Crawl4AI elapsed includes Markdown conversion; "
            "do not infer transport speed ranking"
        ),
        "browser_transport_tested": False,
        "browser_not_run_reason": (
            "0.9.4 hardcoded AutomationControlled suppression; no bypass authorized"
        ),
        "rows": [
            {k: v for k, v in r.items() if k not in ("html", "extraction", "url")}
            | {
                "text_chars": len(r.get("extraction", {}).get("text", "")),
                "links": len(r.get("extraction", {}).get("links", [])),
                "links_preserved_in_markdown": r.get("extraction", {}).get(
                    "links_preserved_in_markdown"
                ),
                "year_tokens": len(r.get("extraction", {}).get("year_tokens", [])),
                "tables": r.get("extraction", {}).get("html_table_count"),
                "attachment_links": len(r.get("extraction", {}).get("attachment_links", [])),
                "attachment_contents_tested": False,
                "quality_verified": False,
            }
            for r in results
        ],
    }
    write_new(out / "metrics.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--settings-file", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.out, args.settings_file)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
