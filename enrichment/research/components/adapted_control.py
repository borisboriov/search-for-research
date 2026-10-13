"""One post-observation control using existing safe project preprocessing (#198)."""

import argparse
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import offline_components as base

from sfr_enrichment.contacts import flexible_email_matches
from sfr_enrichment.sources import render_mathnet_contacts

SCRIPT_BLOCK = re.compile(r"<script\b[^>]*>.*?</script>", re.I | re.S)
SCRIPT_SRC = re.compile(r"<script\b[^>]*\bsrc\s*=\s*[\'\"]([^\'\"]+)[\'\"][^>]*>", re.I)


def normalize(text: str) -> str:
    """Existing whitespace rule, right-to-left replacement preserves source spans."""
    for value, start, end in reversed(list(flexible_email_matches(text))):
        text = text[:start] + value + text[end:]
    return text


def decoder_urls(text: str, url: str) -> list[str]:
    return [urljoin(url, m[1]) for m in SCRIPT_SRC.finditer(text) if "func_string.js" in m[1]]


def freeze(baseline: Path, root: Path) -> None:
    base.freeze(baseline, root)
    urls = set()
    manifest = base.read(root / "manifest.json")
    for source in manifest["sources"]:
        if source["source_kind"] == "direct_http":
            urls.update(decoder_urls(Path(source["decoded_path"]).read_text(), source["url"]))
    receipts = {}
    for path in sorted((baseline / "sources").glob("*/request-result-*.json")):
        record = base.read(path)
        if record["url"] not in urls or record["url"] in receipts:
            continue
        if not record.get("complete") or record["status"] != 200:
            continue
        if "javascript" not in (record.get("content_type") or ""):
            continue
        body = path.parent / record["body_path"]
        if base.sha(body.read_bytes()) != record["body_sha256"]:
            raise ValueError("Decoder cache SHA mismatch")
        receipts[record["url"]] = {
            "receipt_path": str(path),
            "receipt_sha256": base.sha(path.read_bytes()),
            "body_path": str(body),
            "body_sha256": record["body_sha256"],
        }
    base.save(
        root / "adaptation.json",
        {
            "adapter_sha256": base.sha(Path(__file__).read_bytes()),
            "rules": (
                "Post-observation adaptation, not independent test: same safe project renderer "
                "and whitespace normalization for all HTML parsers; same whitespace "
                "normalization after both PDF extractors; no OCR/guesses/arbitrary JS/network"
            ),
            "decoder_receipts": receipts,
            "parent_manifest_sha256": base.sha((root / "manifest.json").read_bytes()),
        },
    )


def preprocess(text: str, url: str, receipts: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    transforms = []
    targets = decoder_urls(text, url)
    if len(targets) == 1 and targets[0] in receipts and "document.write(decode_email(" in text:
        receipt = receipts[targets[0]]
        path = Path(receipt["receipt_path"])
        script = Path(receipt["body_path"]).read_bytes()
        if (
            base.sha(path.read_bytes()) != receipt["receipt_sha256"]
            or base.sha(script) != receipt["body_sha256"]
        ):
            raise ValueError("Frozen decoder changed")
        for match in SCRIPT_BLOCK.finditer(text):
            if "document.write(decode_email(" in match[0]:
                replacement = render_mathnet_contacts(match[0], script)
                if replacement != match[0]:
                    transforms.append(
                        {
                            "kind": "project_mathnet_email_v1",
                            "start": match.start(),
                            "end": match.end(),
                            "original_quote": match[0],
                            "replacement": replacement,
                            "decoder_body_sha256": receipt["body_sha256"],
                        }
                    )
        text = render_mathnet_contacts(text, script)
    return normalize(text), transforms


def replay(root: Path) -> None:
    config = base.read(root / "adaptation.json")
    if config["adapter_sha256"] != base.sha(Path(__file__).read_bytes()):
        raise ValueError("Adapter changed after freeze")
    if config["parent_manifest_sha256"] != base.sha((root / "manifest.json").read_bytes()):
        raise ValueError("Parent manifest changed")
    original_parse = base.parse
    transforms_by_url = {}

    def adapted(kind: str, raw: bytes, decoded: str, url: str) -> tuple[str, list[dict[str, str]]]:
        if kind in ("control", "bs4-lxml", "trafilatura", "findyourprofessor"):
            decoded, transforms = preprocess(decoded, url, config["decoder_receipts"])
            transforms_by_url[url] = transforms
        text, extras = original_parse(kind, raw, decoded, url)
        if kind != "orcid-json":
            text = normalize(text)
        return text, extras

    base.parse = adapted
    base.replay(root)
    result = base.read(root / "replay.json")
    manifest = base.read(root / "manifest.json")
    sources = {s["url"]: s for s in manifest["sources"]}
    rows = []
    for row in result["rows"]:
        source = sources[row["url"]]
        original = Path(source["decoded_path"]).read_text()
        for candidate in row["candidates"]:
            value = candidate["value"]
            origin = None
            index = original.lower().find(value.lower())
            if index >= 0:
                origin = {"kind": "original_literal", "start": index, "end": index + len(value)}
            else:
                for normalized, start, end in flexible_email_matches(original):
                    if normalized.lower() == value.lower():
                        origin = {"kind": "original_spaced_literal", "start": start, "end": end}
                        break
            if origin is None:
                for transformation in transforms_by_url.get(row["url"], []):
                    if value.lower() in transformation["replacement"].lower():
                        origin = {
                            k: transformation[k]
                            for k in ("kind", "start", "end", "decoder_body_sha256")
                        }
                        break
            if origin is not None:
                origin["original_quote"] = original[origin["start"] : origin["end"]]
                origin["quote_sha256"] = base.sha(origin["original_quote"].encode())
            rows.append(
                {
                    "author_id": row["author_id"],
                    "tool": row["tool"],
                    "value": value,
                    "url": row["url"],
                    "source_body_sha256": row["body_sha256"],
                    "source_decoded_sha256": source["decoded_sha256"],
                    "derived_quote": candidate["quote"],
                    "original_binding": origin,
                    "accepted_personal": False,
                    "current": "unknown",
                }
            )
    base.save(
        root / "preprocessing-provenance.json",
        {
            "adaptation_sha256": base.sha((root / "adaptation.json").read_bytes()),
            "replay_sha256": base.sha((root / "replay.json").read_bytes()),
            "rows": rows,
            "unbound_candidates": sum(r["original_binding"] is None for r in rows),
            "transformation_records": transforms_by_url,
        },
    )


if __name__ == "__main__":
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
        base.evaluate(args.root.resolve(), args.human.resolve())
