"""Изолированный эксперимент: заморозка выборки и ORCID, без записи в каталог.

Все выходы, включая контакты и фрагменты, должны лежать вне git checkout.
Результат ORCID — кандидаты для проверки, не подтверждённые контакты/набор.
"""

import argparse
import hashlib
import json
import re
import sqlite3
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

FIELDS = (
    "personal_contact",
    "coordinator_contact",
    "supervision_history",
    "published_recruitment",
    "direct_willingness",
    "topic",
    "supervisor_role",
    "student_level",
    "student_year",
    "required_skills",
    "external_students",
    "thesis_possible",
    "city",
    "work_format",
    "workload",
    "payment",
    "deadline",
    "response_method",
)
STATUSES = (
    "found",
    "not_found",
    "not_checked",
    "inaccessible",
    "contradiction",
    "explicit_negative",
)
METHOD = "enrichment100-v1-pilot"
ORCID_API = "https://pub.orcid.org/v3.0"
MAX_REQUESTS = 150


def now() -> str:
    return datetime.now(UTC).isoformat()


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_new(path: Path, value: Any) -> None:
    """Не перезаписывать снимки и результаты, даже при повторном запуске."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    path.chmod(0o600)


def private_root(path: Path) -> Path:
    path = path.resolve()
    for parent in (path, *path.parents):
        if (parent / ".git").exists():
            raise ValueError("Исходные материалы и контакты должны находиться вне git")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    return path


def select_sample(docs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    ids = [row["id"] for row in docs]
    if len(ids) != len(set(ids)):
        raise ValueError("Повторный author_id в индексе")
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in docs:
        if not isinstance(row.get("h_index"), int) or row["h_index"] < 0:
            raise ValueError("Для точного отбора нужен известный неотрицательный h-index")
        institution = row.get("institution")
        if not institution:
            raise ValueError("Принадлежность вузу не определена")
        groups.setdefault(institution, []).append(row)
    if len(groups) != 12 or any(len(rows) < 8 for rows in groups.values()):
        raise ValueError("Нужны 12 вузов с минимум восемью профилями")

    def key(row: dict[str, Any]) -> tuple[int, str]:
        return -row["h_index"], row["id"]

    sample = []
    for institution in sorted(groups):
        sample.extend(sorted(groups[institution], key=key)[:8])
    selected = {row["id"] for row in sample}
    sample.extend(sorted((row for row in docs if row["id"] not in selected), key=key)[:4])
    if len(sample) != 100:
        raise ValueError("Не удалось получить ровно 100 профилей")
    return sample, sorted(groups)


def freeze(index: Path, db: Path, deployed: Path, out: Path) -> None:
    out = private_root(out)
    if (out / "manifest.json").exists():
        raise ValueError("Выборка уже заморожена; используйте её, не меняйте участников")
    meta = read(index / "meta.json")
    docs = read(index / "docs.json")
    digest = hashlib.sha256()
    for row in docs:
        digest.update(row["id"].encode())
        digest.update(b"\x00")
        digest.update(row["indexed_text"].encode())
        digest.update(b"\n")
    version = f"{meta['model_key']}_clean-{len(docs)}p-{digest.hexdigest()[:8]}"
    health = read(deployed)["runtime"]["health"]
    if (
        meta["corpus_sha"] != digest.hexdigest()
        or meta["n_profiles"] != len(docs)
        or health["index_version"] != version
        or health["profiles_count"] != len(docs)
        or health["institutions_count"] != 12
        or not meta["clean"]
    ):
        raise ValueError("Индекс не совпадает с проверенным действующим корпусом")
    sample, institutions = select_sample(docs)
    db_digest = sha(db)
    with sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True) as conn:
        rows = conn.execute(
            "SELECT a.openalex_id, a.orcid, a.display_name, a.h_index, "
            "i.openalex_id, COALESCE(i.name_ru, i.name_en), a.merged_into_id, "
            "a.suspect_merge FROM authors a JOIN institutions i "
            "ON i.id=a.last_known_institution_id"
        ).fetchall()
    catalog = {row[0].rsplit("/", 1)[-1]: row for row in rows}
    for row in sample:
        match = catalog.get(row["id"])
        if not match or (match[2], match[3], match[5], match[6]) != (
            row["name"],
            row["h_index"],
            row["institution"],
            None,
        ):
            raise ValueError("Снимок БД не соответствует выбранному профилю индекса")
        row["institution_id"] = match[4].rsplit("/", 1)[-1]
        row["orcid"] = match[1]
        row["suspect_merge"] = bool(match[7])
    if sha(db) != db_digest:
        raise ValueError("БД изменилась во время чтения")
    by_institution = {
        name: min(
            (row for row in sample if row["institution"] == name),
            key=lambda row: (-row["h_index"], row["id"]),
        )
        for name in institutions
    }
    pilot = [
        row["id"]
        for row in sorted(by_institution.values(), key=lambda row: row["institution_id"])[:10]
    ]
    for row in sample:
        row["cohort"] = "pilot" if row["id"] in pilot else "evaluation"
    hashes = {
        name: sha(index / name) for name in ("docs.json", "meta.json", "index.faiss", "vectors.npy")
    }
    write_new(out / "sample.json", sample)
    write_new(
        out / "manifest.json",
        {
            "created_at": now(),
            "method": METHOD,
            "index_version": version,
            "index_hashes": hashes,
            "db_sha256": db_digest,
            "deployment_proof_sha256": sha(deployed),
            "deployment_checked_at": read(deployed)["runtime"]["checked_at"],
            "sample_sha256": sha(out / "sample.json"),
            "pilot_ids": pilot,
            "evaluation_ids": [row["id"] for row in sample if row["id"] not in pilot],
            "selection": "8 per institution, then 4 global; -h_index, author_id",
            "live_health_rechecked": False,
        },
    )
    write_new(
        out / "source_bank.json",
        [
            {
                "institution": name,
                "institution_id": by_institution[name]["institution_id"],
                "sources": [],
                "access_status": "not_checked",
                "checked_at": None,
                "purpose": "person, department, lab, theses, recruitment, coordinator",
            }
            for name in institutions
        ],
    )
    write_new(
        out / "human_review_10.json",
        [
            {
                "author_id": row["id"],
                "name": row["name"],
                "institution": row["institution"],
                "identity_verdict": "not_checked",
                "identity_evidence": [],
                "contact_verdict": "not_checked",
                "recruitment_verdict": "not_checked",
                "human_reviewed": False,
                "reviewer": None,
                "reviewed_at": None,
                "minutes": None,
                "notes": "",
            }
            for row in sample
            if row["cohort"] == "pilot"
        ],
    )
    print(json.dumps({"index_version": version, "profiles": 100, "pilot": 10}))


def verified_sample(root: Path) -> list[dict[str, Any]]:
    if sha(root / "sample.json") != read(root / "manifest.json")["sample_sha256"]:
        raise ValueError("Замороженная выборка изменена")
    return list(read(root / "sample.json"))


def orcid_id(value: str | None) -> str | None:
    if not value:
        return None
    match = re.fullmatch(r"(?:https?://orcid.org/)?(\d{4}-\d{4}-\d{4}-\d{3}[\dX])", value)
    if not match:
        raise ValueError("Некорректный ORCID, запрос не отправлен")
    return match[1]


def public_candidates(record: dict[str, Any]) -> dict[str, Any]:
    person = record.get("person") or {}
    return {
        "name": person.get("name"),
        "other_names": person.get("other-names"),
        "emails": [
            entry
            for entry in (person.get("emails") or {}).get("email", [])
            if entry.get("visibility") == "public" and entry.get("email")
        ],
        "links": (person.get("researcher-urls") or {}).get("researcher-url", []),
        "activities": record.get("activities-summary"),
        "record_last_modified": (record.get("history") or {}).get("last-modified-date"),
        "identity_verdict": "not_checked",
        "warning": "OpenAlex ORCID is a candidate; verify name and independent identity signal",
    }


def latest_results(root: Path) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for path in sorted((root / "orcid").glob("*.json")):
        row = read(path)
        old = latest.get(row["author_id"])
        if old is None or row["checked_at"] > old["checked_at"]:
            latest[row["author_id"]] = row
    return latest


def run_orcid(
    root: Path, cohort: str, mailto: str, rules: Path, retry_transport: bool = False
) -> None:
    root = private_root(root)
    sample = verified_sample(root)
    policy = read(rules)
    if policy.get("source") != ORCID_API or policy.get("access") != "allowed":
        raise ValueError("Нужна датированная проверка правил ORCID")
    if not policy.get("checked_at") or not policy.get("terms_url"):
        raise ValueError("Отсутствует доказательство проверки условий")
    if cohort != "pilot":
        raise ValueError(
            "Оценка 90 ещё не разрешена: сначала согласование критериев и фиксация метода"
        )
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", mailto):
        raise ValueError("Нужен действительный mailto")
    write_new(root / f"access-policy-{time.time_ns()}.json", policy)
    requests_dir = root / "requests"
    requests_dir.mkdir(exist_ok=True, mode=0o700)
    attempts = len(list(requests_dir.glob("*.json")))
    started = time.monotonic()
    last_request = 0.0
    stop_path = root / "orcid-stop.json"
    stopped = stop_path.exists()
    previous = latest_results(root)
    with httpx.Client(
        timeout=30,
        follow_redirects=False,
        headers={
            "User-Agent": f"search-for-research-experiment/1.0 (mailto:{mailto})",
            "Accept": "application/json",
        },
    ) as client:
        for row in sample:
            if row["cohort"] != cohort:
                continue
            result_path = root / "orcid" / f"{row['id']}.json"
            if row["id"] in previous:
                prior = previous[row["id"]]
                if not retry_transport or prior.get("error") != "ConnectError":
                    continue
                result_path = root / "orcid" / f"{row['id']}--{time.time_ns()}.json"
            oid = orcid_id(row["orcid"])
            result: dict[str, Any] = {
                "author_id": row["id"],
                "cohort": cohort,
                "method": METHOD,
                "checked_at": now(),
                "identity_verdict": "not_checked",
                "human_reviewed": False,
                "fields": dict.fromkeys(FIELDS, "not_checked"),
                "orcid_status": "not_found" if oid is None else "not_checked",
            }
            if oid and not stopped:
                cache_path = root / "cache" / f"{oid}.json"
                if cache_path.exists():
                    cached = read(cache_path)
                    result.update(cached)
                else:
                    url = f"{ORCID_API}/{oid}/record"
                    for retry in range(3):
                        if attempts >= MAX_REQUESTS:
                            stopped = True
                            result["orcid_status"] = "not_checked"
                            result["stop_reason"] = "request_budget"
                            break
                        time.sleep(max(0, 1.0 - (time.monotonic() - last_request)))
                        attempts += 1
                        last_request = time.monotonic()
                        attempt_path = requests_dir / f"{attempts:04d}.json"
                        # Резервировать запрос до сети: после аварии расход не потеряется.
                        write_new(attempt_path, {"url": url, "started_at": now()})
                        try:
                            response = client.get(url)
                        except httpx.HTTPError as exc:
                            result.update(orcid_status="inaccessible", error=type(exc).__name__)
                            break
                        result.update(source=url, http_status=response.status_code)
                        if response.status_code in (403, 429):
                            stopped = True
                            result.update(orcid_status="inaccessible", stop_reason="access_limit")
                            write_new(
                                stop_path,
                                {
                                    "at": now(),
                                    "status": response.status_code,
                                    "reason": "access_limit; manual source review required",
                                },
                            )
                            break
                        if response.status_code >= 500 and retry < 2:
                            time.sleep(2 ** (retry + 1))
                            continue
                        if response.status_code == 200:
                            try:
                                record = response.json()
                                candidates = public_candidates(record)
                            except (ValueError, AttributeError, TypeError):
                                result.update(orcid_status="inaccessible", error="invalid_response")
                                break
                            write_new(root / "raw" / f"{oid}.json", record)
                            result.update(orcid_status="found", candidates=candidates)
                        else:
                            result["orcid_status"] = (
                                "not_found" if response.status_code == 404 else "inaccessible"
                            )
                        write_new(
                            cache_path,
                            {
                                k: result[k]
                                for k in ("source", "http_status", "orcid_status", "checked_at")
                            }
                            | (
                                {"candidates": result["candidates"]}
                                if "candidates" in result
                                else {}
                            ),
                        )
                        break
            elif oid:
                result["stop_reason"] = "source_stopped"
            write_new(result_path, result)
    write_new(
        root / f"run-{time.time_ns()}.json",
        {
            "cohort": cohort,
            "seconds": round(time.monotonic() - started, 3),
            "requests_total": attempts,
            "stopped": stopped,
            "paid_api_cost": 0,
            "external_llm_calls": 0,
        },
    )
    summary(root)


def summary(root: Path) -> dict[str, Any]:
    sample = verified_sample(root)
    results = list(latest_results(root).values())
    result = {
        "sample": len(sample),
        "pilot": 10,
        "evaluation": 90,
        "orcid_profiles_recorded": len(results),
        "orcid_statuses": dict(Counter(row["orcid_status"] for row in results)),
        "candidate_email_profiles": sum(
            bool(row.get("candidates", {}).get("emails")) for row in results
        ),
        "identity_verified_profiles": 0,
        "human_verified_profiles": 0,
        "field_statuses": {
            field: {
                "not_checked": 100,
            }
            for field in FIELDS
        },
        "network_requests": len(list((root / "requests").glob("*.json"))),
        "denominator_note": "ORCID record found does not mean identity/contact verified",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def export_metrics(root: Path, out: Path) -> None:
    """Наружу только whitelist агрегатов и отпечатков; никаких имён/email/фрагментов."""
    metrics = summary(root)
    manifest = read(root / "manifest.json")
    metrics.update(
        {
            "phase": "pilot_preparation_not_completed_experiment",
            "method": METHOD,
            "index_version": manifest["index_version"],
            "sample_sha256": manifest["sample_sha256"],
            "index_hashes": manifest["index_hashes"],
            "live_health_rechecked": manifest["live_health_rechecked"],
            "selection_unique_ids": len({row["id"] for row in verified_sample(root)}),
            "suspect_merge_profiles": sum(row["suspect_merge"] for row in verified_sample(root)),
            "historical_transport_failures": sum(
                read(path).get("error") == "ConnectError"
                for path in (root / "orcid").glob("*.json")
            ),
            "runs": [
                {
                    k: run[k]
                    for k in (
                        "cohort",
                        "seconds",
                        "requests_total",
                        "stopped",
                        "paid_api_cost",
                        "external_llm_calls",
                    )
                }
                for run in (read(path) for path in sorted(root.glob("run-*.json")))
            ],
            "identity_error_rate": None,
            "recruitment_error_rate": None,
            "human_review_minutes": None,
            "agent_manual_review_minutes": None,
            "criteria_agreed_by_human": False,
        }
    )
    review = read(root / "agent_review_10.json")
    metrics["profiles_with_shared_work_titles"] = sum(
        bool(row["shared_work_title_evidence"]) for row in review["rows"]
    )
    metrics["page_comparison"] = read(root / "comparison" / "metrics.json")
    write_new(out, metrics)


def prepare_review(root: Path, catalog_export: Path) -> None:
    """Таблица оснований для первых 10; никаких автоматических вердиктов человека."""
    root = private_root(root)
    pilot = [row for row in verified_sample(root) if row["cohort"] == "pilot"]
    selected = {row["id"] for row in pilot}
    export = {
        row["id"]: row
        for row in (
            json.loads(line) for line in catalog_export.read_text(encoding="utf-8").splitlines()
        )
        if row["id"] in selected
    }
    results = latest_results(root)
    reviews = []
    started = time.monotonic()
    for row in pilot:
        catalog = export[row["id"]]
        if (catalog["name"], catalog["institution"], catalog["h_index"]) != (
            row["name"],
            row["institution"],
            row["h_index"],
        ):
            raise ValueError("Экспорт не соответствует замороженному профилю")
        result = results.get(row["id"], {})
        candidates = result.get("candidates") or {}
        activities = candidates.get("activities") or {}
        works = activities.get("works") or {}
        titles = []
        for group in works.get("group", []):
            for work in group.get("work-summary", []):
                title = ((work.get("title") or {}).get("title") or {}).get("value")
                if title:
                    titles.append(title)

        def normalized(text: str) -> str:
            return re.sub(r"\W+", "", text.casefold())

        orcid_titles = {normalized(title): title for title in titles}
        shared = [
            {
                "catalog_title": work["title"],
                "orcid_title": orcid_titles[normalized(work["title"])],
                "catalog_work_id": work["openalex_id"],
                "mega_collaboration": work.get("is_mega_collaboration"),
            }
            for work in catalog.get("works", [])
            if normalized(work["title"]) in orcid_titles
        ]
        reviews.append(
            {
                "author_id": row["id"],
                "catalog_name": row["name"],
                "institution": row["institution"],
                "orcid_name_fragment": candidates.get("name"),
                "orcid_source": result.get("source"),
                "checked_at": result.get("checked_at"),
                "source_updated_at": candidates.get("record_last_modified"),
                "shared_work_title_evidence": shared,
                "affiliation_fragments": activities.get("employments"),
                "contact_candidates": candidates.get("emails", []),
                "identity_verdict": "not_checked",
                "contact_verdict": "not_checked",
                "recruitment_verdict": "not_checked",
                "agent_prepared": True,
                "human_reviewed": False,
                "human_reviewer": None,
                "human_minutes": None,
                "field_review": dict.fromkeys(FIELDS, "not_checked"),
                "caution": "Shared titles require review; identity is not accepted automatically",
            }
        )
    write_new(
        root / "agent_review_10.json",
        {
            "catalog_export_sha256": sha(catalog_export),
            "preparation_seconds": round(time.monotonic() - started, 3),
            "rows": reviews,
        },
    )
    lines = [
        "# Первые 10 — таблица оснований для ручной проверки",
        "",
        "Подготовлено агентом. Человеческая проверка: 0/10. Вердикты не выставлены.",
        "",
        "| ID | Имя | Вуз | Общие работы | Кандидаты email | Основания | Человек |",
        "|---|---|---|---:|---:|---|---|",
    ]
    for row in reviews:
        lines.append(
            f"| {row['author_id']} | {row['catalog_name']} | {row['institution']} | "
            f"{len(row['shared_work_title_evidence'])} | {len(row['contact_candidates'])} | "
            "agent_review_10.json: имя, работы, аффилиации и фрагменты | не просмотрено |"
        )
    lines.extend(
        [
            "",
            "Для контакта надо проверить личность и принадлежность адреса человеку.",
            "Отличие аффилиации не доказывает ошибку личности.",
            "Отсутствие работ не доказывает совпадение личности.",
            "Набор/готовность/условия студентов не проверены по ORCID; нужны отдельные источники.",
        ]
    )
    path = root / "manual_review_10.md"
    with path.open("x", encoding="utf-8") as stream:
        stream.write("\n".join(lines) + "\n")
    path.chmod(0o600)
    print(
        json.dumps(
            {
                "prepared": 10,
                "human_reviewed": 0,
                "profiles_with_shared_titles": sum(
                    bool(row["shared_work_title_evidence"]) for row in reviews
                ),
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    freeze_parser = commands.add_parser("freeze")
    freeze_parser.add_argument("--index", type=Path, required=True)
    freeze_parser.add_argument("--db", type=Path, required=True)
    freeze_parser.add_argument("--deployment-proof", type=Path, required=True)
    freeze_parser.add_argument("--out", type=Path, required=True)
    run_parser = commands.add_parser("orcid")
    run_parser.add_argument("--root", type=Path, required=True)
    run_parser.add_argument("--cohort", choices=("pilot", "evaluation"), default="pilot")
    run_parser.add_argument("--mailto", required=True)
    run_parser.add_argument("--rules", type=Path, required=True)
    run_parser.add_argument("--retry-transport", action="store_true")
    summary_parser = commands.add_parser("summary")
    summary_parser.add_argument("--root", type=Path, required=True)
    review_parser = commands.add_parser("prepare-review")
    review_parser.add_argument("--root", type=Path, required=True)
    review_parser.add_argument("--catalog-export", type=Path, required=True)
    export_parser = commands.add_parser("export-metrics")
    export_parser.add_argument("--root", type=Path, required=True)
    export_parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "freeze":
        freeze(args.index, args.db, args.deployment_proof, args.out)
    elif args.command == "orcid":
        run_orcid(args.root, args.cohort, args.mailto, args.rules, args.retry_transport)
    elif args.command == "prepare-review":
        prepare_review(args.root, args.catalog_export)
    elif args.command == "export-metrics":
        export_metrics(args.root, args.out)
    else:
        summary(args.root)


if __name__ == "__main__":
    main()
