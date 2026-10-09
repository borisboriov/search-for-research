"""Версия 3: раздельная семантическая переоценка сохранённых доказательств.

Не ищет в интернете, не определяет смысл по ключевым словам и не считает
находки проверяющего независимыми подтверждениями или человеческим эталоном.
"""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from enrichment_experiment import FIELDS, private_root, read, sha, verified_sample
from enrichment_verification import OBJECTS, identifier, immutable_bytes, immutable_json

RULES_VERSION = "semantic-v3"
VERDICTS = ("supported", "refuted", "insufficient", "conflicting")
FIELD_VERDICTS = ("correct", "misclassified", "insufficient")
EXTRA_FIELDS = ("appointment_duration", "nationality", "person_status")
FACT_KINDS = (
    "literal",
    "effort",
    "appointment_duration",
    "institutional_external",
    "nationality",
    "supervision_history",
    "intake",
    "willingness",
    "person_status",
)
LEVELS = ("undergraduate", "masters", "phd", "postdoc", "unknown")
APPLICABILITY = ("current", "historical", "expired", "undated", "unknown", "explicit_negative")
DATE_BASES = ("content", "source_metadata", "url_only", "conflicting", "unknown")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _frozen_profile(root: Path, source: dict[str, Any]) -> None:
    frozen = {row["id"]: row for row in verified_sample(root)}
    _require(
        source.get("profile") == frozen.get(source["author_id"]),
        "Профиль отличается от исходной выборки",
    )
    _require(source.get("sample_sha256") == sha(root / "sample.json"), "Другая версия выборки")


def _snapshot(root: Path, path: Path) -> str:
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    immutable_bytes(root / "semantic-source-snapshots" / f"{digest}.json", payload)
    return digest


def prepare(root: Path, input_path: Path, old_output: Path, rubric: Path) -> Path:
    """Скрывает ожидаемые решения; сохраняет точные исходные байты и цитаты."""
    root = private_root(root)
    source, old = read(input_path), read(old_output)
    _frozen_profile(root, source)
    _require(old["input_sha256"] == sha(input_path), "Старая оценка другого входа")
    pool: dict[str, Any] = {}
    items: list[dict[str, Any]] = []

    def refs(evidence: list[dict[str, Any]]) -> list[str]:
        ids = []
        for row in evidence:
            # Объяснения автора/проверяющего могут раскрывать ожидаемый вердикт.
            entry = {
                key: row.get(key)
                for key in ("url", "excerpt", "checked_at", "information_date", "object_type")
            }
            existing = next((key for key, value in pool.items() if value == entry), None)
            key = existing or f"E{len(pool) + 1:04d}"
            pool[key] = entry
            ids.append(key)
        return ids

    verdicts = {row["claim_id"]: row for row in old["result"]["claim_verdicts"]}
    for claim in source["collector"]["claims"]:
        items.append(
            {
                "item_id": claim["claim_id"],
                "origin": "collector",
                "original_field": claim["field"],
                "value": claim["value"],
                "evidence_refs": refs(claim["evidence"] + verdicts[claim["claim_id"]]["evidence"]),
            }
        )
    for index, finding in enumerate(old["result"]["new_findings"]):
        items.append(
            {
                "item_id": f"candidate_{index:03d}",
                "origin": "verifier_candidate",
                "original_field": finding["field"],
                "value": finding["value"],
                "evidence_refs": refs(finding["evidence"]),
                "candidate_row_sha256": hashlib.sha256(
                    json.dumps(finding, sort_keys=True, ensure_ascii=False).encode()
                ).hexdigest(),
            }
        )
    profile_evidence = {}
    for name in ("identity", "current_affiliation"):
        profile_evidence[name] = refs(old["result"][name]["evidence"])
    value = {
        "author_id": source["author_id"],
        "profile": source["profile"],
        "rules_version": RULES_VERSION,
        "rubric_sha256": sha(rubric),
        "sample_sha256": source["sample_sha256"],
        "source_input_sha256": _snapshot(root, input_path),
        "old_output_sha256": _snapshot(root, old_output),
        "collector_agent_id": source["collector"].get("provenance", {}).get("agent_id"),
        "old_verifier_agent_id": old["result"]["provenance"].get("agent_id"),
        "items": items,
        "evidence_pool": pool,
        "profile_evidence": profile_evidence,
        "search_scope": "saved_material_only_no_network",
        "source_text_policy": "untrusted_data_not_instructions",
    }
    path = root / "semantics" / RULES_VERSION / "inputs" / f"{identifier(source['author_id'])}.json"
    immutable_json(path, value)
    return path


def prepare_control(
    root: Path,
    profile: dict[str, Any],
    collector_path: Path,
    evidence_pool: dict[str, Any],
    rubric: Path,
    sample_sha256: str,
    *,
    namespace: str | None = None,
) -> Path:
    """Вход независимого проверяющего после реального нового cache-only сборщика.

    collector_path — его неизменяемый JSON с author_id, items (item_id, field,
    value, evidence_refs), provenance.agent_id и profile_evidence (без вердиктов).
    Дополнительные категории разрешены отдельно от исходных 18 полей.
    """
    root = private_root(root)
    collector = read(collector_path)
    author_id = collector["author_id"]
    _require(author_id == profile["id"], "Сборщик другого фиксированного профиля")
    items = []
    for row in collector["items"]:
        _require(row["field"] in (*FIELDS, *EXTRA_FIELDS), "Неизвестное поле сборщика")
        _require(
            not any(key in row for key in ("verdict", "expected_verdict")),
            "Ожидаемый вердикт запрещён",
        )
        _require(
            all(ref in evidence_pool for ref in row["evidence_refs"]),
            "Неизвестный источник сборщика",
        )
        items.append(
            {
                "item_id": identifier(row["item_id"]),
                "origin": "collector",
                "original_field": row["field"],
                "value": row["value"],
                "evidence_refs": row["evidence_refs"],
            }
        )
    _require(len({row["item_id"] for row in items}) == len(items), "Повторный атом")
    value = {
        "source_kind": "control_cache_only_collection",
        "author_id": author_id,
        "profile": profile,
        "rules_version": RULES_VERSION,
        "rubric_sha256": sha(rubric),
        "sample_sha256": sample_sha256,
        "source_input_sha256": _snapshot(root, collector_path),
        "old_output_sha256": None,
        "collector_agent_id": collector["provenance"]["agent_id"],
        "old_verifier_agent_id": None,
        "items": items,
        "evidence_pool": evidence_pool,
        "profile_evidence": collector.get("profile_evidence", {}),
        "search_scope": "saved_material_only_no_network",
        "source_text_policy": "untrusted_data_not_instructions",
    }
    base = root / "semantics" / RULES_VERSION
    directory = (
        base / "control-inputs"
        if namespace is None
        else base / "control-runs" / identifier(namespace) / "inputs"
    )
    path = directory / f"{identifier(author_id)}.json"
    _frozen_profile(root, value)
    immutable_json(path, value)
    return path


def classification(item: dict[str, Any], assessment: dict[str, Any]) -> dict[str, Any]:
    """Правила допустимости после агентской оценки; не подменяют её эвристикой."""
    reasons = []
    if item["original_field"] not in FIELDS:
        reasons.append("additional_field_not_original_coverage")
    if item["origin"] != "collector":
        reasons.append("new_finding_candidate_not_independently_confirmed")
    for key in ("text_verdict", "identity_verdict"):
        if assessment[key] != "supported":
            reasons.append(key)
    if assessment["field_verdict"] != "correct":
        reasons.append("field_verdict")
    if assessment["object_relation"] != "supported":
        reasons.append("object_relation")
    field = item["original_field"]
    kind = assessment["fact_kind"]
    if field == "workload" and kind != "effort":
        reasons.append("workload_requires_effort_not_duration")
    if field == "external_students" and kind != "institutional_external":
        reasons.append("external_requires_institutional_membership")
    expected_kind = {
        "supervision_history": "supervision_history",
        "published_recruitment": "intake",
        "direct_willingness": "willingness",
    }.get(field)
    if expected_kind and kind != expected_kind:
        reasons.append("field_requires_matching_fact_kind")
    if field == "direct_willingness" and assessment["object_type"] != "scientist":
        reasons.append("personal_willingness_requires_scientist")
    if assessment["current_applicability"] == "explicit_negative":
        reasons.append("negative_not_positive_coverage")
    if field in ("published_recruitment", "direct_willingness"):
        if assessment["current_applicability"] != "current":
            reasons.append("opportunity_not_current")
        if assessment["information_date"] is None or assessment["date_basis"] in (
            "url_only",
            "conflicting",
            "unknown",
        ):
            reasons.append("current_opportunity_date_unestablished")
        if set(assessment["student_level"]) <= {"postdoc", "unknown"}:
            reasons.append("student_opportunity_not_established")
    return {
        "usable_coverage": not reasons,
        "coverage_field": field if not reasons else None,
        "reason": reasons,
        "corrected_field": assessment["corrected_field"],
        "candidate_only": item["origin"] != "collector",
    }


def validate(source: dict[str, Any], result: dict[str, Any], input_sha: str) -> dict[str, Any]:
    _require(result.get("input_sha256") == input_sha, "SHA входа не совпадает")
    _require(result.get("author_id") == source["author_id"], "Другой профиль")
    _require(result.get("rules_version") == RULES_VERSION, "Другая версия правил")
    provenance = result.get("provenance", {})
    _require(bool(provenance.get("agent_id")), "Нет независимого исполнителя")
    _require(
        provenance["agent_id"]
        not in (source.get("collector_agent_id"), source.get("old_verifier_agent_id")),
        "Исполнитель уже извлекал или проверял этот профиль",
    )
    _require(
        provenance.get("runtime_status") in ("recorded", "runtime_not_exposed"),
        "Нет статуса runtime",
    )
    for key in ("model", "effort", "tokens", "cost_usd"):
        _require(key in provenance, f"Неизвестные {key} должны быть null")
    for key in ("tokens", "cost_usd"):
        value = provenance[key]
        _require(
            value is None
            or (isinstance(value, int | float) and not isinstance(value, bool) and value >= 0),
            f"Некорректный {key}",
        )
    if provenance["runtime_status"] == "recorded":
        _require(bool(provenance["model"] and provenance["effort"]), "Нет model/effort")
    items = {row["item_id"]: row for row in source["items"]}
    assessments = result.get("items", [])
    actual = [row.get("item_id") for row in assessments]
    _require(
        len(actual) == len(set(actual)) and set(actual) == set(items),
        "Оценить каждый атом один раз",
    )

    def evidence_refs(row: dict[str, Any]) -> None:
        refs = row.get("evidence_refs")
        _require(
            isinstance(refs, list) and all(ref in source["evidence_pool"] for ref in refs),
            "Неизвестное доказательство",
        )
        _require(bool(row.get("explanation")), "Нет объяснения")

    derived = {}
    for row in assessments:
        evidence_refs(row)
        for key in ("text_verdict", "identity_verdict"):
            _require(row.get(key) in VERDICTS, f"Неизвестный {key}")
        _require(row.get("field_verdict") in FIELD_VERDICTS, "Неизвестная пригодность поля")
        corrected = row.get("corrected_field")
        _require(
            corrected is None or corrected in (*FIELDS, *EXTRA_FIELDS),
            "Неизвестное исправленное поле",
        )
        if row["field_verdict"] == "misclassified":
            _require(
                corrected != items[row["item_id"]]["original_field"],
                "Исправление оставляет неверное поле",
            )
        if row["field_verdict"] == "correct":
            _require(corrected is None, "Корректное поле не требует переноса")
        _require(row.get("object_type") in OBJECTS, "Неизвестный объект")
        _require(
            row.get("object_relation") in ("supported", "insufficient", "conflicting"),
            "Не установлена связь объекта",
        )
        _require(row.get("fact_kind") in FACT_KINDS, "Неизвестный вид факта")
        levels = row.get("student_level")
        _require(
            isinstance(levels, list) and bool(levels) and all(x in LEVELS for x in levels),
            "Нужен уровень студента",
        )
        _require(
            "information_date" in row
            and (row["information_date"] is None or isinstance(row["information_date"], str)),
            "Нужна дата или null",
        )
        _require(row.get("date_basis") in DATE_BASES, "Неизвестное основание даты")
        _require(row.get("current_applicability") in APPLICABILITY, "Неизвестная применимость")
        _require(isinstance(row.get("question"), str), "Нужен вопрос человеку")
        if row["text_verdict"] == "supported":
            _require(bool(row["evidence_refs"]), "Подтверждение без источника")
        if row["date_basis"] in ("url_only", "conflicting", "unknown"):
            _require(row["information_date"] is None, "Неопределённую дату нельзя додумывать")
        field, kind = items[row["item_id"]]["original_field"], row["fact_kind"]
        inherently_other_field = {
            "appointment_duration": "appointment_duration",
            "nationality": "nationality",
            "person_status": "person_status",
        }.get(kind)
        if (inherently_other_field is not None and field != inherently_other_field) or (
            field == "direct_willingness" and row["object_type"] != "scientist"
        ):
            _require(
                row["field_verdict"] != "correct",
                "Текст подтверждён, но поле неверно классифицировано",
            )
        derived[row["item_id"]] = classification(items[row["item_id"]], row)
    profiles = result.get("profile_assessments", {})
    _require(
        set(profiles) == {"identity", "current_affiliation", "activity"},
        "Нужны независимые оценки личности, аффилиации и активности",
    )
    for row in profiles.values():
        _require(row.get("verdict") in VERDICTS, "Неизвестный профильный вердикт")
        evidence_refs(row)
        if row["verdict"] == "supported":
            _require(bool(row["evidence_refs"]), "Профиль подтверждён без источника")
        _require(
            row.get("date_basis") in DATE_BASES and "information_date" in row,
            "Нужна дата профильного факта",
        )
        if row["date_basis"] in ("url_only", "conflicting", "unknown"):
            _require(row["information_date"] is None, "Неопределённая профильная дата")
    _require(
        profiles["activity"].get("status") in ("active", "deceased", "ceased", "unknown"),
        "Нужен отдельный статус активности, включая смерть или неопределённость",
    )
    summary = result.get("summary", {})
    _require(
        set(summary) == {"known", "unknown", "identity", "current_opportunity"}
        and all(isinstance(x, str) and x.strip() for x in summary.values()),
        "Нужны понятные краткие выводы",
    )
    return derived


def import_result(root: Path, input_path: Path, result_path: Path, run_id: str) -> Path:
    root = private_root(root)
    source = read(input_path)
    _frozen_profile(root, source)
    for name in ("source_input_sha256", "old_output_sha256"):
        digest = source[name]
        if digest is None and name == "old_output_sha256":
            _require(
                source.get("source_kind") == "control_cache_only_collection",
                "Нет старого источника повторной оценки",
            )
            continue
        _require(
            sha(root / "semantic-source-snapshots" / f"{digest}.json") == digest,
            "Изменён сохранённый источник",
        )
    payload = result_path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    result = json.loads(payload)
    derived = validate(source, result, sha(input_path))
    immutable_bytes(root / "semantic-result-snapshots" / f"{digest}.json", payload)
    path = (
        input_path.parent.parent
        / "outputs"
        / identifier(run_id)
        / f"{identifier(source['author_id'])}.json"
    )
    immutable_json(
        path,
        {
            "input_sha256": sha(input_path),
            "input_relative_path": str(input_path.relative_to(root)),
            "result_sha256": digest,
            "rules_version": RULES_VERSION,
            "result": result,
            "classifications": derived,
            "human_reviewed": False,
            "human_verdict": None,
            "human_minutes": None,
            "accepted_automatically": False,
        },
    )
    return path


def metrics(root: Path, run_id: str, output: Path) -> dict[str, Any]:
    root = private_root(root)
    base = root / "semantics" / RULES_VERSION
    counters: dict[str, Counter[str]] = {
        name: Counter()
        for name in (
            "text_verdict",
            "identity_verdict",
            "field_verdict",
            "fact_kind",
            "current_applicability",
            "corrections_to",
            "candidate_field_verdict",
            "coverage_profiles",
            "v2_confirmed_profiles",
            "candidate_corrections_to",
            "candidate_misclassifications_by_original_field",
            "candidate_fact_kind",
            "candidate_object_type",
            "current_coverage_profiles",
            "closed_or_old_recruitment_profiles",
            "department_negative_profiles",
            "candidate_current_applicability",
            "eligibility_exclusion_reasons",
            "activity_status",
            "profile_identity",
            "profile_current_affiliation",
        )
    }
    corrections: Counter[str] = Counter()
    total = candidate_total = before_claims = eligible_claims = baseline_profiles = 0
    outputs = sorted((base / "outputs" / identifier(run_id)).glob("*.json"))
    for path in outputs:
        wrapper = read(path)
        input_path = root / wrapper.get(
            "input_relative_path", str((base / "inputs" / path.name).relative_to(root))
        )
        _require(input_path.resolve().is_relative_to(root.resolve()), "Вход вне места эксперимента")
        source = read(input_path)
        derived = validate(source, wrapper["result"], sha(input_path))
        _require(wrapper["input_sha256"] == sha(input_path), "SHA обёртки отличается")
        _require(derived == wrapper["classifications"], "Производная классификация отличается")
        items = {row["item_id"]: row for row in source["items"]}
        if source["old_output_sha256"] is not None:
            baseline_profiles += 1
            old = read(root / "semantic-source-snapshots" / f"{source['old_output_sha256']}.json")
            old_inputs = read(
                root / "semantic-source-snapshots" / f"{source['source_input_sha256']}.json"
            )
            old_fields = {
                row["claim_id"]: row["field"] for row in old_inputs["collector"]["claims"]
            }
            old_confirmed = [
                row
                for row in old["result"]["claim_verdicts"]
                if row["verdict"] == "confirmed_by_source"
            ]
            before_claims += len(old_confirmed)
            counters["v2_confirmed_profiles"].update(
                {old_fields[row["claim_id"]] for row in old_confirmed}
            )
        profiles = wrapper["result"]["profile_assessments"]
        counters["activity_status"][profiles["activity"]["status"]] += 1
        counters["profile_identity"][profiles["identity"]["verdict"]] += 1
        counters["profile_current_affiliation"][profiles["current_affiliation"]["verdict"]] += 1
        coverage = set()
        current_coverage = set()
        closed_recruitment = set()
        department_negative = set()
        for row in wrapper["result"]["items"]:
            item = items[row["item_id"]]
            if item["origin"] == "verifier_candidate":
                candidate_total += 1
                counters["candidate_field_verdict"][row["field_verdict"]] += 1
                counters["candidate_fact_kind"][row["fact_kind"]] += 1
                counters["candidate_object_type"][row["object_type"]] += 1
                counters["candidate_current_applicability"][row["current_applicability"]] += 1
                if row["field_verdict"] == "misclassified":
                    counters["candidate_corrections_to"][row["corrected_field"] or "unknown"] += 1
                    counters["candidate_misclassifications_by_original_field"][
                        item["original_field"]
                    ] += 1
                continue
            total += 1
            if item["original_field"] == "published_recruitment" and row[
                "current_applicability"
            ] in ("historical", "expired"):
                closed_recruitment.add(item["original_field"])
            if row["current_applicability"] == "explicit_negative" and row["object_type"] in (
                "laboratory",
                "organization",
            ):
                department_negative.add(item["original_field"])
            for name in (
                "text_verdict",
                "identity_verdict",
                "field_verdict",
                "fact_kind",
                "current_applicability",
            ):
                counters[name][row[name]] += 1
            if row["field_verdict"] == "misclassified":
                corrections[item["original_field"]] += 1
                counters["corrections_to"][row["corrected_field"] or "unknown"] += 1
            if derived[row["item_id"]]["usable_coverage"]:
                eligible_claims += 1
                coverage.add(item["original_field"])
                if (
                    row["current_applicability"] == "current"
                    and row["information_date"] is not None
                    and row["date_basis"] in ("content", "source_metadata")
                ):
                    current_coverage.add(item["original_field"])
            else:
                counters["eligibility_exclusion_reasons"].update(derived[row["item_id"]]["reason"])
        counters["coverage_profiles"].update(coverage)
        counters["current_coverage_profiles"].update(current_coverage)
        counters["closed_or_old_recruitment_profiles"].update(closed_recruitment)
        counters["department_negative_profiles"].update(department_negative)
    value = {
        "rules_version": RULES_VERSION,
        "evaluation_design": "reassessment_of_previously_seen_100_not_independent_test",
        "denominators": {
            "profiles": len(outputs),
            "collector_claims": total,
            "verifier_candidates": candidate_total,
            "human_reviewed": 0,
            "profiles_with_v2_baseline": baseline_profiles,
        },
        "counts": {key: dict(value) for key, value in counters.items()},
        "misclassifications_by_original_field": dict(corrections),
        "coverage_comparison": {
            field: {
                "v2_source_confirmed_profiles": counters["v2_confirmed_profiles"][field],
                "v3_usable_profiles": counters["coverage_profiles"][field],
            }
            for field in FIELDS
        },
        "claim_comparison": {"v2_source_confirmed": before_claims, "v3_usable": eligible_claims},
        "human_accuracy": None,
        "human_records_consulted": False,
        "candidates_independently_confirmed": 0,
    }
    immutable_json(output, value)
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--input", type=Path, required=True)
    prep.add_argument("--old-output", type=Path, required=True)
    prep.add_argument("--rubric", type=Path, required=True)
    imp = sub.add_parser("import")
    imp.add_argument("--input", type=Path, required=True)
    imp.add_argument("--result", type=Path, required=True)
    imp.add_argument("--run-id", required=True)
    metric = sub.add_parser("metrics")
    metric.add_argument("--run-id", required=True)
    metric.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        print(prepare(args.root, args.input, args.old_output, args.rubric))
    elif args.command == "import":
        print(import_result(args.root, args.input, args.result, args.run_id))
    else:
        metrics(args.root, args.run_id, args.output)


if __name__ == "__main__":
    main()
