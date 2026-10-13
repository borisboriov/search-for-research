"""Sol-assisted контакты: явный поиск агентом, code pipeline и saved offline export.

Ни одна команда не выполняет поиск. run требует --live и отдельно разрешённый root.
"""

import argparse
import asyncio
import fcntl
import json
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from sfr_enrichment.binding import SourceHost
from sfr_enrichment.common import ensure_not_stopped, private_root, read, sha, verified_sample
from sfr_enrichment.config import RUBRIC, repository_root
from sfr_enrichment.contacts import (
    check_contact_input,
    check_quota,
    checked_source,
    contact_packet,
    digest,
    safe_url,
    verify_contact_input,
)
from sfr_enrichment.evidence import identifier, immutable_json
from sfr_enrichment.fragments import check_dates
from sfr_enrichment.native import normalized_provenance
from sfr_enrichment.replay import legacy_pdf_text
from sfr_enrichment.review import make_packet, normalize
from sfr_enrichment.semantics import prepare_control
from sfr_enrichment.sources import PublicLoader, SourceUnavailable

METHOD = "sol-assisted-contacts-v1"


def code_hashes() -> dict[str, str]:
    repo = repository_root()
    return {
        str(path.relative_to(repo)): sha(path)
        for path in sorted(Path(__file__).parent.glob("*.py"))
    } | {
        "rubric": sha(RUBRIC),
        "uv.lock": sha(repo / "uv.lock"),
        "pyproject.toml": sha(repo / "pyproject.toml"),
        "enrichment/pyproject.toml": sha(repo / "enrichment/pyproject.toml"),
    }


def validate_plan(profiles: list[dict[str, Any]], plan: dict[str, Any]) -> None:
    ids = [identifier(p["id"]) for p in profiles]
    if not 1 <= len(ids) <= 10 or len(ids) != len(set(ids)):
        raise ValueError("Нужны 1..10 уникальных профилей")
    if plan.get("schema") != METHOD or plan.get("requested_search_model") != "gpt-6.1-sol":
        raise ValueError("Нужен явный Sol-assisted plan; поиск CLI не предоставляется")
    if plan.get("requested_search_effort") != "high":
        raise ValueError("План должен фиксировать requested Sol/high")
    rows = plan.get("profiles", [])
    if len(rows) != len(ids) or {r["author_id"] for r in rows} != set(ids):
        raise ValueError("План не соответствует выборке")
    for row in rows:
        sources = row.get("sources", [])
        if not 1 <= len(sources) <= 8 or len({s["url"] for s in sources}) != len(sources):
            raise ValueError("Нужны 1..8 уникальных наблюдённых источников на профиль")
        for source in sources:
            safe_url(source["url"])
            if source["kind"] not in ("direct_http", "direct_pdf", "structured_orcid"):
                raise ValueError("Неизвестный source kind")
            if type(source.get("render_mathnet", False)) is not bool or (
                source.get("render_mathnet") and source["kind"] != "direct_http"
            ):
                raise ValueError("render_mathnet допустим только для direct_http")
            discovery = source.get("discovery", {})
            if (
                discovery.get("method") not in ("agent_search", "observed_href", "known_orcid")
                or discovery.get("observed_url") != source["url"]
                or not discovery.get("note")
                or (discovery["method"] == "agent_search" and not discovery.get("query"))
            ):
                raise ValueError(
                    "Нужен URL и явное происхождение; это запись агента, не tool receipt"
                )


def prepare(root: Path, profiles_path: Path, plan_path: Path, scope_path: Path) -> Path:
    """Фиксирует разрешение/лимиты/список URL; не запускает источники и модели."""
    root = private_root(root)
    ensure_not_stopped(root)
    profiles, plan, scope = read(profiles_path), read(plan_path), read(scope_path)
    validate_plan(profiles, plan)
    if not scope.get("authorization_reference"):
        raise ValueError("Нужна ссылка на отдельное разрешение будущего live scope")
    if type(scope.get("live_authorized")) is not bool:
        raise ValueError("Нужен явный live_authorized; для offline fixture — false")
    for key in ("deadline_acquisition", "deadline_verification"):
        deadline = datetime.fromisoformat(scope[key])
        if deadline.tzinfo is None:
            raise ValueError("Deadline должен включать timezone")
    for key, maximum in (("HTTP_total_cap", 200), ("HTTP_per_profile_cap", 30)):
        if type(scope[key]) is not int or not 1 <= scope[key] <= maximum:
            raise ValueError("Недопустимый явный HTTP cap")
    if scope.get("remaining_stop") not in (0, 5, 15) or type(scope["remaining_stop"]) is not int:
        raise ValueError("Нужен явный remaining_stop 0/5/15")
    if scope.get("disk_byte_cap") is not None and (
        type(scope["disk_byte_cap"]) is not int
        or not 1 <= scope["disk_byte_cap"] <= 512 * 1024 * 1024
    ):
        raise ValueError("Invalid explicit disk cap")
    immutable_json(root / "sample.json", profiles)
    immutable_json(root / "search-plan.json", plan)
    immutable_json(root / "scope.json", scope)
    immutable_json(root / "official-ORCID-policy.json", scope.get("ORCID_policy", {}))
    immutable_json(
        root / "manifest.json",
        {
            "method": METHOD,
            "sample_sha256": sha(root / "sample.json"),
            "plan_sha256": sha(root / "search-plan.json"),
            "scope_sha256": sha(root / "scope.json"),
            "code_sha256": code_hashes(),
            "model_job_cap": len(profiles),
            "HTTP_total_cap": scope["HTTP_total_cap"],
            "HTTP_per_profile_cap": scope["HTTP_per_profile_cap"],
            "remaining_stop": scope["remaining_stop"],
            "deadline_acquisition": scope["deadline_acquisition"],
            "deadline_verification": scope["deadline_verification"],
            "search_is_assisted": True,
            "search_plan_is_agent_supplied": True,
            "GLM_allowed": False,
            "human_reviewed": 0,
            "code_layout": "sfr-enrichment-package-v1",
            "event_storage": "native-jsonl-no-pi-session-snapshots",
            "disk_byte_cap": scope.get("disk_byte_cap"),
            "extraction_version": "literal-code-v2",
            "extraction_policy": (
                "shared flexible matcher; automatic checked literal renderer; "
                "exact cross-source dedup; no automatic attribution"
            ),
        },
    )
    return root / "manifest.json"


def frozen(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manifest = read(root / "manifest.json")
    if (
        manifest["method"] != METHOD
        or manifest["code_sha256"] != code_hashes()
        or manifest["plan_sha256"] != sha(root / "search-plan.json")
        or manifest["scope_sha256"] != sha(root / "scope.json")
        or read(root / "official-ORCID-policy.json")
        != read(root / "scope.json").get("ORCID_policy", {})
    ):
        raise ValueError("Frozen код/план/scope/policy изменён; нужен новый разрешённый root")
    profiles = verified_sample(root)
    scope = read(root / "scope.json")
    if (
        manifest["model_job_cap"] != len(profiles)
        or manifest.get("disk_byte_cap") != scope.get("disk_byte_cap")
        or any(
            manifest[key] != scope[key]
            for key in (
                "HTTP_total_cap",
                "HTTP_per_profile_cap",
                "remaining_stop",
                "deadline_acquisition",
                "deadline_verification",
            )
        )
    ):
        raise ValueError("Frozen caps/deadlines изменены")
    plan = read(root / "search-plan.json")
    validate_plan(profiles, plan)
    return profiles, plan


def progress(root: Path) -> dict[str, Any]:
    profiles = verified_sample(root)
    results = [read(p) for p in sorted((root / "results").glob("*.json"))]
    gated_results = 0
    for profile in profiles:
        aid = profile["id"]
        result_path = root / "results" / f"{aid}.json"
        gate_path = root / "date-checks" / f"{aid}.json"
        if result_path.exists() and gate_path.exists():
            input_path = Path(read(root / "prepared" / f"{aid}.json")["input_path"])
            check_result(root, input_path, result_path)
            dates = check_dates(read(root / "corpora" / f"{aid}.json"), read(result_path)["result"])
            if dates != read(gate_path):
                raise ValueError("Date gate изменён")
            gated_results += 1
    receipts = [r["receipt"] for r in results]
    usage = {
        key: (
            sum(r["tokens"][key] for r in receipts)
            if all(
                isinstance(r.get("tokens"), dict)
                and type(r["tokens"].get(key)) is int
                and r["tokens"][key] >= 0
                for r in receipts
            )
            else None
        )
        for key in ("input_tokens", "output_tokens", "cached_input_tokens")
    }
    started = list((root / "runs").glob("*/native_verifier/started.json"))
    unfinished = [
        str(p.parent.relative_to(root))
        for p in started
        if not (p.parent / "finished.json").exists() and not (p.parent / "receipt.json").exists()
    ]
    return {
        "method": METHOD,
        "profiles": len(profiles),
        "validated_results": gated_results,
        "native_outputs_saved": len(results),
        "source_reservations": len(list((root / "HTTP-ledger").glob("*-reserved.json"))),
        "native_jobs_started": len(started),
        "unknown_started_jobs_no_retry": unfinished,
        "tokens_completed_native_jobs": usage,
        "subscription_debit": None,
        "api_cost_usd": None,
        "assisted_search_usage": None,
        "development_review_usage": None,
        "human_reviewed": 0,
        "terminal_stop": any((p / "stopped.json").exists() for p in (root, *root.parents)),
        "search_implementation": "explicit_agent_step_not_available_in_this_CLI",
    }


def check_result(root: Path, input_path: Path, result_path: Path) -> None:
    source = check_contact_input(root, input_path)
    wrapper = read(result_path)
    directory = root / "runs" / source["author_id"] / "native_verifier"
    receipt = read(directory / "receipt.json")
    if (
        wrapper["input_sha256"] != sha(input_path)
        or wrapper["receipt"] != receipt
        or receipt["raw_result_sha256"] != sha(directory / "raw-result.json")
        or wrapper["result"]
        != read(directory / "raw-result.json")
        | {"provenance": normalized_provenance(receipt, "verify")}
        or read(root / "corpora" / f"{source['author_id']}.json")["fragments"]
        != source["evidence_pool"]
    ):
        raise ValueError("Result/raw/receipt/input/corpus binding изменён")
    normalize(source, wrapper)


def packet_entries(paths: list[tuple[Path, Path]]) -> list[dict[str, Any]]:
    entries = []
    for input_path, result_path in paths:
        _, result = normalize(read(input_path), read(result_path))
        selected = [
            a["claim_id"]
            for a in result["claim_assessments"]
            if a.get("eligibility", {}).get("usable_coverage")
            and a["eligibility"]["coverage_field"] == "personal_contact"
        ]
        entries.append(
            {
                "input_path": str(input_path),
                "assessment_path": str(result_path),
                "stratum": "targeted",
                "selection_reason": "Все профили данного сохранённого прохода",
                "review_claim_ids": selected,
            }
        )
    return entries


def checked_index(root: Path, index_path: Path, expected_sha: str) -> dict[str, Any]:
    if index_path.resolve().parent != root.resolve() or sha(index_path) != expected_sha:
        raise ValueError("Не совпал transfer index SHA/root")
    value = read(index_path)
    for relative, expected in value["private_file_sha256"].items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()) or sha(path) != expected:
            raise ValueError("Не совпал сохранённый evidence SHA")
    return {
        "root": str(root.resolve()),
        "index": index_path.name,
        "sha256": expected_sha,
        "checked_files": len(value["private_file_sha256"]),
    }


def saved(
    root: Path,
    baseline: Path,
    index: Path,
    index_sha: str,
    legacy_root: Path,
    legacy_index: Path,
    legacy_sha: str,
) -> Path:
    """Только read-only baseline → новый packet; старые STOP/метрики не меняются."""
    ensure_not_stopped(root)
    if any(root.resolve().is_relative_to(old.resolve()) for old in (baseline, legacy_root)):
        raise ValueError("Нужен отдельный новый root")
    reference = checked_index(baseline, index, index_sha)
    parser_reference = checked_index(legacy_root, legacy_index, legacy_sha)
    profiles = verified_sample(baseline)

    @lru_cache(maxsize=10)
    def parse_historical_pdf(raw: bytes) -> str:
        return legacy_pdf_text(legacy_root, raw)

    paths = []
    for profile in profiles:
        prepared = read(baseline / "prepared" / f"{profile['id']}.json")
        path = Path(prepared["input_path"])
        if not path.resolve().is_relative_to(baseline.resolve()) or sha(path) != prepared["sha256"]:
            raise ValueError("Изменён prepared input")
        check_contact_input(baseline, path, pdf_extractor=parse_historical_pdf)
        paths.append((path, baseline / "results" / f"{profile['id']}.json"))
    root = private_root(root)
    entries = packet_entries(paths)
    immutable_json(root / "baseline-reference.json", reference)
    immutable_json(root / "entries.json", entries)
    cards = make_packet(root, "baseline-contacts", entries, contact_review=True)
    manifest = read(cards.parent / "manifest.json")
    dates: dict[str, int] = {}
    for profile in manifest["profiles"]:
        for row in profile["assessment"]["claim_assessments"]:
            if row["claim_id"] in profile["review_claim_ids"]:
                dates[row["current_applicability"]] = dates.get(row["current_applicability"], 0) + 1
    receipts = [read(result)["receipt"] for _, result in paths]
    immutable_json(
        root / "offline-progress.json",
        {
            "profiles": len(profiles),
            "selected_contacts": sum(len(e["review_claim_ids"]) for e in entries),
            "contact_dates": dates,
            "human_reviewed": 0,
            "new_profile_model_jobs": 0,
            "new_source_calls": 0,
            "new_search_calls": 0,
            "GLM_jobs": 0,
            "baseline_native_tokens": sum(
                r["tokens"]["input_tokens"] + r["tokens"]["output_tokens"] for r in receipts
            ),
            "baseline_native_wall_seconds": sum(r["wall_elapsed_seconds"] for r in receipts),
            "baseline_search_usage": None,
            "subscription_debit": None,
            "api_cost_usd": None,
            "development_review_usage": None,
            "baseline_reference": reference,
            "baseline_sample_sha256": sha(baseline / "sample.json"),
            "historical_pdf_parser_root": str(legacy_root.resolve()),
            "historical_pdf_parser_reference": parser_reference,
        },
    )
    return cards


async def run_pipeline(
    root: Path, remaining_percent: float, author_ids: list[str] | None = None
) -> Path:
    """После нового разрешения: источники → литералы → независимый Sol → карточки."""
    ensure_not_stopped(root)
    profiles, plan = frozen(root)
    if read(root / "scope.json")["live_authorized"] is not True:
        raise ValueError("Offline scope: live source/model calls не разрешены")
    check_quota(root, remaining_percent, "assisted pipeline")
    selected = set(author_ids) if author_ids is not None else {p["id"] for p in profiles}
    if not selected or not selected <= {p["id"] for p in profiles}:
        raise ValueError("Profile selector outside frozen sample")
    paths = []
    for profile in profiles:
        aid = profile["id"]
        if aid not in selected:
            continue
        result_path = root / "results" / f"{aid}.json"
        prepared_path = root / "prepared" / f"{aid}.json"
        if prepared_path.exists():
            input_path = Path(read(prepared_path)["input_path"])
        else:
            row = next(p for p in plan["profiles"] if p["author_id"] == aid)
            directory = root / "sources" / aid
            loader = PublicLoader(directory, [s["url"] for s in row["sources"]], root, aid)
            source_paths = []
            host = SourceHost(root, profile, "live")
            for spec in row["sources"]:
                failure_path = (
                    root / "source-failures" / aid / f"{digest(spec['url'].encode())}.json"
                )
                if failure_path.exists():
                    continue
                try:
                    source = await loader.load(spec["url"], kind=spec["kind"])
                except SourceUnavailable as exc:
                    immutable_json(
                        failure_path,
                        {
                            "url": spec["url"],
                            "kind": spec["kind"],
                            "error": str(exc),
                            "retries": 0,
                            "at": datetime.now(UTC).isoformat(),
                        },
                    )
                    continue
                path = directory / f"source-{digest(source['url'].encode())}.json"
                decoded, _ = checked_source(path.parent, source)
                automatic_renderer = (
                    source["source_kind"] == "direct_http"
                    and "document.write(decode_email(" in decoded
                    and "func_string.js" in decoded
                )
                if spec.get("render_mathnet") or automatic_renderer:
                    rendered = list((root / "rendered-sources" / aid).rglob(path.name))
                    if len(rendered) > 1:
                        raise ValueError("Неоднозначный сохранённый renderer")
                    if rendered:
                        checked_source(rendered[0].parent, read(rendered[0]))
                        path = rendered[0]
                    host.allowed[spec["url"]] = 0
                    host.records[spec["url"]] = path
                    await host.render(spec["url"])
                    path = host.records[spec["url"]]
                source_paths.append(path)
            if not source_paths:
                immutable_json(
                    root / "profile-failures" / f"{aid}.json",
                    {
                        "author_id": aid,
                        "status": "no_usable_source",
                        "model_called": False,
                    },
                )
                continue
            collector = {
                "author_id": aid,
                "items": [],
                "evidence_pool": {},
                "profile_evidence": {"identity": [], "current_affiliation": []},
                "field_statuses": {},
                "provenance": {
                    "agent_id": "code:" + METHOD,
                    "collector_kind": "deterministic_contact_candidates",
                    "model_called": False,
                    "automatic_retries": 0,
                },
                "limits": {
                    "candidates_per_source": 32,
                    "literal_normalization": "whitespace_around_at_only",
                },
            }
            by_email: dict[str, dict[str, Any]] = {}
            for path in source_paths:
                part = contact_packet(
                    path.parent, profile, [read(path)], candidate_cap=32, flexible_literals=True
                )
                aliases = {
                    ref: f"E{len(collector['evidence_pool']) + i + 1:04d}"
                    for i, ref in enumerate(part["evidence_pool"])
                }
                collector["evidence_pool"].update(
                    {aliases[k]: v for k, v in part["evidence_pool"].items()}
                )
                for item in part["items"]:
                    refs = [aliases[r] for r in item["evidence_refs"]]
                    if item["value"] in by_email:
                        previous = by_email[item["value"]]
                        previous["evidence_refs"] = list(
                            dict.fromkeys(previous["evidence_refs"] + refs)
                        )
                    else:
                        merged = item | {
                            "item_id": f"contact_{len(collector['items']) + 1:03d}",
                            "evidence_refs": refs,
                        }
                        collector["items"].append(merged)
                        by_email[item["value"]] = merged
                collector["profile_evidence"]["identity"] += [
                    aliases[r] for r in part["profile_evidence"]["identity"]
                ]
            # Все static fragments вместо скрытой обрезки; E цитаты/атрибуты сохраняются.
            corpus = host.full_corpus()
            source_by_id = {s["source_id"]: s for s in corpus["sources"]}
            for fragment in corpus["fragments"].values():
                saved_source = source_by_id[fragment["source_id"]]
                fragment.update(
                    {k: saved_source[k] for k in ("source_record_path", "source_record_sha256")}
                )
                fragment["representation"] = "static_text"
            by_source = {
                (s["url"], s["body_sha256"], s["text_sha256"]): s["source_id"]
                for s in corpus["sources"]
            }
            for fragment in collector["evidence_pool"].values():
                fragment["source_id"] = by_source[
                    (fragment["url"], fragment["body_sha256"], fragment["text_sha256"])
                ]
            collector["evidence_pool"].update(corpus["fragments"])
            collector["profile_evidence"]["identity"] += list(corpus["fragments"])
            collector["limits"]["all_static_fragments_included"] = True
            collector_path = root / "normalized" / aid / "collector.json"
            immutable_json(collector_path, collector)
            input_path = prepare_control(
                root,
                profile,
                collector_path,
                collector["evidence_pool"],
                RUBRIC,
                sha(root / "sample.json"),
                namespace=METHOD,
                source_kind=METHOD,
            )
            if input_path.stat().st_size > 1_000_000:
                raise ValueError("Полный вход превышает 1MB; остановка без model/truncation")
            immutable_json(
                root / "corpora" / f"{aid}.json", corpus | {"fragments": collector["evidence_pool"]}
            )
            immutable_json(
                prepared_path, {"input_path": str(input_path), "sha256": sha(input_path)}
            )
        if sha(input_path) != read(prepared_path)["sha256"]:
            raise ValueError("Prepared input SHA изменён")
        check_contact_input(root, input_path)
        if not result_path.exists():
            deadline = datetime.fromisoformat(read(root / "manifest.json")["deadline_verification"])
            if datetime.now(UTC) >= deadline:
                raise ValueError("Verification deadline; новые jobs запрещены")
            verify_contact_input(
                root,
                input_path,
                remaining_percent=remaining_percent,
                allow_profile_evidence=True,
                deadline_epoch=deadline.timestamp(),
                prompt_byte_cap=1_000_000,
            )
        check_result(root, input_path, result_path)
        # Raw/native result не переписывается; gate обязателен до выдачи карточек.
        dates = check_dates(read(root / "corpora" / f"{aid}.json"), read(result_path)["result"])
        immutable_json(root / "date-checks" / f"{aid}.json", dates)
        paths.append((input_path, result_path))
    all_paths = []
    for profile in profiles:
        aid = profile["id"]
        result_path = root / "results" / f"{aid}.json"
        if result_path.exists():
            input_path = Path(read(root / "prepared" / f"{aid}.json")["input_path"])
            check_result(root, input_path, result_path)
            all_paths.append((input_path, result_path))
    entries = packet_entries(all_paths)
    if selected != {p["id"] for p in profiles}:
        return make_packet(
            root, "smoke-" + "-".join(sorted(selected)), entries, contact_review=True
        )
    immutable_json(root / "entries.json", entries)
    cards = make_packet(root, "assisted-contacts", entries, contact_review=True)
    immutable_json(root / "completed-progress.json", progress(root))
    return cards


async def run(root: Path, remaining_percent: float, author_ids: list[str] | None = None) -> Path:
    ensure_not_stopped(root)
    # Один процесс на root: reservations существующих компонентов не являются mutex.
    with (root / "run.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("Другой run уже пишет этот root") from exc
        try:
            return await run_pipeline(root, remaining_percent, author_ids)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("prepare", "dry-run", "status", "run", "saved"):
        item = sub.add_parser(command)
        item.add_argument("--root", type=Path, required=True)
        if command == "prepare":
            for key in ("profiles", "plan", "scope"):
                item.add_argument("--" + key, type=Path, required=True)
        if command == "run":
            item.add_argument("--live", action="store_true", required=True)
            item.add_argument("--remaining-percent", type=float, required=True)
            item.add_argument("--author-id", action="append")
        if command == "saved":
            for key in ("baseline", "index", "legacy-pdf-root", "legacy-index"):
                item.add_argument("--" + key, type=Path, required=True)
            item.add_argument("--index-sha256", required=True)
            item.add_argument("--legacy-index-sha256", required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        output: Any = str(prepare(args.root, args.profiles, args.plan, args.scope))
    elif args.command == "saved":
        output = str(
            saved(
                args.root,
                args.baseline,
                args.index,
                args.index_sha256,
                args.legacy_pdf_root,
                args.legacy_index,
                args.legacy_index_sha256,
            )
        )
    elif args.command == "run":
        output = str(asyncio.run(run(args.root, args.remaining_percent, args.author_id)))
    else:
        frozen(args.root)
        output = progress(args.root)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
