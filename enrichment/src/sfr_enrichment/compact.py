"""Lossless transport of literal evidence; canonical input remains unchanged."""

import json
from copy import deepcopy
from typing import Any

FORMAT = "literal-union-v1"


def encode(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def compact_input(source: dict[str, Any]) -> dict[str, Any]:
    pool = source["evidence_pool"]
    groups: dict[tuple[str, str, str], list[tuple[str, dict[str, Any]]]] = {}
    for ref, row in sorted(pool.items()):
        if (
            type(row["start"]) is not int
            or type(row["end"]) is not int
            or not 0 <= row["start"] < row["end"]
            or len(row["excerpt"]) != row["end"] - row["start"]
        ):
            raise ValueError("Invalid literal span")
        key = (row["source_record_path"], row["source_record_sha256"], row["representation"])
        groups.setdefault(key, []).append((ref, row))
    blocks: dict[str, Any] = {}
    aliases: dict[str, Any] = {}
    for key in sorted(groups):
        rows = groups[key]
        metadata = [
            {k: v for k, v in row.items() if k not in ("excerpt", "start", "end")}
            for _, row in rows
        ]
        common = {
            k: v
            for k, v in metadata[0].items()
            if all(k in meta and meta[k] == v for meta in metadata)
        }
        spans: list[dict[str, Any]] = []
        for ref, row in sorted(rows, key=lambda pair: (pair[1]["start"], pair[1]["end"], pair[0])):
            start, end, text = row["start"], row["end"], row["excerpt"]
            if spans and start <= spans[-1]["end"]:
                span = spans[-1]
                overlap_end = min(end, span["end"])
                if (
                    text[: overlap_end - start]
                    != span["excerpt"][start - span["start"] : overlap_end - span["start"]]
                ):
                    raise ValueError("Conflicting overlapping evidence")
                if end > span["end"]:
                    span["excerpt"] += text[span["end"] - start :]
                    span["end"] = end
                span["refs"].append(ref)
            else:
                spans.append({"start": start, "end": end, "excerpt": text, "refs": [ref]})
        by_ref = dict(rows)
        for span in spans:
            block_id = f"B{len(blocks) + 1:04d}"
            refs = span.pop("refs")
            blocks[block_id] = {"source": common, **span}
            for ref in refs:
                row = by_ref[ref]
                aliases[ref] = {
                    "block_id": block_id,
                    "start": row["start"],
                    "end": row["end"],
                    "metadata": {
                        k: v
                        for k, v in row.items()
                        if k not in common and k not in ("start", "end", "excerpt")
                    },
                }
    result = deepcopy(source)
    result["evidence_pool"] = aliases
    result["evidence_blocks"] = blocks
    result["evidence_transport"] = FORMAT
    if expand_input(result) != source:
        raise ValueError("Lossless evidence reconstruction failed")
    return result


def expand_input(compact: dict[str, Any]) -> dict[str, Any]:
    if compact.get("evidence_transport") != FORMAT:
        raise ValueError("Unknown evidence transport")
    result = deepcopy(compact)
    blocks = result.pop("evidence_blocks")
    result.pop("evidence_transport")
    pool = {}
    for ref, alias in result["evidence_pool"].items():
        block = blocks.get(alias["block_id"])
        if block is None or not block["start"] <= alias["start"] < alias["end"] <= block["end"]:
            raise ValueError("Unknown block or evidence range")
        if len(block["excerpt"]) != block["end"] - block["start"]:
            raise ValueError("Invalid block length")
        if set(alias["metadata"]) & set(block["source"]):
            raise ValueError("Conflicting alias metadata")
        pool[ref] = {
            **block["source"],
            **alias["metadata"],
            "start": alias["start"],
            "end": alias["end"],
            "excerpt": block["excerpt"][
                alias["start"] - block["start"] : alias["end"] - block["start"]
            ],
        }
    refs = [ref for item in result["items"] for ref in item["evidence_refs"]]
    refs += [ref for values in result["profile_evidence"].values() for ref in values]
    if any(ref not in pool for ref in refs):
        raise ValueError("Unknown evidence ID")
    result["evidence_pool"] = pool
    return result
