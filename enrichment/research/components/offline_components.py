"""Frozen saved-source extraction comparison for #198; never fetches sources.

freeze reads source metadata only; replay cannot read human answers. evaluate
compares already sealed candidates with human8, without changing extraction.
"""

import argparse
import hashlib
import importlib.metadata
import json
import os
import resource
import socket
import time
from collections import Counter
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import unquote

FROZEN10 = (
    "A5070748575",
    "A5047877230",
    "A5006480668",
    "A5011172734",
    "A5069670094",
    "A5054791318",
    "A5065694561",
    "A5054586424",
    "A5089458364",
    "A5042154547",
)
PACKAGES = (
    "beautifulsoup4",
    "lxml",
    "trafilatura",
    "pypdf",
    "pdfplumber",
    "FindYourProfessor",
    "httpx",
)
RULES = {
    "version": "saved-source-v1",
    "emails": "runtime EMAIL regexp; exact literal only; lower-case for comparison",
    "html": (
        "control visible text + mailto + same-host image email query; "
        "bs4 visible text + mailto; trafilatura default plain text only; "
        "FindYourProfessor.extract_emails on raw HTML"
    ),
    "pdf": "default page.extract_text; no OCR, no inferred reconstruction",
    "orcid": "person.emails.email with public visibility only; no search in works",
    "attribution": "all extracted values are candidates; no automatic personal acceptance",
    "dates": "source information_date retained as metadata, not current applicability",
    "network": "socket connect blocked during replay; no profile/model jobs",
    "limits": (
        "25 sources, 10 frozen IDs, body <=8MiB PDF/2MiB other, PDF <=100 pages, text <=1M chars"
    ),
}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read(path: Path) -> Any:
    return json.loads(path.read_text())


def save(path: Path, obj: Any) -> None:
    with path.open("x") as file:
        json.dump(obj, file, ensure_ascii=False, indent=2)
    path.chmod(0o600)


def freeze(baseline: Path, root: Path) -> None:
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    sources = []
    for path in sorted((baseline / "sources").glob("*/source-*.json")):
        meta = read(path)
        sources.append(
            {
                "author_id": path.parent.name,
                "metadata_path": str(path),
                "metadata_sha256": sha(path.read_bytes()),
                **{
                    k: meta[k]
                    for k in (
                        "url",
                        "source_kind",
                        "body_sha256",
                        "body_bytes",
                        "decoded_sha256",
                        "text_sha256",
                    )
                },
                "body_path": str(path.parent / meta["body_path"]),
                "decoded_path": str(path.parent / meta["decoded_path"]),
                "information_date": meta.get("information_date"),
            }
        )
    if len(sources) != 25:
        raise ValueError("Expected 25 sources")
    if set(s["author_id"] for s in sources) != set(FROZEN10):
        raise ValueError("Frozen10 mismatch")
    if Counter(s["source_kind"] for s in sources) != {
        "structured_orcid": 10,
        "direct_http": 11,
        "direct_pdf": 4,
    }:
        raise ValueError("Format counts mismatch")
    packages = {}
    for name in PACKAGES:
        m = importlib.metadata.metadata(name)
        packages[name] = {
            "version": importlib.metadata.version(name),
            "license": m.get("License-Expression") or m.get("License"),
            "classifiers": m.get_all("Classifier") or [],
        }
    save(
        root / "manifest.json",
        {
            "created_at": datetime.now(UTC).isoformat(),
            "rules": RULES,
            "script_sha256": sha(Path(__file__).read_bytes()),
            "sources": sources,
            "runtime_files": {
                str(p.relative_to(Path(__file__).resolve().parents[2])): sha(p.read_bytes())
                for p in (Path(__file__).resolve().parents[2] / "src/sfr_enrichment").glob("*.py")
            },
            "packages": packages,
            "python": os.sys.version,
            "baseline": str(baseline),
            "skips": {
                "GROBID": "optional server/models installation not justified for four text PDFs",
                "Scrapy": "offline extraction answers primary question; no loading claim",
                "Crawl4AI": "no justified JS case with observable hard cap of internal requests",
            },
        },
    )


def blocked(*args: Any, **kwargs: Any) -> Any:
    raise RuntimeError("Offline replay forbids network")


def parse(kind: str, raw: bytes, decoded: str, url: str) -> tuple[str, list[dict[str, str]]]:
    from sfr_enrichment.contacts import ContactsHTML
    from sfr_enrichment.http_policy import extract
    from sfr_enrichment.sources import pdf_text

    if kind == "control":
        parser = ContactsHTML(url)
        parser.feed(decoded)
        extras = parser.mailto + parser.image_contacts
        return extract(decoded, url)["text"], extras
    if kind == "bs4-lxml":
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(decoded, "lxml")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        extras = [
            {"value": unquote(str(a["href"])[7:].split("?", 1)[0]), "quote": str(a)}
            for a in soup.select("a[href]")
            if str(a["href"]).lower().startswith("mailto:")
        ]
        return soup.get_text("\n", strip=True), extras
    if kind == "findyourprofessor":
        from FindYourProfessor import extract_emails

        return "", [
            {
                "value": v,
                "quote": decoded[max(0, decoded.find(v) - 160) : decoded.find(v) + len(v) + 160],
            }
            for v in extract_emails(decoded)
        ]
    if kind == "trafilatura":
        import trafilatura

        return trafilatura.extract(decoded) or "", []
    if kind == "pypdf":
        return pdf_text(raw), []
    if kind == "pdfplumber":
        import pdfplumber

        with pdfplumber.open(BytesIO(raw)) as pdf:
            if len(pdf.pages) > 100:
                raise ValueError("PDF page budget")
            return "\n".join(p.extract_text() or "" for p in pdf.pages), []
    if kind == "orcid-json":
        from sfr_enrichment.common import public_candidates

        emails = public_candidates(json.loads(raw))["emails"]
        return "\n".join(e["email"] for e in emails), []
    raise ValueError(kind)


def replay(root: Path) -> None:
    from sfr_enrichment.contacts import EMAIL

    manifest = read(root / "manifest.json")
    module_root = Path(__file__).resolve().parents[2]
    for rel, expected in manifest["runtime_files"].items():
        if sha((module_root / rel).read_bytes()) != expected:
            raise ValueError("Runtime changed after freeze")
    for name, meta in manifest["packages"].items():
        if importlib.metadata.version(name) != meta["version"]:
            raise ValueError("Package version differs from freeze")
    if manifest["script_sha256"] != sha(Path(__file__).read_bytes()):
        raise ValueError("Script changed after freeze")
    socket.socket.connect_ex = blocked  # type: ignore[method-assign]
    socket.socket.connect = blocked  # type: ignore[method-assign]
    socket.create_connection = blocked
    rows = []
    started = time.monotonic()
    cpu = time.process_time()
    for source in manifest["sources"]:
        meta_path = Path(source["metadata_path"])
        if sha(meta_path.read_bytes()) != source["metadata_sha256"]:
            raise ValueError("Metadata SHA mismatch")
        raw = Path(source["body_path"]).read_bytes()
        decoded_bytes = Path(source["decoded_path"]).read_bytes()
        if sha(raw) != source["body_sha256"] or sha(decoded_bytes) != source["decoded_sha256"]:
            raise ValueError("Source SHA mismatch")
        kinds = {
            "direct_http": ["control", "bs4-lxml", "trafilatura", "findyourprofessor"],
            "direct_pdf": ["pypdf", "pdfplumber"],
            "structured_orcid": ["orcid-json"],
        }[source["source_kind"]]
        cap = 8388608 if source["source_kind"] == "direct_pdf" else 2097152
        if len(raw) > cap:
            raise ValueError("Source size budget")
        for kind in kinds:
            start, before = time.monotonic(), time.process_time()
            row = {
                k: source[k]
                for k in ("author_id", "url", "source_kind", "body_sha256", "information_date")
            }
            try:
                text, extras = parse(kind, raw, decoded_bytes.decode(), source["url"])
                if len(text) > 1000000:
                    raise ValueError("Text budget")
                candidates = []
                for match in EMAIL.finditer(text):
                    candidates.append(
                        {
                            "value": match[0],
                            "channel": "text",
                            "quote": text[max(0, match.start() - 160) : match.end() + 160],
                        }
                    )
                candidates.extend(
                    {"value": v["value"], "channel": "attribute", "quote": v["quote"]}
                    for v in extras
                    if EMAIL.fullmatch(v["value"])
                )
                row.update(
                    status="ok",
                    text_sha256=sha(text.encode()),
                    text_chars=len(text),
                    candidates=candidates,
                    accepted_personal=[],
                    identity="not_checked",
                    current="unknown",
                )
            except Exception as exc:
                row.update(status="error", error=f"{type(exc).__name__}: {exc}", candidates=[])
            row.update(
                tool=kind,
                seconds=time.monotonic() - start,
                cpu_seconds=time.process_time() - before,
            )
            rows.append(row)
    result = {
        "manifest_sha256": sha((root / "manifest.json").read_bytes()),
        "rows": rows,
        "HTTP_source_requests": 0,
        "profile_model_jobs": 0,
        "human_minutes": 0,
        "wall_seconds": time.monotonic() - started,
        "cpu_seconds": time.process_time() - cpu,
        "peak_rss_platform_units": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "rss_units": "bytes on macOS, KiB on Linux; process including imports",
    }
    save(root / "replay.json", result)


def evaluate(root: Path, human: Path) -> None:
    replayed = read(root / "replay.json")
    if replayed["manifest_sha256"] != sha((root / "manifest.json").read_bytes()):
        raise ValueError("Manifest changed after replay")
    answers = read(human)
    known = {}
    for item in answers["comparisons"]:
        dims = item["human"]["dimensions"]
        if dims["text"] == dims["identity"] == "agree":
            known[item["author_id"]] = item
    if len(known) != 8:
        raise ValueError("Expected human8")
    summary = []
    for author_id in FROZEN10:
        for tool in (
            "control",
            "bs4-lxml",
            "trafilatura",
            "pypdf",
            "pdfplumber",
            "orcid-json",
            "findyourprofessor",
        ):
            rows = [
                r for r in replayed["rows"] if r["author_id"] == author_id and r["tool"] == tool
            ]
            values = {c["value"].lower() for r in rows for c in r["candidates"]}
            reference = known.get(author_id)
            recovered = bool(reference and reference["collector_value"].lower() in values)
            summary.append(
                {
                    "author_id": author_id,
                    "tool": tool,
                    "sources": len(rows),
                    "candidate_count": len(values),
                    "known_human8_recovered": int(recovered),
                    "known_human8_loss": int(bool(reference) and bool(rows) and not recovered),
                    "unmatched_candidates_need_review": len(values) - int(recovered),
                    "automatic_accepted": 0,
                    "new_human_reviewed": 0,
                    "reference_date": reference["verifier"]["information_date"]
                    if reference
                    else None,
                    "reference_applicability": reference["verifier"]["current_applicability"]
                    if reference
                    else None,
                    "current": "uncertain" if reference else "unknown",
                }
            )
    save(
        root / "evaluation.json",
        {
            "human_record_path": str(human),
            "human_sha256": sha(human.read_bytes()),
            "replay_sha256": sha((root / "replay.json").read_bytes()),
            "reference_scope": "human8 text+identity only, not profile/current gold",
            "rows": summary,
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["freeze", "replay", "evaluate"])
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--human", type=Path)
    args = parser.parse_args()
    if args.phase == "freeze":
        if args.baseline is None:
            parser.error("--baseline required")
        freeze(args.baseline.resolve(), args.root.resolve())
    elif args.phase == "replay":
        replay(args.root.resolve())
    else:
        if args.human is None:
            parser.error("--human required")
        evaluate(args.root.resolve(), args.human.resolve())


if __name__ == "__main__":
    main()
