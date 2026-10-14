"""Public HTTP policy and literal HTML extraction; no benchmark runner."""

import asyncio
import hashlib
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from sfr_enrichment.common import now, read, write_new


class SimpleHTML(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.text: list[str] = []
        self.links: list[str] = []
        self.tables = 0
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style", "noscript"):
            self.hidden += 1
        if self.hidden:
            return
        if tag == "table":
            self.tables += 1
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(urljoin(self.base_url, href))

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript") and self.hidden:
            self.hidden -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden and data.strip():
            self.text.append(data.strip())


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
        domain = urlparse(url).netloc
        # Decoder/other loader instances share the persisted stop, not a stale snapshot.
        record = self.root / f"domain-stop-{hashlib.sha256(domain.encode()).hexdigest()}.json"
        if record.exists():
            if read(record).get("domain") != domain:
                raise ValueError("Domain STOP record mismatch")
            self.domains.add(domain)
        return domain in self.domains

    def observe(self, url: str, status_code: int | None) -> None:
        if status_code not in (403, 429) or self.blocked(url):
            return
        self.block(url, f"HTTP{status_code}", status_code)

    def block(self, url: str, reason: str, status_code: int | None = None) -> None:
        """Keep a conservative domain stop with its real observed status/reason."""
        if self.blocked(url):
            return
        domain = urlparse(url).netloc
        name = hashlib.sha256(domain.encode()).hexdigest()
        write_new(
            self.root / f"domain-stop-{name}.json",
            {
                "domain": domain,
                "url": url,
                "status_code": status_code,
                "reason": reason,
                "checked_at": now(),
            },
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
