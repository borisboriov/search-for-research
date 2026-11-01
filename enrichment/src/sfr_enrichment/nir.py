"""Offline frozen B/C preparation and paired analysis; no acquisition or model transport."""

import argparse
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sfr_enrichment.batch import encoded
from sfr_enrichment.common import now, private_root, read, sha, write_new
from sfr_enrichment.evidence import identifier, immutable_bytes
from sfr_enrichment.native_claude import EFFORTS as CLAUDE_EFFORTS
from sfr_enrichment.native_claude import verify_isolation_proof
from sfr_enrichment.nir_inventory import (
    candidate_identity_keys,
    canonical_document_url,
    canonical_email,
    overlap_reasons,
    validate_inventory,
)

LABELS = ("supported", "refuted", "insufficient")
ANNOTATORS = ("adelina", "sasha")
PROFILE_KEYS = {
    "name",
    "aliases",
    "identifiers",
    "affiliations",
    "topics",
    "id",
    "author_id",
    "openalex_id",
    "orcid",
}
CASE_KEYS = {"case_id", "group_id", "pair_id", "example_ids", "profile", "email", "evidence"}
SOURCE_KEYS = {"source_id", "url", "captured_at", "content_date", "source_path", "excerpt"}
DIAGNOSTIC_STATUS = "diagnostic_known_capture_gaps_not_holdout"
# Absent field means the original codex transport; v1 protocols stay byte-identical.
TRANSPORTS = ("codex_cli", "claude_cli")
DIAGNOSTIC_LIMITATION = (
    "Diagnostic pilot only: two historical email/document details remain unknown; "
    "known people and all recorded evidence remain excluded. Not an independent holdout "
    "or confirmation of the hypothesis."
)


def protocol_transport(protocol: dict[str, Any]) -> str:
    transport = protocol.get("transport", "codex_cli")
    if transport not in TRANSPORTS:
        raise ValueError("Неизвестный транспорт протокола")
    if transport == "claude_cli" and protocol.get("effort") not in CLAUDE_EFFORTS:
        raise ValueError("Неподдерживаемый effort для claude_cli")
    return str(transport)


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Нужно непустое поле {field}")
    return value


def timestamp(value: Any) -> None:
    parsed = datetime.fromisoformat(nonempty(value, "timestamp").replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Нужен часовой пояс")


def number(value: Any, field: str, *, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError(f"Нужно конечное неотрицательное {field}")


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def private_output(path: Path) -> Path:
    """Keep output outside Git without changing permissions of existing shared parents."""
    target = path.resolve()
    if any((parent / ".git").exists() for parent in target.parents):
        raise ValueError("Исходные материалы и контакты должны находиться вне git")
    missing = []
    parent = target.parent
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o700, exist_ok=True)
    return target


def compose(identity: str, relation: str) -> str:
    if identity not in LABELS or relation not in LABELS:
        raise ValueError("Неизвестный класс")
    if identity == relation == "supported":
        return "supported"
    if "refuted" in (identity, relation):
        return "refuted"
    return "insufficient"


def validate_diagnostic_decision(
    decision: dict[str, Any],
    inventory: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    inventory_sha256: str,
    selection_sha256: str,
    protocol_sha256: str,
) -> None:
    """Admit only the documented two capture gaps, never arbitrary incomplete history."""
    required = {
        "schema",
        "purpose",
        "planned_n",
        "maximum_n",
        "one_pair_per_person",
        "advisor_agreement",
        "authorization",
        "inventory_sha256",
        "selection_sha256",
        "protocol_sha256",
        "accepted_blocking_gaps",
        "accepted_capture_limits",
        "limitation_acknowledged",
    }
    if not isinstance(decision, dict) or set(decision) != required:
        raise ValueError("Нужна точная diagnostic decision schema")
    if (
        decision["schema"] != "nir_diagnostic_decision_v1"
        or decision["purpose"] != "diagnostic_pilot_not_holdout"
        or type(decision["planned_n"]) is not int
        or decision["planned_n"] != 30
        or type(decision["maximum_n"]) is not int
        or decision["maximum_n"] != 30
        or decision["one_pair_per_person"] is not True
        or decision["advisor_agreement"] != "preliminary"
        or decision["limitation_acknowledged"] is not True
    ):
        raise ValueError("Diagnostic decision допускает только согласованный ограниченный пилот")
    authorization = decision["authorization"]
    if not isinstance(authorization, dict) or set(authorization) != {
        "authorized_by",
        "authorized_at",
        "reference",
        "scope",
    }:
        raise ValueError("Нужна provenance разрешения диагностической процедуры")
    for key in ("authorized_by", "reference"):
        nonempty(authorization[key], key)
    timestamp(authorization["authorized_at"])
    if authorization["scope"] != "diagnostic_30_pairs":
        raise ValueError("Неверный scope разрешения диагностической процедуры")
    for field, expected in (
        ("inventory_sha256", inventory_sha256),
        ("selection_sha256", selection_sha256),
        ("protocol_sha256", protocol_sha256),
    ):
        if decision[field] != expected:
            raise ValueError("Diagnostic decision не соответствует замороженным входам: " + field)
    if not 1 <= len(rows) <= 30 or len({row["group_id"] for row in rows}) != len(rows):
        raise ValueError("Диагностический пилот: максимум 30 пар, одна пара на человека")
    completeness, coverage = inventory["completeness"], inventory["coverage"]
    if (
        completeness.get("complete") is not False
        or completeness.get("prior_details_complete") is not False
        or coverage.get("metadata_scope_complete") is not True
    ):
        raise ValueError("Diagnostic decision не отменяет полноту metadata scope")
    gaps = [gap for gap in completeness["gaps"] if gap["blocking"]]
    limits = coverage.get("historical_capture_limits", [])
    if (
        len(gaps) != 2
        or len(limits) != 2
        or not isinstance(decision["accepted_blocking_gaps"], list)
        or not isinstance(decision["accepted_capture_limits"], list)
        or sorted(map(digest, gaps)) != sorted(map(digest, decision["accepted_blocking_gaps"]))
        or sorted(map(digest, limits)) != sorted(map(digest, decision["accepted_capture_limits"]))
    ):
        raise ValueError("Разрешены только два точных исторических capture gaps")
    if {gap["selector"] for gap in gaps} != {"$.rows[6]", "$.rows[9]"} or len(
        {(gap["source_id"], gap["path"]) for gap in gaps}
    ) != 1:
        raise ValueError("Diagnostic decision относится только к двум исходным строкам")
    for gap in gaps:
        if (
            gap["kind"] != "historical_capture_detail_missing"
            or Path(gap["path"]).name != "contacts_manual_sfr5.json"
            or gap["missing_fields"] != ["email_literal", "document_locator"]
        ):
            raise ValueError("Неподдерживаемое историческое ограничение")
        matching = [
            limit
            for limit in limits
            if all(limit[key] == gap[key] for key in ("source_id", "path", "selector"))
        ]
        if (
            len(matching) != 1
            or matching[0].get("kind") != "publication_flag_without_recorded_address"
            or matching[0].get("document_locator_recorded") is not False
            or matching[0].get("person_key") not in inventory["lookup"]["identity_keys"]
        ):
            raise ValueError("Известный человек из capture gap должен остаться исключённым")


def diagnostic_scope(manifest: dict[str, Any]) -> dict[str, Any]:
    """Neutral, non-personal scope safe for both annotators and downstream artifacts."""
    if manifest.get("holdout_status") != DIAGNOSTIC_STATUS:
        return {}
    return {
        "diagnostic_scope": {
            "purpose": "diagnostic_pilot_not_holdout",
            "planned_n": 30,
            "actual_n": manifest["cases"],
            "sample_status": "complete_planned_count" if manifest["cases"] == 30 else "shortfall",
            "limitation": DIAGNOSTIC_LIMITATION,
        }
    }


def freeze(
    root: Path,
    selection: Path,
    exclusions: Path,
    protocol_path: Path,
    *,
    development_only: bool = False,
    diagnostic_decision: Path | None = None,
) -> Path:
    """Copy allowlisted inputs and source bodies, excluding every declared previous use."""
    root = private_root(root)
    if (root / "manifest.json").exists():
        raise FileExistsError(root / "manifest.json")
    rows, old, protocol = read(selection), read(exclusions), read(protocol_path)
    if not isinstance(rows, list) or not rows:
        raise ValueError("Нужна непустая выборка")
    if development_only and diagnostic_decision is not None:
        raise ValueError("Diagnostic decision несовместима с development-only")
    decision = read(diagnostic_decision) if diagnostic_decision is not None else None
    if development_only:
        if old.get("complete_prior_use_inventory") is not True or not old.get("inventory_sources"):
            raise ValueError("Нужны источники даже для разработочного реестра")
        for source in old["inventory_sources"]:
            if sha(exclusions.parent / source["path"]) != source["sha256"]:
                raise ValueError("Изменён источник реестра исключений")
        for key in ("group_ids", "pair_ids", "example_ids"):
            if not isinstance(old.get(key), list) or any(not isinstance(x, str) for x in old[key]):
                raise ValueError("Нужны списки прежних людей, пар и примеров разработки")
    elif old.get("schema") != "nir_prior_inventory_v1":
        raise ValueError(
            "Для нового отбора нужен producer registry; legacy только --development-only"
        )
    else:
        validate_inventory(old, exclusions.parent)
        if decision is not None:
            validate_diagnostic_decision(
                decision,
                old,
                rows,
                inventory_sha256=sha(exclusions),
                selection_sha256=sha(selection),
                protocol_sha256=sha(protocol_path),
            )
        elif old.get("completeness", {}).get("complete") is not True:
            raise ValueError("Неполный реестр: новый независимый отбор заблокирован")
    for key in (
        "rubric",
        "common_examples",
        "instructions_B",
        "instructions_C",
        "model",
        "effort",
        "code_revision",
        "runtime_version",
    ):
        nonempty(protocol.get(key), key)
    if any(protocol[key].startswith("TEMPLATE") for key in ("code_revision", "runtime_version")):
        raise ValueError("Заполните фактические версии вместо TEMPLATE перед freeze")
    protocol_transport(protocol)
    if not isinstance(protocol.get("generation"), dict):
        raise ValueError("Нужно зафиксировать параметры generation (пустой объект допустим)")
    if not isinstance(protocol.get("limits"), dict) or not protocol["limits"]:
        raise ValueError("Нужны заранее заданные лимиты; freeze ничего не запускает")
    cases = []
    case_ids: set[str] = set()
    pair_ids: set[str] = set()
    exact_pairs: set[tuple[str, str]] = set()
    identity_groups: dict[str, str] = {}
    for row in rows:
        if set(row) != CASE_KEYS or set(row["profile"]) - PROFILE_KEYS:
            raise ValueError("Посторонние поля могут раскрыть ответы; используйте чистый input")
        for key in ("case_id", "group_id", "pair_id"):
            identifier(row[key])
        if row["case_id"] in case_ids or row["pair_id"] in pair_ids:
            raise ValueError("Повтор case_id/pair_id")
        if not isinstance(row["example_ids"], list) or any(
            not isinstance(x, str) for x in row["example_ids"]
        ):
            raise ValueError("Нужен список идентификаторов доказательных примеров")
        if development_only and (
            row["group_id"] in old["group_ids"]
            or row["pair_id"] in old["pair_ids"]
            or any(x in old["example_ids"] for x in row["example_ids"])
        ):
            raise ValueError("Прежний человек, пара или доказательный пример запрещены")
        case_ids.add(row["case_id"])
        pair_ids.add(row["pair_id"])
        nonempty(row["email"], "email")
        exact_pair = (
            row["group_id"],
            row["email"].strip() if development_only else canonical_email(row["email"]),
        )
        if exact_pair in exact_pairs:
            raise ValueError("Повтор пары group_id/email под другим идентификатором")
        exact_pairs.add(exact_pair)
        nonempty(row["profile"].get("name"), "profile.name")
        if not isinstance(row["evidence"], list) or not row["evidence"]:
            raise ValueError("Нужны сохранённые доказательства")
        sources = []
        seen_sources = set()
        for item in row["evidence"]:
            if set(item) != SOURCE_KEYS or item["source_id"] in seen_sources:
                raise ValueError("Некорректный или повторный источник")
            identifier(item["source_id"])
            seen_sources.add(item["source_id"])
            timestamp(item["captured_at"])
            if urlparse(item["url"]).scheme not in ("https", "http") or (
                not development_only and canonical_document_url(item["url"]) is None
            ):
                raise ValueError("Нужен публичный URL источника")
            if item["content_date"] is not None:
                nonempty(item["content_date"], "content_date")
            body = (selection.parent / item["source_path"]).read_bytes()
            if nonempty(item["excerpt"], "excerpt") not in body.decode("utf-8"):
                raise ValueError("Цитата должна буквально входить в сохранённый текст")
            body_hash = hashlib.sha256(body).hexdigest()
            target = root / "sources" / f"{body_hash}.txt"
            if not target.exists():
                immutable_bytes(target, body)
            sources.append(
                {k: v for k, v in item.items() if k != "source_path"}
                | {"body_sha256": body_hash, "snapshot": f"sources/{body_hash}.txt"}
            )
        if not development_only:
            identity_keys = candidate_identity_keys(row["profile"], row["group_id"])
            if not identity_keys:
                raise ValueError("Для нового отбора нужен сильный идентификатор исследователя")
            if any(
                key in identity_groups and identity_groups[key] != row["group_id"]
                for key in identity_keys
            ):
                raise ValueError("Один исследователь не может иметь разные group_id в выборке")
            for key in identity_keys:
                identity_groups[key] = row["group_id"]
            reasons = overlap_reasons(
                old,
                {
                    "identity_keys": identity_keys,
                    "email": row["email"],
                    "snapshot_sha256": [s["body_sha256"] for s in sources],
                    "excerpt_sha256": [
                        hashlib.sha256(s["excerpt"].encode("utf-8")).hexdigest() for s in sources
                    ],
                    "source_urls": [s["url"] for s in sources],
                    "example_keys": row["example_ids"],
                },
            )
            if reasons:
                raise ValueError("Пересечение с прежним использованием: " + ", ".join(reasons))
        cases.append({**row, "evidence": sources})
    # Both arms receive precisely the same JSON; only the required output structure differs.
    write_new(root / "cases.json", cases)
    if diagnostic_decision is not None:
        # Preserve exact approved bytes; input hashes are checked again after freeze.
        for source, filename in (
            (exclusions, "exclusions.json"),
            (protocol_path, "protocol.json"),
            (selection, "selection.json"),
            (diagnostic_decision, "diagnostic-decision.json"),
        ):
            immutable_bytes(root / filename, source.read_bytes())
    else:
        write_new(root / "exclusions.json", old)
        write_new(root / "protocol.json", protocol)
    input_hashes = {}
    for case in cases:
        path = root / "model-inputs" / f"{case['case_id']}.json"
        write_new(
            path,
            {
                "case": case,
                "source_bodies": {
                    source["source_id"]: (root / source["snapshot"]).read_bytes().decode("utf-8")
                    for source in case["evidence"]
                },
            },
        )
        input_hashes[case["case_id"]] = sha(path)
    common = {
        "rubric": protocol["rubric"],
        "common_examples": protocol["common_examples"],
        "cases_sha256": sha(root / "cases.json"),
    }
    for arm in ("B", "C"):
        write_new(
            root / f"prompt-{arm}.json", common | {"instructions": protocol[f"instructions_{arm}"]}
        )
    manifest = {
        "schema": "nir_email_bc_v1",
        "created_at": now(),
        "selection_sha256": sha(selection),
        "exclusion_input_sha256": sha(exclusions),
        "cases_sha256": sha(root / "cases.json"),
        "protocol_sha256": sha(root / "protocol.json"),
        "exclusions_sha256": sha(root / "exclusions.json"),
        "prompt_sha256": {arm: sha(root / f"prompt-{arm}.json") for arm in ("B", "C")},
        "case_input_sha256": input_hashes,
        "cases": len(cases),
        "groups": len({r["group_id"] for r in cases}),
        "holdout_status": "development_only_not_holdout"
        if development_only
        else DIAGNOSTIC_STATUS
        if decision is not None
        else "recorded_prior_overlap_checked",
        "launch_authorized": False,
        "warning": (
            "Development data only; no new-holdout claim"
            if development_only
            else (
                "Recorded prior-overlap check only; "
                "new-frame identity/coherence requires verification"
            )
        ),
    }
    if decision is not None:
        manifest.update(
            diagnostic_decision_sha256=sha(root / "diagnostic-decision.json"),
            warning=DIAGNOSTIC_LIMITATION,
        )
        manifest.update(diagnostic_scope(manifest))
    write_new(root / "manifest.json", manifest)
    return root / "manifest.json"


def checked(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    root = private_root(root)
    manifest = read(root / "manifest.json")
    if manifest.get("schema") != "nir_email_bc_v1":
        raise ValueError("Неизвестная схема")
    for filename, field in (
        ("cases.json", "cases_sha256"),
        ("protocol.json", "protocol_sha256"),
        ("exclusions.json", "exclusions_sha256"),
    ):
        if sha(root / filename) != manifest[field]:
            raise ValueError("Замороженный вход изменён")
    for arm in ("B", "C"):
        if sha(root / f"prompt-{arm}.json") != manifest["prompt_sha256"][arm]:
            raise ValueError("Замороженная инструкция изменена")
    cases = read(root / "cases.json")
    inventory = read(root / "exclusions.json")
    protocol_transport(read(root / "protocol.json"))
    if (
        manifest.get("holdout_status") == DIAGNOSTIC_STATUS
        or "diagnostic_decision_sha256" in manifest
        or (root / "diagnostic-decision.json").exists()
        or (
            inventory.get("schema") == "nir_prior_inventory_v1"
            and inventory.get("completeness", {}).get("complete") is not True
        )
    ):
        if (
            manifest.get("holdout_status") != DIAGNOSTIC_STATUS
            or sha(root / "diagnostic-decision.json") != manifest.get("diagnostic_decision_sha256")
            or sha(root / "selection.json") != manifest["selection_sha256"]
            or manifest["exclusion_input_sha256"] != manifest["exclusions_sha256"]
            or manifest["cases"] != len(cases)
            or manifest["cases"] != len(read(root / "selection.json"))
            or manifest["groups"] != len({case["group_id"] for case in cases})
            or manifest.get("diagnostic_scope") != diagnostic_scope(manifest)["diagnostic_scope"]
            or manifest.get("launch_authorized") is not False
        ):
            raise ValueError("Диагностический статус или decision изменены")
        validate_diagnostic_decision(
            read(root / "diagnostic-decision.json"),
            inventory,
            read(root / "selection.json"),
            inventory_sha256=manifest["exclusions_sha256"],
            selection_sha256=manifest["selection_sha256"],
            protocol_sha256=manifest["protocol_sha256"],
        )
    for case in cases:
        if (
            sha(root / "model-inputs" / f"{case['case_id']}.json")
            != manifest["case_input_sha256"][case["case_id"]]
        ):
            raise ValueError("Общий модельный вход изменён")
        for source in case["evidence"]:
            if sha(root / source["snapshot"]) != source["body_sha256"]:
                raise ValueError("Снимок источника изменён")
    return manifest, cases, read(root / "protocol.json")


def export(root: Path, annotator: str) -> Path:
    """Separate neutral forms; no model outputs, assignments, or peer answers are copied."""
    if annotator not in ANNOTATORS:
        raise ValueError("Неизвестный разметчик")
    manifest, cases, protocol = checked(root)
    directory = root / "human-packets" / annotator
    clean_cases = []
    for case in cases:
        sources = []
        for source in case["evidence"]:
            body_path = Path(source["snapshot"])
            target = directory / body_path
            if not target.exists():
                immutable_bytes(target, (root / body_path).read_bytes())
            sources.append(dict(source))
        clean_cases.append({**case, "evidence": sources})
    package = {
        "schema": "nir_human_packet_v1",
        "annotator": annotator,
        "rubric": protocol["rubric"],
        "common_examples": protocol["common_examples"],
        "cases": clean_cases,
        "warning": "Только сохранённые источники. Не искать новые; не обсуждать до сдачи ответов.",
        **diagnostic_scope(manifest),
    }
    if manifest.get("holdout_status") == DIAGNOSTIC_STATUS:
        package["holdout_status"] = DIAGNOSTIC_STATUS
    write_new(directory / "packet.json", package)
    template = {
        "schema": "nir_human_answers_v1",
        "annotator": annotator,
        "packet_sha256": sha(directory / "packet.json"),
        "reviewed_at": None,
        "minutes": None,
        "actual_human_attestation": False,
        "answers": [
            {
                "case_id": c["case_id"],
                "status": "not_reviewed",
                "label": None,
                "reason": "",
                "source_ids": [],
            }
            for c in cases
        ],
    }
    write_new(directory / "answers-template.json", template)
    return directory / "packet.json"


def validate_answer(answer: dict[str, Any], case: dict[str, Any]) -> None:
    status = answer.get("status")
    if status not in ("ok", "technical_skip"):
        raise ValueError("Нужен status ok или technical_skip; not_reviewed не является ответом")
    nonempty(answer.get("reason"), "reason")
    refs = answer.get("source_ids")
    if (
        not isinstance(refs, list)
        or len(refs) != len(set(refs))
        or set(refs) - {s["source_id"] for s in case["evidence"]}
    ):
        raise ValueError("Неизвестные доказательства")
    if status == "technical_skip":
        if answer.get("label") is not None:
            raise ValueError("Техпропуск не является содержательным классом")
    elif answer.get("label") not in LABELS or (
        answer["label"] in ("supported", "refuted") and not refs
    ):
        raise ValueError("Нужен класс и ссылки для подтверждения/опровержения")


def import_human(root: Path, answers_path: Path, record_id: str) -> Path:
    manifest, cases, protocol = checked(root)
    identifier(record_id)
    answers = read(answers_path)
    annotator = nonempty(answers.get("annotator"), "annotator")
    if answers.get("schema") != "nir_human_answers_v1" or annotator not in ANNOTATORS:
        raise ValueError("Неизвестный формат/разметчик")
    packet = root / "human-packets" / annotator / "packet.json"
    if answers.get("packet_sha256") != sha(packet):
        raise ValueError("Ответы от другого пакета")
    frozen_packet = read(packet)
    expected = {
        "schema": "nir_human_packet_v1",
        "annotator": annotator,
        "rubric": protocol["rubric"],
        "common_examples": protocol["common_examples"],
        "cases": cases,
        "warning": "Только сохранённые источники. Не искать новые; не обсуждать до сдачи ответов.",
        **diagnostic_scope(manifest),
    }
    if manifest.get("holdout_status") == DIAGNOSTIC_STATUS:
        expected["holdout_status"] = DIAGNOSTIC_STATUS
    if frozen_packet != expected:
        raise ValueError("Нейтральный пакет изменён")
    for case in cases:
        for source in case["evidence"]:
            if sha(packet.parent / source["snapshot"]) != source["body_sha256"]:
                raise ValueError("Снимок в пакете разметчика изменён")
    if answers.get("actual_human_attestation") is not True:
        raise ValueError("Нужно подтверждение реальной человеческой разметки")
    timestamp(answers.get("reviewed_at"))
    number(answers.get("minutes"), "minutes")
    if answers["minutes"] <= 0:
        raise ValueError("Нужно фактическое положительное время")
    index = {c["case_id"]: c for c in cases}
    seen = set()
    for answer in answers.get("answers", []):
        case_id = answer.get("case_id")
        if case_id not in index or case_id in seen:
            raise ValueError("Неизвестный или повторный случай")
        seen.add(case_id)
        validate_answer(answer, index[case_id])
    if not seen:
        raise ValueError("Нет ответов")
    previous = {
        row["case_id"]
        for path in (root / "human-records" / annotator).glob("*.json")
        for row in read(path)["answers"]["answers"]
    }
    if previous & seen:
        raise ValueError("Повторный ответ разметчика; сохранённые ответы не заменяются")
    target = root / "human-records" / annotator / f"{record_id}.json"
    write_new(
        target,
        {
            "answers_sha256": sha(answers_path),
            "manifest_sha256": sha(root / "manifest.json"),
            "recorded_at": now(),
            "answers": answers,
        },
    )
    return target


def import_model(root: Path, answers_path: Path, record_id: str) -> Path:
    manifest, cases, protocol = checked(root)
    identifier(record_id)
    value = read(answers_path)
    arm = nonempty(value.get("arm"), "arm")
    if value.get("schema") != "nir_model_answers_v1" or arm not in ("B", "C"):
        raise ValueError("Неизвестный формат/вариант")
    expected = {
        "manifest_sha256": sha(root / "manifest.json"),
        "cases_sha256": manifest["cases_sha256"],
        "protocol_sha256": manifest["protocol_sha256"],
        "prompt_sha256": manifest["prompt_sha256"][arm],
        "model": protocol["model"],
        "effort": protocol["effort"],
        "generation": protocol["generation"],
        "code_revision": protocol["code_revision"],
        "runtime_version": protocol["runtime_version"],
    }
    if any(value.get(k) != v for k, v in expected.items()):
        raise ValueError("Модель/инструкции/входы отличаются от фиксированного протокола")
    index = {c["case_id"]: c for c in cases}
    seen = set()
    normalized = []
    for result in value.get("results", []):
        if not {
            "case_id",
            "status",
            "raw_response",
            "started_at",
            "latency_seconds",
            "cost_usd",
            "input_tokens",
            "output_tokens",
            "observed_model",
            "observed_effort",
            "receipt",
        } <= set(result):
            raise ValueError("Нужны все поля ответа и расходов; неизвестное обозначается null")
        case_id = result.get("case_id")
        if case_id not in index or case_id in seen:
            raise ValueError("Неизвестный/повторный случай")
        if result.get("case_input_sha256") != manifest["case_input_sha256"][case_id]:
            raise ValueError("Ответ модели относится к другому общему входу пары")
        seen.add(case_id)
        nonempty(result.get("raw_response"), "raw_response")
        timestamp(result.get("started_at"))
        number(result.get("latency_seconds"), "latency_seconds")
        number(result.get("cost_usd"), "cost_usd", nullable=True)
        for field in ("input_tokens", "output_tokens"):
            count = result.get(field)
            if count is not None and (type(count) is not int or count < 0):
                raise ValueError("Токены — неотрицательные целые либо null")
        for field in ("model", "effort"):
            observed = result[f"observed_{field}"]
            if observed is not None:
                nonempty(observed, f"observed_{field}")
        if result["receipt"] is not None and not isinstance(result["receipt"], dict):
            raise ValueError("receipt должен быть объектом метаданных либо null")
        label = None
        if result.get("status") == "ok":
            response = json.loads(result["raw_response"])
            nonempty(response.get("reason"), "reason")
            if arm == "B":
                label = response.get("label")
                if label not in LABELS:
                    raise ValueError("Нет общего суждения B")
            else:
                label = compose(response.get("identity"), response.get("object_relation"))
            validate_answer({**response, "status": "ok", "label": label}, index[case_id])
        elif result.get("status") != "technical_skip":
            raise ValueError("Статус модели должен отличать технический пропуск")
        if result["status"] == "technical_skip":
            nonempty(result.get("error"), "error")
        normalized.append(
            {
                **result,
                "label": label,
                "raw_response_sha256": hashlib.sha256(result["raw_response"].encode()).hexdigest(),
                "receipt_sha256": digest(result["receipt"])
                if result["receipt"] is not None
                else None,
                "provenance": "caller-supplied metadata; identity not independently verified",
                "configuration_mismatch": any(
                    result[f"observed_{field}"] is not None
                    and result[f"observed_{field}"] != protocol[field]
                    for field in ("model", "effort")
                ),
            }
        )
    if not seen:
        raise ValueError("Нет ответов")
    previous = {row["case_id"] for row in records(root, f"model-records/{arm}", "results")}
    if previous & seen:
        raise ValueError("Повторный модельный результат; зафиксируйте новый эксперимент отдельно")
    target = root / "model-records" / arm / f"{record_id}.json"
    write_new(target, {"answers_sha256": sha(answers_path), **value, "results": normalized})
    return target


def output_schema(arm: str, source_ids: list[str]) -> dict[str, Any]:
    verdict = {"type": "string", "enum": list(LABELS)}
    properties = (
        {"label": verdict} if arm == "B" else {"identity": verdict, "object_relation": verdict}
    ) | {
        "reason": {"type": "string"},
        "source_ids": {"type": "array", "items": {"type": "string", "enum": source_ids}},
    }
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def claude_request(request: dict[str, Any]) -> dict[str, Any]:
    """Same frozen request with the claude_cli transport arguments instead of codex ones."""
    codex = request["native_kwargs"]
    converted: dict[str, Any] = {}
    for key, value in request.items():
        if key == "schema":
            converted.update(schema="nir_native_request_v2", transport="claude_cli")
        elif key == "native_kwargs":
            converted["claude_kwargs"] = {
                name: codex[name]
                for name in ("model", "effort", "timeout_seconds", "max_output_file_bytes")
            }
        elif key == "native_configuration_supported":
            converted["claude_configuration_supported"] = codex["effort"] in CLAUDE_EFFORTS
        elif key == "generation_proposal_not_enforced_by_native":
            converted["generation_proposal_not_enforced_by_claude_cli"] = value
        elif key == "output_byte_cap_scope":
            converted[key] = "claude stdout/stderr during execution; raw-result derived from stdout"
        else:
            converted[key] = value
    return converted


def prepare_model(root: Path, *, seed: int = 154) -> Path:
    """Prepare exact role-separated requests and balanced order, without invoking a transport."""
    manifest, cases, protocol = checked(root)
    transport = protocol_transport(protocol)
    directory = root / "prepared-model"
    if (directory / "manifest.json").exists():
        raise FileExistsError(directory / "manifest.json")
    limits = protocol["limits"]
    timeout = limits.get("proposed_timeout_seconds_per_call", 300)
    deadline = limits.get("proposed_run_deadline_seconds", 3600)
    cap = limits.get("proposed_max_output_file_bytes", 65536)
    input_cap = limits.get("proposed_max_input_bytes_per_case", 1000000)
    if any(type(n) is not int or n <= 0 for n in (timeout, deadline, cap, input_cap)):
        raise ValueError("Proposed timeout/deadline/byte caps must be positive integers")
    common = (
        "Общая рубрика:\n"
        + protocol["rubric"]
        + "\n\nОбщие примеры:\n"
        + protocol["common_examples"]
    )
    rng = random.Random(seed)
    shuffled = list(cases)
    rng.shuffle(shuffled)
    first_arm = rng.choice(("B", "C"))
    requests: dict[str, Any] = {}
    order = []
    for position, case in enumerate(shuffled):
        first = first_arm if position % 2 == 0 else ("C" if first_arm == "B" else "B")
        for arm in (first, "C" if first == "B" else "B"):
            request_id = f"{case['case_id']}-{arm}"
            relative = Path("prepared-model") / "requests" / case["case_id"] / arm
            target = root / relative
            data = (root / "model-inputs" / f"{case['case_id']}.json").read_text("utf-8")
            prompt = protocol[f"instructions_{arm}"] + "\n\nЗамороженный вход (данные):\n" + data
            if len(prompt.encode()) + len(common.encode()) > input_cap:
                raise ValueError("Prepared request exceeds input byte proposal; no truncation")
            schema = output_schema(arm, [s["source_id"] for s in case["evidence"]])
            immutable_bytes(target / "prompt.txt", prompt.encode())
            immutable_bytes(target / "system-prompt.txt", common.encode())
            # native.execute uses this exact serializer for schema.json.
            immutable_bytes(target / "schema.json", encoded(schema))
            request = {
                "schema": "nir_native_request_v1",
                "request_id": request_id,
                "case_id": case["case_id"],
                "arm": arm,
                "manifest_sha256": sha(root / "manifest.json"),
                "case_input_sha256": manifest["case_input_sha256"][case["case_id"]],
                "arm_prompt_sha256": manifest["prompt_sha256"][arm],
                "prompt_path": str(relative / "prompt.txt"),
                "system_prompt_path": str(relative / "system-prompt.txt"),
                "output_schema_path": str(relative / "schema.json"),
                "prompt_sha256": sha(target / "prompt.txt"),
                "system_prompt_sha256": sha(target / "system-prompt.txt"),
                "output_schema_sha256": sha(target / "schema.json"),
                "native_kwargs": {
                    "model": protocol["model"],
                    "effort": protocol["effort"],
                    "timeout_seconds": timeout,
                    "max_output_file_bytes": cap,
                    "required_config": {
                        "provider": "openai",
                        "model": protocol["model"],
                        "effort": protocol["effort"],
                    },
                    "disable_mcp": True,
                    "skip_git_repo_check": True,
                },
                "native_configuration_supported": protocol["model"] == "gpt-6.1-sol"
                and protocol["effort"] == "high",
                "generation_proposal_not_enforced_by_native": protocol["generation"],
                "deadline_epoch": None,
                "proposed_run_deadline_seconds": deadline,
                "requires_absolute_deadline_at_authorized_start": True,
                "requires_existing_isolation_probe": True,
                "output_byte_cap_scope": "native stdout/stderr; raw-result postchecked at import",
                "launch_authorized": False,
                "holdout_status": manifest.get("holdout_status", "legacy_unclassified_not_holdout"),
                **diagnostic_scope(manifest),
            }
            if transport == "claude_cli":
                request = claude_request(request)
            write_new(target / "request.json", request)
            requests[request_id] = {
                "path": str(relative / "request.json"),
                "sha256": sha(target / "request.json"),
            }
            order.append(request_id)
    write_new(
        directory / "manifest.json",
        {
            "schema": "nir_prepared_native_v1",
            "manifest_sha256": sha(root / "manifest.json"),
            "seed": seed,
            "order": order,
            "requests": requests,
            "order_rule": "shuffle cases; alternate first arm, balanced B/C-first within one case",
            **({"transport": transport} if transport != "codex_cli" else {}),
            "launch_authorized": False,
            "holdout_status": manifest.get("holdout_status", "legacy_unclassified_not_holdout"),
            **diagnostic_scope(manifest),
        },
    )
    return directory / "manifest.json"


def prepared_request(root: Path, request_id: str) -> dict[str, Any]:
    manifest, _, protocol = checked(root)
    transport = protocol_transport(protocol)
    identifier(request_id)
    prepared = read(root / "prepared-model" / "manifest.json")
    if prepared.get("manifest_sha256") != sha(root / "manifest.json"):
        raise ValueError("Prepared request относится к другому набору")
    entry = prepared["requests"].get(request_id)
    if entry is None or sha(root / entry["path"]) != entry["sha256"]:
        raise ValueError("Prepared request отсутствует или изменён")
    request: dict[str, Any] = read(root / entry["path"])
    if manifest.get("holdout_status") == DIAGNOSTIC_STATUS and any(
        item.get("holdout_status") != DIAGNOSTIC_STATUS
        or item.get("diagnostic_scope") != manifest["diagnostic_scope"]
        or item.get("launch_authorized") is not False
        for item in (prepared, request)
    ):
        raise ValueError("Prepared request потерял диагностическое ограничение")
    if (
        request["request_id"] != request_id
        or request["manifest_sha256"] != prepared["manifest_sha256"]
    ):
        raise ValueError("Неверная привязка request/case")
    arguments = "claude_kwargs" if transport == "claude_cli" else "native_kwargs"
    other = "native_kwargs" if transport == "claude_cli" else "claude_kwargs"
    if (
        prepared.get("transport", "codex_cli") != transport
        or request.get("transport", "codex_cli") != transport
        or not isinstance(request.get(arguments), dict)
        or other in request
    ):
        raise ValueError("Транспорт prepared request не совпадает с протоколом")
    for key, field in (
        ("prompt_path", "prompt_sha256"),
        ("system_prompt_path", "system_prompt_sha256"),
        ("output_schema_path", "output_schema_sha256"),
    ):
        if sha(root / request[key]) != request[field]:
            raise ValueError("Prepared prompt/schema изменены")
    return request


def import_native(root: Path, request_id: str, native_dir: Path, record_id: str) -> Path:
    """Normalize existing native.execute artifacts; never execute or recover a model job."""
    manifest, _, protocol = checked(root)
    request = prepared_request(root, request_id)
    identifier(record_id)
    if request.get("transport") == "claude_cli":
        return import_claude_native(root, request, native_dir, record_id)
    receipt, started, finished = (
        read(native_dir / name) for name in ("receipt.json", "started.json", "finished.json")
    )
    for name, field in (
        ("prompt.txt", "prompt_sha256"),
        ("schema.json", "output_schema_sha256"),
        ("instructions.txt", "system_prompt_sha256"),
    ):
        if sha(native_dir / name) != request[field]:
            raise ValueError("Native prompt/schema не соответствуют данному case/arm")
    raw_path = native_dir / "raw-result.json"
    if sha(raw_path) != receipt.get("raw_result_sha256"):
        raise ValueError("Native raw hash не совпадает")
    if raw_path.stat().st_size > request["native_kwargs"]["max_output_file_bytes"]:
        raise ValueError("Native raw-result превышает postcheck byte cap")
    if (
        receipt.get("prompt_sha256") != request["prompt_sha256"]
        or started.get("prompt_sha256") != request["prompt_sha256"]
    ):
        raise ValueError("Native receipt/started относятся к другому prompt")
    required = request["native_kwargs"]["required_config"]
    if started.get("requested_config") != required or any(
        receipt.get(f"requested_{field}") != required[field] for field in ("model", "effort")
    ):
        raise ValueError("Native requested configuration отличается от протокола")
    if finished.get("exit_code") != 0 or receipt.get("tool_calls") != 0:
        raise ValueError("Нет успешного cache-only native результата; используйте technical_skip")
    execution_provenance = receipt.get("execution_provenance")
    if execution_provenance is not None and (
        started.get("execution_provenance") != execution_provenance
        or any(
            sha(native_dir / filename) != execution_provenance.get(key)
            for filename, key in (
                ("execution-amendment.json", "execution_amendment_sha256"),
                ("isolated-model-catalog.json", "isolated_catalog_sha256"),
                ("effective-features.txt", "effective_features_sha256"),
            )
        )
    ):
        raise ValueError("Native execution amendment provenance mismatch")
    if sha(native_dir / "events.jsonl") != receipt.get("events_sha256"):
        raise ValueError("Native events hash не совпадает")
    events = [
        json.loads(line)
        for line in (native_dir / "events.jsonl").read_text().splitlines()
        if line.strip()
    ]
    turn_start = next((i for i, e in enumerate(events) if e.get("type") == "turn.started"), 0)
    if any(
        "item" in event
        and event["item"].get("type") not in ("agent_message", "reasoning")
        and not (
            i < turn_start
            and event in receipt.get("client_diagnostics", [])
            and event["item"].get("type") == "error"
        )
        for i, event in enumerate(events)
    ):
        raise ValueError("Native events содержат tool execution")
    usage = next(
        (e.get("usage") for e in reversed(events) if e.get("type") == "turn.completed"), None
    )
    if (
        not any(e.get("type") == "thread.started" for e in events)
        or not isinstance(usage, dict)
        or usage != receipt.get("tokens")
    ):
        raise ValueError("Нет согласованного completed/usage в native events")
    proof = read(native_dir / "isolation-probe.json")
    if (
        proof.get("instruction_delivery") != "rendered_instruction_and_exact_final_user"
        or proof.get("instruction_sha256") != request["system_prompt_sha256"]
        or proof.get("user_prompt_sha256") != request["prompt_sha256"]
    ):
        raise ValueError("Native isolation delivery не доказана для этого request")
    # Recheck saved renderer output rather than treating a status string as sufficient proof.
    render_hash = nonempty(proof.get("stdout_sha256"), "stdout_sha256")
    if len(render_hash) != 64 or any(c not in "0123456789abcdef" for c in render_hash):
        raise ValueError("Некорректный isolation render SHA")
    render_path = native_dir / f"isolation-stdout-{render_hash}.bin"
    if sha(render_path) != proof["stdout_sha256"]:
        raise ValueError("Native isolation render hash/path не совпадает")
    rendered = read(render_path)
    if not isinstance(rendered, list) or any(
        message.get("type") != "message"
        or message.get("role") not in ("user", "developer", "system")
        or not isinstance(message.get("content"), list)
        or any(c.get("type") not in ("input_text", "text") for c in message["content"])
        for message in rendered
    ):
        raise ValueError("Некорректный native isolation render")
    texts = ["".join(c["text"] for c in message["content"]) for message in rendered]
    common = (root / request["system_prompt_path"]).read_text()
    if (
        not rendered
        or rendered[-1].get("role") != "user"
        or texts[-1] != (root / request["prompt_path"]).read_text()
        or sum(
            common in text and message.get("role") in ("developer", "system")
            for message, text in zip(rendered, texts, strict=True)
        )
        != 1
    ):
        raise ValueError("Native сохранённый render не доставляет точные инструкции")
    start, finish = started.get("started_at_epoch"), finished.get("finished_at_epoch")
    number(start, "started_at_epoch")
    number(finish, "finished_at_epoch")
    number(receipt.get("wall_elapsed_seconds"), "wall_elapsed_seconds")
    elapsed = finish - start
    if elapsed < 0 or not math.isclose(elapsed, receipt["wall_elapsed_seconds"], abs_tol=1e-6):
        raise ValueError("Native времена не согласованы")
    usage = usage if isinstance(usage, dict) else {}
    case_id, arm = request["case_id"], request["arm"]
    imported = root / "native-imports" / record_id
    source_names: tuple[str, ...] = (
        "raw-result.json",
        "receipt.json",
        "started.json",
        "finished.json",
        "prompt.txt",
        "schema.json",
        "instructions.txt",
        "events.jsonl",
        "isolation-probe.json",
        render_path.name,
    )
    optional_names = [
        name
        for name in (
            "command.json",
            "requested-config.json",
            "stderr.log",
            "execution-amendment.json",
            "isolated-model-catalog.json",
            "effective-features.txt",
        )
        if (native_dir / name).is_file()
    ]
    optional_names.extend(
        p.name
        for pattern in ("isolation-*.bin", "isolation-render-*.json")
        for p in native_dir.glob(pattern)
    )
    source_names = tuple(dict.fromkeys((*source_names, *optional_names)))
    for name in source_names:
        immutable_bytes(imported / "native" / name, (native_dir / name).read_bytes())
    envelope = {
        "schema": "nir_model_answers_v1",
        "arm": arm,
        "manifest_sha256": sha(root / "manifest.json"),
        "cases_sha256": manifest["cases_sha256"],
        "protocol_sha256": manifest["protocol_sha256"],
        "prompt_sha256": manifest["prompt_sha256"][arm],
        **{
            k: protocol[k]
            for k in ("model", "effort", "generation", "code_revision", "runtime_version")
        },
        "results": [
            {
                "case_id": case_id,
                "case_input_sha256": request["case_input_sha256"],
                "status": "ok",
                "raw_response": raw_path.read_text(),
                "started_at": datetime.fromtimestamp(start, UTC).isoformat(),
                "latency_seconds": elapsed,
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
                "cost_usd": receipt.get("cost_usd"),
                "observed_model": receipt.get("model"),
                "observed_effort": receipt.get("effort"),
                "receipt": {
                    "native_receipt": receipt,
                    "request_id": request_id,
                    "native_artifacts_sha256": {
                        name: sha(imported / "native" / name) for name in source_names
                    },
                },
            }
        ],
    }
    write_new(imported / "normalized.json", envelope)
    return import_model(root, imported / "normalized.json", record_id)


def import_claude_native(
    root: Path, request: dict[str, Any], native_dir: Path, record_id: str
) -> Path:
    """Normalize saved native_claude.execute artifacts; never execute or recover a model job."""
    manifest, _, protocol = checked(root)
    kwargs = request["claude_kwargs"]
    receipt, started, finished, requested_file = (
        read(native_dir / name)
        for name in ("receipt.json", "started.json", "finished.json", "requested-config.json")
    )
    for name, field in (
        ("prompt.txt", "prompt_sha256"),
        ("schema.json", "output_schema_sha256"),
        ("instructions.txt", "system_prompt_sha256"),
    ):
        if sha(native_dir / name) != request[field]:
            raise ValueError("Claude prompt/schema не соответствуют данному case/arm")
    requested = {"transport": "claude_cli", "model": kwargs["model"], "effort": kwargs["effort"]}
    if (
        receipt.get("transport") != "claude_cli"
        or started.get("requested_config") != requested
        or requested_file != requested
        or (receipt.get("requested_model"), receipt.get("requested_effort"))
        != (kwargs["model"], kwargs["effort"])
    ):
        raise ValueError("Claude requested configuration отличается от протокола")
    if (
        receipt.get("prompt_sha256") != request["prompt_sha256"]
        or started.get("prompt_sha256") != request["prompt_sha256"]
    ):
        raise ValueError("Claude receipt/started относятся к другому prompt")
    raw_path, stdout_path = native_dir / "raw-result.json", native_dir / "stdout.json"
    for path, field in (
        (raw_path, "raw_result_sha256"),
        (stdout_path, "stdout_sha256"),
        (native_dir / "stderr.log", "stderr_sha256"),
    ):
        if sha(path) != receipt.get(field):
            raise ValueError("Claude raw/stdout hash не совпадает")
        if path.stat().st_size > kwargs["max_output_file_bytes"]:
            raise ValueError("Claude output превышает byte cap")
    result = read(stdout_path)
    if (
        finished.get("exit_code") != 0
        or not isinstance(result, dict)
        or result.get("type") != "result"
        or result.get("is_error") is not False
        or result.get("subtype") != "success"
        or result.get("permission_denials") != []
        or not isinstance(result.get("structured_output"), dict)
        or read(raw_path) != result["structured_output"]
    ):
        raise ValueError("Нет успешного Claude результата; используйте technical_skip")
    usage = result.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    tokens = {
        key: usage.get(key)
        for key in (
            "input_tokens",
            "output_tokens",
            "cache_read_input_tokens",
            "cache_creation_input_tokens",
        )
    }
    cost = result.get("total_cost_usd")
    model_usage = result.get("modelUsage")
    observed = (
        next(iter(model_usage)) if isinstance(model_usage, dict) and len(model_usage) == 1 else None
    )
    if (
        tokens != receipt.get("tokens")
        or (cost if type(cost) in (int, float) else None) != receipt.get("cost_usd")
        or observed != receipt.get("model")
        or receipt.get("effort") is not None
        or result.get("session_id") != receipt.get("session_id")
    ):
        raise ValueError("Claude receipt не согласован с сохранённым результатом")
    # Recheck the copied stored proof (saved init events), not only recorded hashes.
    proof = verify_isolation_proof(
        native_dir,
        model=kwargs["model"],
        effort=kwargs["effort"],
        cli_version=str(receipt.get("cli_version")),
    )
    if (
        proof["isolation_proof_sha256"] != receipt.get("isolation_proof_sha256")
        or proof["isolation_proof_sha256"] != started.get("isolation_proof_sha256")
        or any(
            sha(native_dir / f"isolation-{label}.json") != receipt.get(f"isolation_{label}_sha256")
            or receipt.get(f"isolation_{label}_sha256") != started.get(f"isolation_{label}_sha256")
            for label in ("probe", "control")
        )
    ):
        raise ValueError("Claude isolation proof hash не совпадает")
    proof_names = ["isolation-proof.json", *proof["files_sha256"]]
    if receipt.get("tool_registry") != [] or receipt.get("mcp_servers") != []:
        raise ValueError("Claude receipt не подтверждает пустой registry")
    start, finish = started.get("started_at_epoch"), finished.get("finished_at_epoch")
    number(start, "started_at_epoch")
    number(finish, "finished_at_epoch")
    number(receipt.get("wall_elapsed_seconds"), "wall_elapsed_seconds")
    elapsed = finish - start
    if elapsed < 0 or not math.isclose(elapsed, receipt["wall_elapsed_seconds"], abs_tol=1e-6):
        raise ValueError("Claude времена не согласованы")
    case_id, arm = request["case_id"], request["arm"]
    imported = root / "native-imports" / record_id
    source_names = tuple(
        dict.fromkeys(
            (
                "raw-result.json",
                "receipt.json",
                "started.json",
                "finished.json",
                "requested-config.json",
                "prompt.txt",
                "schema.json",
                "instructions.txt",
                "stdout.json",
                "stderr.log",
                *proof_names,
                *(
                    name
                    for name in ("command.json", "cli-version.txt", "cli-help.txt")
                    if (native_dir / name).is_file()
                ),
                *sorted(p.name for p in native_dir.glob("isolation-*")),
            )
        )
    )
    for name in source_names:
        immutable_bytes(imported / "native" / name, (native_dir / name).read_bytes())
    parts = [
        tokens[key]
        for key in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
    ]
    components = [n for n in parts if type(n) is int and n >= 0]
    envelope = {
        "schema": "nir_model_answers_v1",
        "arm": arm,
        "manifest_sha256": sha(root / "manifest.json"),
        "cases_sha256": manifest["cases_sha256"],
        "protocol_sha256": manifest["protocol_sha256"],
        "prompt_sha256": manifest["prompt_sha256"][arm],
        **{
            k: protocol[k]
            for k in ("model", "effort", "generation", "code_revision", "runtime_version")
        },
        "results": [
            {
                "case_id": case_id,
                "case_input_sha256": request["case_input_sha256"],
                "status": "ok",
                "raw_response": raw_path.read_text(),
                "started_at": datetime.fromtimestamp(start, UTC).isoformat(),
                "latency_seconds": elapsed,
                # Claude reports cache reads/writes beside input_tokens, not inside it.
                "input_tokens": sum(components) if len(components) == len(parts) else None,
                "output_tokens": tokens["output_tokens"]
                if type(tokens["output_tokens"]) is int
                else None,
                "cost_usd": receipt.get("cost_usd"),
                "observed_model": receipt.get("model"),
                "observed_effort": None,
                "receipt": {
                    "native_receipt": receipt,
                    "request_id": request["request_id"],
                    "transport": "claude_cli",
                    "native_artifacts_sha256": {
                        name: sha(imported / "native" / name) for name in source_names
                    },
                },
            }
        ],
    }
    write_new(imported / "normalized.json", envelope)
    return import_model(root, imported / "normalized.json", record_id)


def records(root: Path, directory: str, key: str) -> list[dict[str, Any]]:
    rows = []
    manifest_hash = sha(root / "manifest.json")
    for path in sorted((root / directory).rglob("*.json")):
        record = read(path)
        if record.get("manifest_sha256") != manifest_hash:
            raise ValueError("Запись от другого замороженного комплекта")
        rows.extend(record[key])
    return rows


def human_state(root: Path, cases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_person: dict[str, dict[str, Any]] = {}
    for annotator in ANNOTATORS:
        by_person[annotator] = {}
        for wrapper in sorted((root / "human-records" / annotator).glob("*.json")):
            record = read(wrapper)
            if record["manifest_sha256"] != sha(root / "manifest.json"):
                raise ValueError("Человеческая запись от другого комплекта")
            answers = record["answers"]
            for row in answers["answers"]:
                if row["case_id"] in by_person[annotator]:
                    raise ValueError("Дублирующая разметка: исправление нельзя молча смешивать")
                by_person[annotator][row["case_id"]] = row
    state: dict[str, dict[str, Any]] = {}
    for case in cases:
        rows = [by_person[a].get(case["case_id"]) for a in ANNOTATORS]
        if any(row is None or row["status"] == "technical_skip" for row in rows):
            state[case["case_id"]] = {"status": "human_missing", "label": None}
        else:
            left, right = rows
            assert left is not None and right is not None
            if left["label"] == right["label"]:
                state[case["case_id"]] = {"status": "agreement", "label": left["label"]}
            else:
                state[case["case_id"]] = {"status": "unresolved", "label": None}
        state[case["case_id"]]["initial_labels"] = [
            row["label"] if row is not None and row["status"] == "ok" else None for row in rows
        ]
    for row in records(root, "adjudications", "decisions"):
        if row["case_id"] not in state or state[row["case_id"]]["status"] != "unresolved":
            raise ValueError("Арбитраж допустим ровно один раз для реально спорной пары")
        state[row["case_id"]].update(status="adjudicated", label=row["label"])
    return state


def adjudicate(root: Path, path: Path, record_id: str) -> Path:
    _, cases, _ = checked(root)
    identifier(record_id)
    value = read(path)
    if value.get("schema") != "nir_adjudication_v1" or value.get("manifest_sha256") != sha(
        root / "manifest.json"
    ):
        raise ValueError("Неверный арбитражный пакет")
    nonempty(value.get("adjudicator"), "adjudicator")
    timestamp(value.get("reviewed_at"))
    if value.get("actual_human_attestation") is not True:
        raise ValueError("Нужен реальный арбитраж человека")
    states, index = human_state(root, cases), {c["case_id"]: c for c in cases}
    seen = set()
    for row in value.get("decisions", []):
        case_id = row.get("case_id")
        if case_id in seen or case_id not in states or states[case_id]["status"] != "unresolved":
            raise ValueError("Арбитраж только реального неразрешённого разногласия")
        seen.add(case_id)
        validate_answer({**row, "status": "ok"}, index[case_id])
    if not seen:
        raise ValueError("Нет арбитражных решений")
    target = root / "adjudications" / f"{record_id}.json"
    write_new(target, {**value, "answers_sha256": sha(path)})
    return target


def arm_metrics(rows: list[dict[str, Any]], arm: str) -> dict[str, Any]:
    resolved = [r for r in rows if r["human_label"] is not None]
    accepted = [r for r in rows if r[arm] == "supported"]
    resolved_accepted = [r for r in accepted if r["human_label"] is not None]
    correct = sum(r["human_label"] == "supported" for r in resolved_accepted)
    unsupported = len(resolved_accepted) - correct
    good = sum(r["human_label"] == "supported" for r in resolved)
    unknown_accepted = len(accepted) - len(resolved_accepted)
    refuted = sum(r["human_label"] == "refuted" for r in resolved_accepted)
    insufficient = sum(r["human_label"] == "insufficient" for r in resolved_accepted)
    return {
        "processed_cases": len(rows),
        "resolved_cases": len(resolved),
        "accepted_all": len(accepted),
        "accepted_resolved": len(resolved_accepted),
        "accepted_unknown_human": unknown_accepted,
        "unsupported_accepted_resolved": unsupported,
        "refuted_accepted_resolved": refuted,
        "insufficient_accepted_resolved": insufficient,
        "supported_human": good,
        "supported_accepted": correct,
        "people_with_supported_acceptance": len(
            {r["group_id"] for r in resolved_accepted if r["human_label"] == "supported"}
        ),
        "R_resolved": ratio(unsupported, len(resolved_accepted)),
        "R_refuted_component": ratio(refuted, len(resolved_accepted)),
        "R_insufficient_component": ratio(insufficient, len(resolved_accepted)),
        "R_all_accepted_bounds": [
            ratio(unsupported, len(accepted)),
            ratio(unsupported + unknown_accepted, len(accepted)),
        ],
        "T": ratio(correct, good),
        "coverage": ratio(len(accepted), len(rows)),
        "technical_missing": sum(r[f"{arm}_technical"] for r in rows),
        "insufficient": sum(r[arm] == "insufficient" for r in rows),
        "refuted": sum(r[arm] == "refuted" for r in rows),
    }


def delta(left: float | None, right: float | None) -> float | None:
    return left - right if left is not None and right is not None else None


def differences(b: dict[str, Any], c: dict[str, Any]) -> dict[str, float | None]:
    return {
        "R_B_minus_C": delta(b["R_resolved"], c["R_resolved"]),
        "T_C_minus_B": delta(c["T"], b["T"]),
        "coverage_C_minus_B": delta(c["coverage"], b["coverage"]),
    }


def human_agreement(states: dict[str, dict[str, Any]]) -> dict[str, Any]:
    labels = [s["initial_labels"] for s in states.values() if None not in s["initial_labels"]]
    count = len(labels)
    observed = ratio(sum(a == b for a, b in labels), count)
    left, right = Counter(a for a, _ in labels), Counter(b for _, b in labels)
    expected = sum(left[label] * right[label] for label in LABELS) / count**2 if count else None
    kappa = (
        (observed - expected) / (1 - expected)
        if observed is not None and expected is not None and expected < 1
        else None
    )
    return {
        "both_reviewed_cases": count,
        "agreement": observed,
        "kappa_unweighted": kappa,
        "confusion": {
            a: {b: sum(x == a and y == b for x, y in labels) for b in LABELS} for a in LABELS
        },
        "note": "Initial independent labels only, before adjudication; missing excluded explicitly",
    }


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def paired_bootstrap(rows: list[dict[str, Any]], seed: int, resamples: int) -> dict[str, Any]:
    if not 1 <= resamples <= 100000:
        raise ValueError("resamples должен быть от 1 до 100000")
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row["group_id"]].append(row)
    ids, rng = sorted(groups), random.Random(seed)
    values: dict[str, list[float]] = {
        "R_B_minus_C": [],
        "T_C_minus_B": [],
        "coverage_C_minus_B": [],
    }
    for _ in range(resamples):
        sample = [row for _ in ids for row in groups[rng.choice(ids)]]
        b, c = arm_metrics(sample, "B"), arm_metrics(sample, "C")
        sample_differences = differences(b, c)
        for field, series in values.items():
            difference = sample_differences[field]
            if difference is not None:
                series.append(difference)
    return {
        "method": "shared researcher-cluster percentile bootstrap; signs in field names",
        "seed": seed,
        "resamples": resamples,
        "clusters": len(ids),
        "intervals": {
            field: {
                "valid_draws": len(series),
                "undefined_draws": resamples - len(series),
                "conditional_on_defined_draws": len(series) < resamples,
                "degenerate": bool(series) and min(series) == max(series),
                "interval_95": [percentile(series, 0.025), percentile(series, 0.975)]
                if series
                else None,
            }
            for field, series in values.items()
        },
        "warning": (
            "Exploratory interval; undefined draws disclosed; "
            "small pilot is not a confirmatory test. Degenerate/zero-error bootstrap "
            "cannot establish zero population risk or confirm a practical margin"
        ),
    }


def analyze(root: Path, output: Path, *, seed: int = 154, resamples: int = 2000) -> Path:
    manifest, cases, _ = checked(root)
    output = private_output(output)
    states = human_state(root, cases)
    models: dict[str, dict[str, Any]] = {"B": {}, "C": {}}
    resources: dict[str, Any] = {}
    for arm in ("B", "C"):
        results = records(root, f"model-records/{arm}", "results")
        for result in results:
            if result["case_id"] in models[arm]:
                raise ValueError("Повторный model результат нельзя молча усреднять")
            models[arm][result["case_id"]] = result
        resources[arm] = {
            "recorded_attempts": len(results),
            "unrecorded_cases": len(cases) - len(results),
            "configuration_mismatches": sum(r["configuration_mismatch"] for r in results),
            "unknown_observed_model": sum(r["observed_model"] is None for r in results),
            "unknown_observed_effort": sum(r["observed_effort"] is None for r in results),
            "missing_receipts": sum(r["receipt"] is None for r in results),
            **{
                field: {
                    "known_sum": sum(r[field] for r in results if r[field] is not None),
                    "unknown_attempts": sum(r[field] is None for r in results),
                    "total": sum(r[field] for r in results)
                    if len(results) == len(cases) and all(r[field] is not None for r in results)
                    else None,
                }
                for field in ("input_tokens", "output_tokens", "cost_usd", "latency_seconds")
            },
        }
    rows = []
    for case in cases:
        row = {
            "case_id": case["case_id"],
            "group_id": case["group_id"],
            "human_status": states[case["case_id"]]["status"],
            "human_label": states[case["case_id"]]["label"],
        }
        for arm in ("B", "C"):
            model_row = models[arm].get(case["case_id"])
            row[arm] = model_row["label"] if model_row else None
            row[f"{arm}_technical"] = model_row is None or model_row["status"] == "technical_skip"
        rows.append(row)
    b, c = arm_metrics(rows, "B"), arm_metrics(rows, "C")
    for arm, metrics in (("B", b), ("C", c)):
        resources[arm]["unit_totals"] = {
            field: {
                unit: total / denominator if total is not None and denominator else None
                for unit, denominator in (
                    ("per_case", len(rows)),
                    ("per_group", len({r["group_id"] for r in rows})),
                    ("per_supported_accept", metrics["supported_accepted"]),
                )
            }
            for field in ("cost_usd", "input_tokens", "output_tokens", "latency_seconds")
            for total in [resources[arm][field]["total"]]
        }
    human_resources: dict[str, Any] = {}
    for annotator in ANNOTATORS:
        saved = [read(p)["answers"] for p in (root / "human-records" / annotator).glob("*.json")]
        minutes = sum(a["minutes"] for a in saved) if saved else None
        reviewed = sum(row["status"] == "ok" for a in saved for row in a["answers"])
        human_resources[annotator] = {
            "recorded_minutes": minutes,
            "reviewed_cases": reviewed,
            "minutes_per_reviewed_case": minutes / reviewed
            if minutes is not None and reviewed
            else None,
            "complete": reviewed == len(cases),
            "note": (
                "Self-reported total includes technical attempts; average is not per-case timing"
            ),
        }
    valid = [r for r in rows if not r["B_technical"] and not r["C_technical"]]
    unknown = [r for r in rows if r["human_label"] is None]
    accepted_bounds = [
        delta(b["R_all_accepted_bounds"][0], c["R_all_accepted_bounds"][1]),
        delta(b["R_all_accepted_bounds"][1], c["R_all_accepted_bounds"][0]),
    ]
    paired_cells = {
        label or "unknown_human": {
            f"B{b_accept}_C{c_accept}": sum(
                r["human_label"] == label
                and (r["B"] == "supported") == bool(b_accept)
                and (r["C"] == "supported") == bool(c_accept)
                for r in rows
            )
            for b_accept in (0, 1)
            for c_accept in (0, 1)
        }
        for label in (*LABELS, None)
    }
    per_annotator = {}
    for i, annotator in enumerate(ANNOTATORS):
        sensitivity_rows = [
            {**r, "human_label": states[r["case_id"]]["initial_labels"][i]} for r in rows
        ]
        per_annotator[annotator] = {arm: arm_metrics(sensitivity_rows, arm) for arm in ("B", "C")}
    write_new(
        output,
        {
            "schema": "nir_analysis_v1",
            "manifest_sha256": sha(root / "manifest.json"),
            "created_at": now(),
            "status": "offline_analysis_not_scientific_completion",
            "holdout_status": manifest.get("holdout_status", "legacy_unclassified_not_holdout"),
            **diagnostic_scope(manifest),
            "configuration_status": (
                "mismatch"
                if any(r["configuration_mismatches"] for r in resources.values())
                else "unknown_or_incomplete"
                if any(
                    r["unknown_observed_model"]
                    or r["unknown_observed_effort"]
                    or r["missing_receipts"]
                    or r["unrecorded_cases"]
                    for r in resources.values()
                )
                else "declared_match_not_independently_verified"
            ),
            "human_status_counts": dict(Counter(s["status"] for s in states.values())),
            "human_initial_agreement": human_agreement(states),
            "per_annotator_sensitivity": per_annotator,
            "paired_acceptance_by_human_class": paired_cells,
            "unknown_human_case_ids": [r["case_id"] for r in unknown],
            "intention_to_process": {"B": b, "C": c},
            "paired_valid_diagnostic": {
                "cases": len(valid),
                "B": arm_metrics(valid, "B"),
                "C": arm_metrics(valid, "C"),
            },
            "differences": differences(b, c),
            "R_B_minus_C_all_accepted_conservative_bounds": accepted_bounds,
            "bootstrap": paired_bootstrap(rows, seed, resamples),
            "resources": resources,
            "human_resources": human_resources,
            "rows": rows,
            "limitations": [
                "No confirmatory p-value: R uses different accepted sets; no unpaired formula",
                "No power/sample-size estimate without a real pilot and chosen practical margins",
                "Bounds include human missing and unresolved; no conversion to insufficient",
                "Exports cannot prove absence of prior human exposure or inventory omissions",
            ],
        },
    )
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in (
        "freeze",
        "export",
        "import-human",
        "import-model",
        "adjudicate",
        "analyze",
        "prepare-model",
        "import-native",
    ):
        command = sub.add_parser(name)
        command.add_argument("--root", required=True, type=Path)
        if name == "freeze":
            command.add_argument("--selection", required=True, type=Path)
            command.add_argument("--exclusions", required=True, type=Path)
            command.add_argument("--protocol", required=True, type=Path)
            mode = command.add_mutually_exclusive_group()
            mode.add_argument("--development-only", action="store_true")
            mode.add_argument("--diagnostic-decision", type=Path)
        elif name == "export":
            command.add_argument("--annotator", required=True, choices=ANNOTATORS)
        elif name == "analyze":
            command.add_argument("--out", required=True, type=Path)
            command.add_argument("--seed", default=154, type=int)
            command.add_argument("--resamples", default=2000, type=int)
        elif name == "prepare-model":
            command.add_argument("--seed", default=154, type=int)
        elif name == "import-native":
            command.add_argument("--request-id", required=True)
            command.add_argument("--native-dir", required=True, type=Path)
            command.add_argument("--record-id", required=True)
        else:
            command.add_argument("--answers", required=True, type=Path)
            command.add_argument("--record-id", required=True)
    args = parser.parse_args()
    root = private_root(args.root)
    if args.command == "freeze":
        result = freeze(
            root,
            args.selection,
            args.exclusions,
            args.protocol,
            development_only=args.development_only,
            diagnostic_decision=args.diagnostic_decision,
        )
    elif args.command == "export":
        result = export(root, args.annotator)
    elif args.command == "analyze":
        result = analyze(root, args.out, seed=args.seed, resamples=args.resamples)
    elif args.command == "prepare-model":
        result = prepare_model(root, seed=args.seed)
    elif args.command == "import-native":
        result = import_native(root, args.request_id, args.native_dir, args.record_id)
    else:
        function = {
            "import-human": import_human,
            "import-model": import_model,
            "adjudicate": adjudicate,
        }[args.command]
        result = function(root, args.answers, args.record_id)
    print(result)


if __name__ == "__main__":
    main()
