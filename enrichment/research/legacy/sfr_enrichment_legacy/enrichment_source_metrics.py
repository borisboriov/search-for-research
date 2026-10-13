"""Вклад отдельных источников: частная карта URL и безопасные счётчики без контактов."""

import argparse
import re
from collections import Counter
from pathlib import Path
from typing import Any

from sfr_enrichment.evidence import identifier, immutable_json, source_family
from sfr_enrichment_legacy.enrichment_experiment import (
    FIELDS,
    STATUSES,
    private_root,
    read,
    sha,
    verified_sample,
)


def source_metrics(root: Path, version: str, run_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    root = private_root(root)
    directory = root / "verification" / identifier(version)
    run_id = identifier(run_id)
    sample = verified_sample(root)
    frozen_ids = {row["id"] for row in sample}
    entries: dict[str, list[dict[str, Any]]] = {}
    inputs = sorted((directory / "inputs").glob("*.json"))
    outputs = sorted((directory / "outputs" / run_id).glob("*.json"))
    linked_original: dict[str, set[str]] = {}
    unresolved_original: Counter[str] = Counter()
    linked_new: dict[str, set[str]] = {}
    additional_sources: Counter[str] = Counter()

    def add(
        author_id: str,
        stage: str,
        field: str,
        items: list[dict[str, Any]],
        field_status: str = "not_recorded",
    ) -> None:
        if field not in FIELDS or author_id not in frozen_ids:
            raise ValueError("Поле или профиль вне фиксированной схемы")
        if field_status not in (*STATUSES, "not_recorded", "new_finding"):
            raise ValueError("Неизвестный статус поля")
        for item in items:
            entries.setdefault(item["url"], []).append(
                {
                    "author_id": author_id,
                    "stage": stage,
                    "field": field,
                    "field_status": field_status,
                    "information_date": item["information_date"],
                }
            )

    for path in inputs:
        value = read(path)
        for claim in value["collector"]["claims"]:
            add(
                value["author_id"],
                "collector_evidence",
                claim["field"],
                claim["evidence"],
                value["collector"].get("field_status", {}).get(claim["field"], "not_recorded"),
            )
    for path in outputs:
        wrapper = read(path)
        value = wrapper["result"]
        if value["author_id"] not in frozen_ids or path.stem != value["author_id"]:
            raise ValueError("Результат вне фиксированной выборки")
        input_path = directory / "inputs" / f"{value['author_id']}.json"
        if wrapper["input_sha256"] != sha(input_path):
            raise ValueError("Результат не связан с входом")
        collector = read(input_path)["collector"]
        claims = {row["claim_id"]: row for row in collector["claims"]}
        for claim in value["claim_verdicts"]:
            if claim["verdict"] == "confirmed_by_source":
                original = claims[claim["claim_id"]]
                field = original["field"]
                if value["identity"]["verdict"] == "confirmed_by_source":
                    linked_original.setdefault(field, set()).add(value["author_id"])
                else:
                    unresolved_original[field] += 1
                if {row["url"] for row in claim["evidence"]} - {
                    row["url"] for row in original["evidence"]
                }:
                    additional_sources[field] += 1
                add(
                    value["author_id"],
                    "verifier_confirmed_original_evidence",
                    claims[claim["claim_id"]]["field"],
                    claim["evidence"],
                    collector.get("field_status", {}).get(
                        claims[claim["claim_id"]]["field"], "not_recorded"
                    ),
                )
        for finding in value["new_findings"]:
            if value["identity"]["verdict"] == "confirmed_by_source":
                linked_new.setdefault(finding["field"], set()).add(value["author_id"])
            add(
                value["author_id"],
                "verifier_new_finding_evidence",
                finding["field"],
                finding["evidence"],
                "new_finding",
            )
    private_sources = []
    safe_sources = []
    for number, (url, rows) in enumerate(sorted(entries.items()), 1):
        source_id = f"S{number:05d}"
        private_sources.append({"source_id": source_id, "url": url, "uses": rows})
        safe_sources.append(
            {
                "source_id": source_id,
                "family": source_family(url),
                "evidence_counts": dict(Counter(row["stage"] for row in rows)),
                "profiles": len({row["author_id"] for row in rows}),
                "field_status_evidence_counts": dict(Counter(row["field_status"] for row in rows)),
                "field_evidence_counts": dict(Counter(row["field"] for row in rows)),
                "dated_evidence": sum(row["information_date"] is not None for row in rows),
                "unknown_date_evidence": sum(row["information_date"] is None for row in rows),
                "information_year_counts": dict(
                    Counter(
                        match.group(1)
                        for row in rows
                        if isinstance(row["information_date"], str)
                        and (
                            match := re.fullmatch(
                                r"((?:19|20)\d{2})(?:-\d{2}(?:-\d{2})?)?",
                                row["information_date"],
                            )
                        )
                    )
                ),
            }
        )
    denominators = {"sample": len(sample), "inputs": len(inputs), "outputs": len(outputs)}
    common = {"version": version, "run_id": run_id, "denominators": denominators}
    return (
        {**common, "sources": private_sources},
        {
            **common,
            "sources": safe_sources,
            "analysis_version": "source_diagnostics_v1",
            "identity_linked_confirmed_original_profiles_by_field": {
                field: len(ids) for field, ids in sorted(linked_original.items())
            },
            "confirmed_original_claims_with_unresolved_identity_by_field": dict(
                sorted(unresolved_original.items())
            ),
            "identity_linked_new_finding_profiles_by_field": {
                field: len(ids) for field, ids in sorted(linked_new.items())
            },
            "confirmed_original_claims_using_additional_source_by_field": dict(
                sorted(additional_sources.items())
            ),
            "note": (
                "Evidence references, not accuracy. New findings are separate; "
                "no human gold standard. Year counts use literal ISO-like information dates; "
                "checking today does not refresh an old offer. Identity-linked counts do not "
                "establish current availability. An additional source does not imply a false claim."
            ),
            "private_evidence_map": "source_id -> URL and per-profile uses in private source map",
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--safe-out", type=Path, required=True)
    args = parser.parse_args()
    private_root(args.private_out.parent)
    private, safe = source_metrics(args.root, args.version, args.run_id)
    immutable_json(args.private_out, private)
    immutable_json(args.safe_out, safe)
    print(f"Sources: {len(safe['sources'])}; contacts/URLs stay outside git")


if __name__ == "__main__":
    main()
