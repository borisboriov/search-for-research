"""Code-owned source tools, without model-selected facts or baseline verdicts."""

import json
import re
import shutil
from contextlib import suppress
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urljoin

from enrichment_compare_loading import extract
from enrichment_contact_first import EMAIL, checked_source, digest, safe_url
from enrichment_experiment import ORCID_API, ensure_not_stopped, now, read, sha
from enrichment_public_sources import PublicLoader, observed_links, render_mathnet_contacts
from enrichment_verification import immutable_bytes, immutable_json


def search_links(raw: Any) -> list[str]:
    """Only actual title/link rows from native search; snippets are never evidence."""
    links: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, str):
            with suppress(ValueError, RecursionError):
                walk(json.loads(value))
        elif isinstance(value, list):
            for row in value:
                walk(row)
        elif isinstance(value, dict):
            if isinstance(value.get("title"), str) and isinstance(value.get("link"), str):
                try:
                    safe_url(value["link"])
                    links.append(value["link"])
                except ValueError:
                    pass
            for key in ("content", "text", "result", "message"):
                if key in value:
                    walk(value[key])

    walk(raw)
    return list(dict.fromkeys(links))


class SourceHost:
    def __init__(self, root: Path, profile: dict[str, Any], mode: str) -> None:
        self.root, self.profile, self.mode = root, profile, mode
        self.aid = profile["id"]
        self.directory = root / "sources" / self.aid
        self.directory.mkdir(parents=True, exist_ok=True)
        self.allowed: dict[str, int] = {}
        self.records: dict[str, Path] = {}
        self.failures: dict[str, str] = {}
        self.calls, self.searches = 0, 0
        orcid = str(profile.get("orcid", "")).rsplit("/", 1)[-1]
        if orcid:
            self.allowed[f"{ORCID_API}/{orcid}/record"] = 0
        if mode == "replay":
            # Fixture only: never import normalized facts, prepared inputs or verdicts.
            previous = Path(read(root / "manifest.json")["baseline_root"])
            for directory in (
                previous / "sources" / self.aid,
                previous / "rendered-sources" / self.aid,
            ):
                for path in directory.glob("source-*.json"):
                    record = read(path)
                    self.records[record["url"]] = path
                    self.allowed[record["url"]] = 0

    def register_search(self, raw: Any) -> None:
        for url in search_links(raw):
            self.allowed.setdefault(url, 0)

    async def public_search(self, query: str) -> dict[str, Any]:
        if self.mode != "live" or not query.strip():
            raise ValueError("Live public search only")
        reservations = [read(p) for p in (self.root / "search").glob("*-reserved.json")]
        if self.searches >= 4 or len(reservations) >= 40:
            raise ValueError("Frozen shared search cap")
        if any(
            r["author_id"] == self.aid
            and r["source"] == "public_DuckDuckGo_HTML"
            and r["query"] == query
            for r in reservations
        ):
            raise ValueError("No identical search retry")
        immutable_json(
            self.root / "search" / f"{len(reservations):04d}-reserved.json",
            {
                "at": now(),
                "author_id": self.aid,
                "query": query,
                "source": "public_DuckDuckGo_HTML",
            },
        )
        self.searches += 1
        # A documented public search endpoint, not a guessed professional path.
        # Ordinary robots/redirect/challenge policy applies; there is no alternate
        # endpoint or bypass after a refusal. All its HTTP is in the same ledger.
        url = "https://html.duckduckgo.com/html/?" + urlencode({"q": query})
        directory = self.root / "discovery" / self.aid
        source = await PublicLoader(directory, [url], self.root, self.aid).load(url)
        decoded, _ = checked_source(directory, source)
        if "anomaly.js" in decoded.lower() or "challenge-form" in decoded.lower():
            immutable_json(
                self.root / "domain-stops" / f"domain-stop-{digest(b'html.duckduckgo.com')}.json",
                {
                    "domain": "html.duckduckgo.com",
                    "url": url,
                    "status_code": 200,
                    "reason": "public_search_challenge",
                    "checked_at": now(),
                },
            )
            raise ValueError("Public search challenge; domain stopped, no bypass")
        rows = [
            r
            for r in observed_links(source["url"], decoded)
            if any(
                "result__a" in match[1].split()
                for match in re.findall(r"\bclass\s*=\s*(['\"])(.*?)\1", r["start_tag"], re.I)
            )
        ]
        for row in rows:
            self.allowed.setdefault(row["url"], 0)
        # Search HTML is NEVER added to records/evidence: discovery only.
        return {
            "discovery_only": True,
            "search_engine": "public_DuckDuckGo_HTML",
            "source_sha256": sha(directory / f"source-{digest(source['url'].encode())}.json"),
            "links": rows[:20],
        }

    def links(self, source: dict[str, Any], decoded: str, static: str) -> list[dict[str, Any]]:
        if source["source_kind"] == "direct_http":
            return observed_links(source["url"], decoded)
        links = []
        # Exact public URL strings in JSON/PDF text; no constructed publisher paths.
        for match in re.finditer(r"https?://[^\s\"<>\\]+", static):
            target = match[0]
            with suppress(ValueError):
                safe_url(target)
                links.append(
                    {
                        "url": target,
                        "anchor": target,
                        "parent_url": source["url"],
                        "parent_decoded_sha256": source["decoded_sha256"],
                        "representation": "static_text",
                        "start": match.start(),
                        "end": match.end(),
                    }
                )
        return links

    async def source(self, url: str) -> tuple[Path, dict[str, Any], str, str]:
        if url not in self.allowed:
            raise ValueError("Unregistered URL: use an actual search row or observed href")
        if url in self.failures:
            raise ValueError("Cached unsuccessful attempt: " + self.failures[url])
        if url not in self.records:
            if self.mode != "live":
                raise ValueError("Source absent from replay fixture; no live fallback")
            kind = "structured_orcid" if url.startswith(ORCID_API + "/") else "direct_http"
            if url.lower().split("?", 1)[0].endswith(".pdf") or "/pdf/" in url:
                kind = "direct_pdf"
            try:
                source = await PublicLoader(self.directory, [url], self.root, self.aid).load(
                    url, kind=kind
                )
            except (ValueError, OSError) as exc:
                self.failures[url] = str(exc)
                raise
            final = source["url"]
            self.allowed.setdefault(final, self.allowed[url])
            path = self.directory / f"source-{digest(final.encode())}.json"
            self.records[url] = self.records[final] = path
        path = self.records[url]
        source = dict(read(path))
        if self.mode == "replay":
            from enrichment_glm_compare import legacy_pdf_text

            decoded, static = checked_source(
                path.parent, source, pdf_extractor=lambda raw: legacy_pdf_text(self.root, raw)
            )
        else:
            decoded, static = checked_source(path.parent, source)
        depth = self.allowed[url]
        for link in self.links(source, decoded, static):
            if depth < 6:
                self.allowed.setdefault(link["url"], depth + 1)
        return path, source, decoded, static

    async def render(self, url: str) -> None:
        parent, source, body, _ = await self.source(url)
        if source.get("rendering_method"):
            return
        tags = re.findall(r"<script\b[^>]*>", body, re.I)
        found = []
        for tag in tags:
            match = re.search(r"\bsrc\s*=\s*['\"]([^'\"]+)['\"]", tag, re.I)
            if match and "func_string.js" in match[1]:
                found.append((tag, match[1], urljoin(source["url"], match[1])))
        if len(found) != 1 or "document.write(decode_email(" not in body:
            raise ValueError("No supported literal public renderer")
        tag, src, target = found[0]
        safe_url(target)
        if self.mode != "live":
            raise ValueError("Unrendered replay source; no live decoder fetch")
        # Ordinary observed script, same robots/access policy as HTML; raw receipt
        # can be usable JS even when HTML decoding intentionally refuses it.
        with suppress(ValueError, UnicodeError):
            await PublicLoader(self.directory, [target], self.root, self.aid).load(target)
        receipt = (
            self.directory / f"request-result-{digest(('direct_http\0' + target).encode())}.json"
        )
        if not receipt.exists():
            raise ValueError("No decoder receipt")
        js = read(receipt)
        if (
            js["status"] != 200
            or not js["complete"]
            or "javascript" not in (js["content_type"] or "")
        ):
            raise ValueError("Decoder inaccessible; no bypass")
        raw = (receipt.parent / js["body_path"]).read_bytes()
        if digest(raw) != js["body_sha256"]:
            raise ValueError("Decoder bytes changed")
        rendered = render_mathnet_contacts(body, raw)
        static = extract(rendered, source["url"])["text"]
        destination = self.root / "rendered-sources" / self.aid / digest(url.encode())
        destination.mkdir(parents=True, exist_ok=False)
        for file in parent.parent.iterdir():
            if file.is_file() and file != parent:
                shutil.copyfile(file, destination / file.name)
        text_path = "rendered-text-" + digest(static.encode()) + ".txt"
        immutable_bytes(destination / text_path, static.encode())
        derivative = source | {
            "rendering_method": "mathnet-email-v1",
            "parent_source_path": str(parent),
            "parent_source_sha256": sha(parent),
            "decoder_receipt_path": str(receipt),
            "decoder_receipt_sha256": sha(receipt),
            "decoder_literal_tag": tag,
            "decoder_literal_src": src,
            "text_path": text_path,
            "text_sha256": digest(static.encode()),
        }
        path = destination / parent.name
        immutable_json(path, derivative)
        checked_source(destination, derivative)
        self.records[url] = self.records[source["url"]] = path

    async def tool(self, args: dict[str, Any]) -> dict[str, Any]:
        ensure_not_stopped(self.root)
        self.calls += 1
        if self.calls > 24:
            raise ValueError("Source tool call cap")
        action, url, query, start = (args[k] for k in ("action", "url", "query", "start"))
        if not isinstance(query, str) or len(query) > 300 or type(start) is not int or start < 0:
            raise ValueError("Invalid text view")
        if action == "replay_search":
            if self.mode != "replay":
                raise ValueError("Replay fixtures unavailable in live mode")
            return {"mode": "replay_fixture_NOT_live_discovery", "urls": list(self.records)}
        if action == "public_search":
            return await self.public_search(query)
        if action == "render":
            await self.render(url)
        path, source, decoded, static = await self.source(url)
        if action == "links":
            links = self.links(source, decoded, static)
            words = query.lower().split()
            matching = [
                x
                for x in links
                if not words or any(w in (x["anchor"] + x["url"]).lower() for w in words)
            ]
            return {
                "url": source["url"],
                "total_links": len(links),
                "matching": len(matching),
                "links": matching[start : start + 80],
                "next_start": start + 80,
                "renderer_available": "document.write(decode_email(" in decoded,
            }
        if query:
            hits = list(re.finditer(re.escape(query), static, re.I))[:12]
            windows = [
                {
                    "start": max(0, m.start() - 600),
                    "text": static[max(0, m.start() - 600) : m.end() + 1000],
                }
                for m in hits
            ]
        else:
            windows = [{"start": start, "text": static[start : start + 8000]}]
        candidates = [
            {"value": m[0], "quote": static[max(0, m.start() - 500) : m.end() + 500]}
            for m in list(EMAIL.finditer(static))[:32]
        ]
        return {
            "url": source["url"],
            "source_kind": source["source_kind"],
            "source_sha256": sha(path),
            "text_chars": len(static),
            "windows": windows,
            "contact_candidates_NOT_personal_verdicts": candidates,
            "renderer_available": "document.write(decode_email(" in decoded,
            "replay": self.mode == "replay",
        }

    async def bind(self, result: dict[str, Any]) -> dict[str, Any]:
        pool: dict[str, Any] = {}

        async def evidence(row: dict[str, Any]) -> str:
            if row["url"] not in self.records:
                raise ValueError("No saved tool body: binding cannot initiate HTTP")
            path, source, decoded, static = await self.source(row["url"])
            quote = row["quote"]
            if not isinstance(quote, str) or not 1 <= len(quote) <= 3000:
                raise ValueError("Quote length")
            body, representation = (
                (static, "static_text") if quote in static else (decoded, "html_literal")
            )
            if quote not in body:
                raise ValueError("GLM quote not in saved source")
            start = body.index(quote)
            ref = f"E{len(pool) + 1:04d}"
            pool[ref] = {
                "url": source["url"],
                "excerpt": quote,
                "checked_at": source["checked_at"],
                "information_date": None,
                "object_type": "scientist",
                "source_kind": source["source_kind"],
                "body_sha256": source["body_sha256"],
                "text_sha256": source["text_sha256"],
                "representation": representation,
                "start": start,
                "end": start + len(quote),
                "source_record_path": str(path),
                "source_record_sha256": sha(path),
            }
            return ref

        if result.get("author_id") != self.aid or len(result.get("items", [])) > 16:
            raise ValueError("Wrong author/item cap")
        items: list[dict[str, Any]] = []
        for row in result["items"]:
            ref = await evidence(row)
            if row["field"] == "personal_contact" and row["value"] not in re.sub(
                r"\s+", "", row["quote"]
            ):
                raise ValueError("Contact value not literal (whitespace normalization only)")
            items.append(
                {
                    "item_id": f"claim_{len(items) + 1:03d}",
                    "field": row["field"],
                    "value": row["value"],
                    "evidence_refs": [ref],
                }
            )
        profile_evidence = {}
        for key in ("identity", "current_affiliation"):
            if len(result["profile_evidence"][key]) > 8:
                raise ValueError("Profile evidence cap")
            profile_evidence[key] = [await evidence(row) for row in result["profile_evidence"][key]]
        if len(pool) > 32 or sum(len(x["excerpt"]) for x in pool.values()) > 48000:
            raise ValueError("Evidence context cap")
        return {
            "author_id": self.aid,
            "items": items,
            "evidence_pool": pool,
            "profile_evidence": profile_evidence,
            "field_statuses": {},
            "provenance": {
                "agent_id": "pi-cli:glm-public-runner-v1:" + self.aid,
                "collector_kind": "glm_public_source_selection",
                "model_called": True,
            },
        }
