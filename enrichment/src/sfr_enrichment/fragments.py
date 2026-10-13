"""Literal source corpus and typed date provenance; no experimental runners."""

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from sfr_enrichment.contacts import EMAIL

DATE_GUARD_POLICY = "fragment-date-v2-orcid-employment-ms"


def catalog(author_id: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    """All saved text, fixed overlap; no model-driven snippets or contact attribution."""
    fragments: dict[str, Any] = {}
    values: dict[str, Any] = {}
    sources = []
    for record in sorted(records, key=lambda r: (r["url"], r["body_sha256"], r["text_sha256"])):
        text = record["text"]
        if hashlib.sha256(text.encode()).hexdigest() != record["text_sha256"]:
            raise ValueError("Source text changed")
        source_id = (
            author_id
            + "-S"
            + hashlib.sha256(
                (record["url"] + record["body_sha256"] + record["text_sha256"]).encode()
            ).hexdigest()[:20]
        )
        sources.append(
            {
                k: record[k]
                for k in ("url", "body_sha256", "text_sha256", "source_kind", "checked_at")
            }
            | {
                "source_id": source_id,
                "characters": len(text),
                "representation": record.get("representation", "checked_static"),
            }
        )
        intervals = []
        for start in range(0, len(text), 1500):
            end = min(start + 1800, len(text))
            ref = f"{source_id}-F{start}-{end}"
            fragments[ref] = {
                "source_id": source_id,
                "start": start,
                "end": end,
                "excerpt": text[start:end],
            }
            values[ref + "-text"] = {"kind": "text", "fragment_id": ref, "start": start, "end": end}
            intervals.append((start, end, ref))
        for match in EMAIL.finditer(text):
            containing = next(
                (r for s, e, r in intervals if s <= match.start() and match.end() <= e), None
            )
            if containing is None:
                raise ValueError("Literal email crosses all fragment boundaries")
            key = f"{source_id}-M{match.start()}-{match.end()}"
            values[key] = {
                "kind": "email",
                "fragment_id": containing,
                "start": match.start(),
                "end": match.end(),
                "literal": match.group(),
            }
    return {"sources": sources, "fragments": fragments, "values": values}


def _json_span(text: str, path: list[str | int]) -> tuple[int, int]:
    """Locate a direct JSON child, skipping complete sibling values (not regex matches)."""
    decoder = json.JSONDecoder()
    start = len(text) - len(text.lstrip())
    for part in path:
        cursor = start + 1
        index = 0
        while True:
            cursor += len(text[cursor:]) - len(text[cursor:].lstrip())
            if isinstance(part, str):
                key, cursor = decoder.raw_decode(text, cursor)
                cursor += len(text[cursor:]) - len(text[cursor:].lstrip())
                if text[cursor] != ":":
                    raise ValueError("Invalid JSON field")
                cursor += 1
            else:
                key = index
            cursor += len(text[cursor:]) - len(text[cursor:].lstrip())
            _, end = decoder.raw_decode(text, cursor)
            if key == part:
                start = cursor
                break
            cursor = end + len(text[end:]) - len(text[end:].lstrip())
            if text[cursor] != ",":
                raise ValueError("JSON path absent")
            cursor += 1
            index += 1
    return start, json.JSONDecoder().raw_decode(text, start)[1]


def _orcid_employment_date(
    corpus: dict[str, Any], assessment: dict[str, Any], axis: str
) -> dict[str, Any]:
    """Bind metadata to one cited employment, never to reading time or a nearby object."""
    if axis != "current_affiliation":
        raise ValueError("Unsupported metadata date object")
    date = assessment["information_date"]
    if not re.fullmatch(r"\d{4}(?:-\d{2}){0,2}", date):
        raise ValueError("Invalid metadata calendar date")
    refs = [corpus["fragments"][ref] for ref in assessment["evidence_refs"]]
    orcid = corpus["profile"].get("orcid", "").removeprefix("https://orcid.org/")
    candidates = []
    for source in corpus["sources"]:
        if source["source_kind"] != "structured_orcid" or source["url"] != (
            f"https://pub.orcid.org/v3.0/{orcid}/record"
        ):
            continue
        cited = [ref for ref in refs if ref["source_id"] == source["source_id"]]
        if not cited:
            continue
        fragments = sorted(
            (f for f in corpus["fragments"].values() if f["source_id"] == source["source_id"]),
            key=lambda f: f["start"],
        )
        text = ""
        for fragment in fragments:
            start, end = fragment["start"], fragment["end"]
            if (
                start > len(text)
                or text[start : min(end, len(text))]
                != fragment["excerpt"][: max(0, min(end, len(text)) - start)]
            ):
                raise ValueError("ORCID fragments have gaps or inconsistent overlaps")
            text += fragment["excerpt"][max(0, len(text) - start) :]
        if (
            len(text) != source["characters"]
            or hashlib.sha256(text.encode()).hexdigest() != (source["text_sha256"])
        ):
            raise ValueError("ORCID source text changed")

        def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            if len({key for key, _ in pairs}) != len(pairs):
                raise ValueError("Duplicate ORCID JSON key")
            return dict(pairs)

        record = json.loads(text, object_pairs_hook=unique_object)
        if record.get("orcid-identifier", {}).get("path") != orcid:
            raise ValueError("ORCID metadata belongs to another profile")

        def covered(
            path: list[str | int],
            saved_text: str = text,
            cited_fragments: list[dict[str, Any]] = cited,
        ) -> bool:
            start, end = _json_span(saved_text, path)
            cursor = start
            for ref in sorted(cited_fragments, key=lambda entry: entry["start"]):
                if ref["start"] <= cursor < ref["end"]:
                    cursor = max(cursor, ref["end"])
            return cursor >= end

        groups = (
            record.get("activities-summary", {}).get("employments", {}).get("affiliation-group", [])
        )
        for i, group in enumerate(groups):
            for j, summary in enumerate(group.get("summaries", [])):
                employment = summary.get("employment-summary", {})
                path: list[str | int] = [
                    "activities-summary",
                    "employments",
                    "affiliation-group",
                    i,
                    "summaries",
                    j,
                    "employment-summary",
                ]
                put_code = employment.get("put-code")
                if (
                    not isinstance(put_code, int)
                    or isinstance(put_code, bool)
                    or not employment.get("organization", {}).get("name")
                    or employment.get("path") != f"/{orcid}/employment/{put_code}"
                ):
                    continue
                if not all(
                    covered([*path, *suffix])
                    for suffix in (["put-code"], ["path"], ["organization", "name"])
                ):
                    continue
                # Bind the object before comparing dates: two cited employments are ambiguous.
                candidates.append((source, text, employment, path, covered))
    if len(candidates) != 1:
        raise ValueError("Metadata date needs exactly one cited employment object")
    source, text, employment, path, covered = candidates[0]
    matches = []
    for field in ("created-date", "last-modified-date"):
        value = employment.get(field, {}).get("value") if employment.get(field) else None
        # The bounded policy accepts 13-digit ORCID epoch milliseconds, not epoch seconds.
        if not isinstance(value, int) or isinstance(value, bool) or not 10**12 <= value < 10**13:
            continue
        if not covered([*path, field]):
            continue
        instant = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(milliseconds=value)
        checked = datetime.fromisoformat(source["checked_at"])
        if checked.tzinfo is None or instant > checked:
            continue
        if instant.date().isoformat()[: len(date)] == date:
            matches.append(
                {
                    "source_id": source["source_id"],
                    "json_path": [*path, field, "value"],
                    "epoch_milliseconds": value,
                    "utc": instant.isoformat(),
                    "information_date": date,
                    "evidence_refs": assessment["evidence_refs"],
                    "object_path": employment["path"],
                }
            )
    if len(matches) != 1:
        raise ValueError("Date does not match one cited ORCID employment metadata field")
    return matches[0]


def check_dates(corpus: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Same date provenance guard for independently assessed live candidates."""
    pool = corpus["fragments"]
    # Literal year presence is a provenance check, not proof of date attribution.
    date_bindings = []
    assessments = [("item", a) for a in result["items"]] + list(
        result["profile_assessments"].items()
    )
    for axis, assessment in assessments:
        date = assessment["information_date"]
        if date is not None:
            years = re.findall(r"(?<!\d)\d{4}(?!\d)", date)
            body = "\n".join(pool[ref]["excerpt"] for ref in assessment["evidence_refs"])
            if assessment["date_basis"] == "source_metadata":
                try:
                    binding = _orcid_employment_date(corpus, assessment, axis)
                except (AttributeError, IndexError, KeyError, TypeError, OverflowError) as error:
                    raise ValueError("Invalid typed ORCID metadata") from error
                date_bindings.append(binding)
                continue
            if not years or not set(years) <= set(re.findall(r"(?<!\d)\d{4}(?!\d)", body)):
                raise ValueError("Date year absent from referenced saved evidence")
    return {"policy": DATE_GUARD_POLICY, "metadata_bindings": date_bindings}
