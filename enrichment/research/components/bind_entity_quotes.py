"""Bind existing extracted values to original HTML entity lines; no new candidates."""

import argparse
import html
from pathlib import Path
from typing import Any

import offline_components as base


def original_line(text: str, value: str) -> dict[str, Any] | None:
    offset = 0
    for line in text.splitlines(keepends=True):
        if value.lower() in html.unescape(line).lower():
            return {
                "kind": "stdlib_html_entity_line",
                "start": offset,
                "end": offset + len(line),
                "original_quote": line,
                "quote_sha256": base.sha(line.encode()),
            }
        offset += len(line)
    return None


def bind(root: Path, prefix: str = "", input_prefix: str = "") -> None:
    base.save(
        root / f"{prefix}entity-binding-manifest.json",
        {
            "script_sha256": base.sha(Path(__file__).read_bytes()),
            "rule": (
                "Post-extraction provenance only: stdlib html.unescape per original line; "
                "no new or changed email candidates"
            ),
            "provenance_sha256": base.sha(
                (root / f"{input_prefix}preprocessing-provenance.json").read_bytes()
            ),
        },
    )
    provenance = base.read(root / f"{input_prefix}preprocessing-provenance.json")
    sources = {s["url"]: s for s in base.read(root / "manifest.json")["sources"]}
    rows = []
    for row in provenance["rows"]:
        source = sources[row["url"]]
        binding = row["original_binding"]
        if binding is None and source["source_kind"] == "direct_http":
            decoded = Path(source["decoded_path"]).read_bytes()
            if base.sha(decoded) != source["decoded_sha256"]:
                raise ValueError("Original decoded SHA changed")
            binding = original_line(decoded.decode(), row["value"])
        rows.append(row | {"original_binding": binding})
    base.save(
        root / f"{prefix}original-quote-bindings.json",
        {
            "entity_binding_manifest_sha256": base.sha(
                (root / f"{prefix}entity-binding-manifest.json").read_bytes()
            ),
            "rows": rows,
            "unbound_candidates": sum(r["original_binding"] is None for r in rows),
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--prefix", default="")
    parser.add_argument("--input-prefix", default="")
    args = parser.parse_args()
    bind(args.root.resolve(), args.prefix, args.input_prefix)
