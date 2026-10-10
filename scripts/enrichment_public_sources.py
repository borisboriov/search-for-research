"""Малый HTTP/API/PDF адаптер публичного эксперимента, без планировщика/crawler."""

import asyncio
import importlib
import ipaddress
import json
import re
import socket
import time
from datetime import UTC, datetime
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx
from enrichment_compare_loading import AGENT, DomainStops, extract, policy
from enrichment_contact_first import Loader, checked_source, digest, safe_url
from enrichment_experiment import ORCID_API, ensure_not_stopped, now, private_root, read
from enrichment_verification import immutable_bytes, immutable_json


class ObservedLinks(HTMLParser):
    """Href, starttag и текст якоря относятся к одному сохранённому HTML."""

    def __init__(self, parent: str, body: str) -> None:
        super().__init__()
        self.parent = parent
        self.sha = digest(body.encode())
        self.rows: list[dict[str, Any]] = []
        self.active: dict[str, Any] | None = None
        self.base_seen = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = dict(attrs)
        if tag == "base" and data.get("href"):
            self.base_seen = True
        if tag == "a" and data.get("href"):
            self.flush()
            self.active = {
                "parent_url": self.parent,
                "parent_decoded_sha256": self.sha,
                "href": data["href"],
                "start_tag": self.get_starttag_text(),
                "parts": [],
            }

    def handle_data(self, data: str) -> None:
        if self.active is not None:
            self.active["parts"].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self.flush()

    def flush(self) -> None:
        if self.active is not None:
            row = self.active
            row["anchor"] = "".join(row.pop("parts"))
            row["url"] = urljoin(self.parent, row["href"])
            self.rows.append(row)
            self.active = None


def observed_links(parent: str, body: str) -> list[dict[str, Any]]:
    parser = ObservedLinks(parent, body)
    parser.feed(body)
    parser.close()
    parser.flush()
    rows = []
    for row in parser.rows:
        try:
            safe_url(row["url"])
        except ValueError:
            continue
        if parser.base_seen and not urlsplit(row["href"]).scheme:
            continue
        rows.append(row)
    return rows


def pdf_text(raw: bytes) -> str:
    """Локальная воспроизводимая PDF extraction; отсутствие parser — отказ."""
    try:
        reader = importlib.import_module("pypdf").PdfReader(BytesIO(raw))
    except ImportError as exc:
        raise ValueError("PDF parser отсутствует") from exc
    if reader.is_encrypted or len(reader.pages) > 100:
        raise ValueError("Encrypted/слишком большой PDF")
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    if len(text) > 1_000_000:
        raise ValueError("PDF text budget")
    return text


MATHNET_DECODER = """function decode_email(a) {
    var t = '';
    for (i = 0; i < a.length; i++) {
        if (a.charCodeAt(i) <= 127) {
            t += String.fromCharCode((a.charCodeAt(i) - 65) * 16 + (a.charCodeAt(++i) - 65))
        } else { t += a.charAt(i); }
    }
    return t;
}"""


def render_mathnet_contacts(body: str, script: bytes) -> str:
    """Воспроизвести точную публичную функцию, без исполнения произвольного JS."""
    text = script.decode("latin1")
    start = text.find("function decode_email(a)")
    if start < 0:
        raise ValueError("No public decode_email function")
    first_brace, depth = text.find("{", start), 0
    for end in range(first_brace, len(text)):
        depth += (text[end] == "{") - (text[end] == "}")
        if depth == 0:
            break
    if re.sub(r"\s+", "", text[start : end + 1]) != re.sub(r"\s+", "", MATHNET_DECODER):
        raise ValueError("Public decoder differs from supported literal function")

    def replace(match: re.Match[str]) -> str:
        value = match[1]
        if len(value) % 2 or not re.fullmatch(r"[A-P]+", value):
            raise ValueError("Unsupported public email encoding")
        return "".join(
            chr((ord(value[i]) - 65) * 16 + ord(value[i + 1]) - 65) for i in range(0, len(value), 2)
        )

    return re.sub(
        r"<script\b[^>]*>\s*document\.write\(decode_email\(['\"]([A-Za-z]+)['\"]\)\);?\s*</script>",
        replace,
        body,
        flags=re.I,
    )


def protection(body: str) -> bool:
    title = re.search(r"<title[^>]*>(.*?)</title", body, re.I | re.S)
    markers = ("captcha", "just a moment", "access denied", "вход в систему")
    if title and any(word in title[1].lower() for word in markers):
        return True
    return len(body) < 100000 and any(
        word in body.lower() for word in ("__js_p_", "cf-chl", "checking your browser")
    )


class PublicLoader(Loader):
    """Прежний source registry с общим finite ledger и отдельной API policy."""

    def __init__(self, root: Path, urls: list[str], experiment: Path, author_id: str) -> None:
        super().__init__(root, urls)
        self.experiment = private_root(experiment)
        self.author_id = author_id
        self.manifest = read(experiment / "manifest.json")
        self.ledger = private_root(experiment / "HTTP-ledger")
        self.stops = DomainStops(private_root(experiment / "domain-stops"))
        # Последняя попытка каждого host переживает новый Loader/profile/process.
        for file in self.ledger.glob("*-finished.json"):
            record = read(file)
            host = urlsplit(record["url"]).netloc
            elapsed = max(0.0, time.time() - record["finished_timestamp"])
            self.budget.last[host] = max(self.budget.last.get(host, 0), time.monotonic() - elapsed)

    async def request(
        self, client: httpx.AsyncClient, url: str, kind: str, cap: int
    ) -> dict[str, Any]:
        safe_url(url)
        ensure_not_stopped(self.experiment)
        ensure_not_stopped(self.root)
        deadline = datetime.fromisoformat(self.manifest["deadline_acquisition"])
        if datetime.now(UTC) >= deadline:
            raise ValueError("Acquisition deadline")
        if self.stops.blocked(url):
            raise ValueError("Domain STOP403/429/challenge")
        key = digest((kind + "\0" + url).encode())
        path = self.root / f"request-result-{key}.json"
        if path.exists():
            return dict(read(path))
        previous = [read(p) for p in self.ledger.glob("*-reserved.json")]
        if (
            len(previous) >= self.manifest["HTTP_total_cap"]
            or sum(p["author_id"] == self.author_id for p in previous)
            >= self.manifest["HTTP_per_profile_cap"]
        ):
            raise ValueError("Frozen HTTP budget")
        requests = private_root(self.root / "requests")
        if any(read(p)["url"] == url and read(p)["kind"] == kind for p in requests.glob("*.json")):
            raise ValueError("Unfinished source: no retry")
        ticket = f"{len(previous):04d}"
        reservation = {"at": now(), "url": url, "kind": kind, "author_id": self.author_id}
        immutable_json(self.ledger / f"{ticket}-reserved.json", reservation)
        immutable_json(requests / f"{ticket}.json", reservation)
        start = time.monotonic()
        body = bytearray()
        meta: dict[str, Any] = {
            "url": url,
            "kind": kind,
            "checked_at": now(),
            "status": None,
            "content_type": None,
            "location": None,
            "HTTP_started": False,
            "complete": False,
            "error": None,
        }
        try:
            async with asyncio.timeout(30):
                parsed = urlsplit(url)
                addresses = await asyncio.to_thread(
                    socket.getaddrinfo,
                    parsed.hostname,
                    parsed.port or 443,
                    type=socket.SOCK_STREAM,
                )
                if not addresses or not all(
                    ipaddress.ip_address(row[4][0]).is_global for row in addresses
                ):
                    raise ValueError("Nonpublic destination IP")
                await self.budget.wait(url, 1)
                client.cookies.clear()
                meta["HTTP_started"] = True
                async with client.stream("GET", url) as response:
                    meta.update(
                        status=response.status_code,
                        content_type=response.headers.get("content-type", ""),
                        location=response.headers.get("location"),
                    )
                    self.stops.observe(url, response.status_code)
                    size = cap if response.status_code == 200 else min(cap, 65536)
                    async for chunk in response.aiter_bytes():
                        if len(body) + len(chunk) > size:
                            raise ValueError("Bounded source body")
                        body.extend(chunk)
                    meta["complete"] = True
        except (httpx.HTTPError, TimeoutError, ValueError, OSError) as exc:
            meta["error"] = type(exc).__name__
        raw = self.root / f"body-{key}.bin"
        immutable_bytes(raw, bytes(body))
        meta.update(
            body_path=raw.name,
            body_sha256=digest(bytes(body)),
            body_bytes=len(body),
            seconds=time.monotonic() - start,
        )
        immutable_json(path, meta)
        immutable_json(
            self.ledger / f"{ticket}-finished.json",
            reservation
            | {
                "HTTP_started": meta["HTTP_started"],
                "status": meta["status"],
                "finished_timestamp": time.time(),
                "receipt_sha256": digest(path.read_bytes()),
            },
        )
        return meta

    async def load(self, url: str, *, kind: str = "direct_http") -> dict[str, Any]:
        if url not in self.allowed or kind not in ("direct_http", "structured_orcid", "direct_pdf"):
            raise ValueError("No registered URL/source kind")
        original = url
        api = kind == "structured_orcid"
        if api:
            access = read(self.experiment / "official-ORCID-policy.json")
            if (
                access.get("access") != "allowed"
                or access.get("source") != ORCID_API
                or not re.fullmatch(
                    re.escape(ORCID_API) + r"/\d{4}-\d{4}-\d{4}-\d{3}[\dX]/record", url
                )
            ):
                raise ValueError("Official public API policy/endpoint missing")
        async with httpx.AsyncClient(
            headers={
                "User-Agent": f"{AGENT}/2.0 (mailto:soskinboris@icloud.com)",
                "Accept": "application/json" if api else "*/*",
            },
            timeout=30,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            visited: set[str] = set()
            for hop in range(6):
                if url in visited:
                    raise ValueError("Redirect cycle")
                visited.add(url)
                registered = self.root / f"source-{digest(url.encode())}.json"
                if registered.exists():
                    source = dict(read(registered))
                    checked_source(self.root, source)
                    return source
                robots_status, robots_basis = None, "official_public_API_policy"
                if not api:
                    parsed = urlsplit(url)
                    robots = await self.request(
                        client, f"{parsed.scheme}://{parsed.netloc}/robots.txt", "robots", 65536
                    )
                    robots_status = robots["status"]
                    if robots_status == 404:
                        allowed, delay, robots_basis = (
                            True,
                            1.0,
                            "robots_missing_404_rfc9309_2.3.1.3",
                        )
                    else:
                        if (
                            not robots["complete"]
                            or robots_status != 200
                            or "text/" not in (robots["content_type"] or "")
                        ):
                            raise ValueError("No full allowing robots")
                        allowed, delay = policy(
                            (self.root / robots["body_path"])
                            .read_bytes()
                            .decode("utf-8", errors="replace"),
                            url,
                            robots_status,
                        )
                        robots_basis = "parsed_robots_200"
                    immutable_json(
                        self.root / f"policy-{digest(url.encode())}.json",
                        {
                            "url": url,
                            "allowed": allowed,
                            "delay": delay,
                            "robots_status": robots_status,
                            "basis": robots_basis,
                        },
                    )
                    if not allowed or delay > 30:
                        raise ValueError("Robots refusal/excessive delay")
                    await self.budget.wait(url, delay)
                response = await self.request(
                    client, url, kind, 8388608 if kind == "direct_pdf" else 2097152
                )
                if not response["complete"]:
                    raise ValueError("Incomplete HTTP source")
                if response["status"] in (301, 302, 303, 307, 308):
                    if api or hop == 5 or not response["location"]:
                        raise ValueError("API/redirect budget/refusal")
                    target = urljoin(url, response["location"])
                    safe_url(target)
                    if any(
                        w in (urlsplit(target).path + "?" + urlsplit(target).query).lower()
                        for w in ("captcha", "challenge", "__cf_chl", "/login", "/signin")
                    ):
                        raise ValueError("Protection redirect; no bypass")
                    immutable_json(
                        self.root / f"redirect-{digest(url.encode())}.json",
                        {
                            "source_url": url,
                            "original_url": original,
                            "Location": response["location"],
                            "observed_target": target,
                            "hop": hop,
                        },
                    )
                    url = target
                    continue
                if response["status"] != 200:
                    raise ValueError("Source access refusal")
                raw = (self.root / response["body_path"]).read_bytes()
                ctype = response["content_type"] or ""
                media_kind = kind
                if "pdf" in ctype and raw.startswith(b"%PDF"):
                    media_kind = "direct_pdf"
                if media_kind == "direct_pdf":
                    if "pdf" not in ctype or not raw.startswith(b"%PDF"):
                        raise ValueError("Not a PDF")
                    decoded = static = pdf_text(raw)
                else:
                    charset = re.search(r"charset=([\w-]+)", ctype, re.I)
                    decoded = raw.decode(charset[1] if charset else "utf-8", errors="strict")
                    if api:
                        if "json" not in ctype:
                            raise ValueError("Not public API JSON")
                        static = json.dumps(json.loads(decoded), ensure_ascii=False, indent=2)
                    else:
                        if "text/html" not in ctype:
                            raise ValueError("Not HTML; register actual PDF separately")
                        if protection(decoded):
                            self.stops.observe(url, 403)
                            raise ValueError("Protection/login HTML; no bypass")
                        static = extract(decoded, url)["text"]
                key = digest(url.encode())
                immutable_bytes(self.root / f"decoded-{key}.txt", decoded.encode())
                immutable_bytes(self.root / f"text-{key}.txt", static.encode())
                source = response | {
                    "source_kind": media_kind,
                    "request_kind": kind,
                    "decoded_path": f"decoded-{key}.txt",
                    "text_path": f"text-{key}.txt",
                    "decoded_sha256": digest(decoded.encode()),
                    "text_sha256": digest(static.encode()),
                    "information_date": None,
                    "robots_status": robots_status,
                    "robots_basis": robots_basis,
                }
                if api:
                    policy_path = self.experiment / "official-ORCID-policy.json"
                    source.update(
                        api_policy_record_path=str(policy_path),
                        api_policy_sha256=digest(policy_path.read_bytes()),
                    )
                immutable_json(registered, source)
                checked_source(self.root, source)
                return source
        raise ValueError("No complete source")
