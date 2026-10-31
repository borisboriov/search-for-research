"""Bounded NIR source acquisition only: no attribution/model transport or human labels.

One private campaign owns the frozen person queue, budgets and HTTP ledger. Batches
contain at most ten consecutive people; an attempted batch cannot be submitted again.
"""

import argparse
import asyncio
import fcntl
import json
import re
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from sfr_enrichment.binding import SourceHost
from sfr_enrichment.common import (
    check_storage_budget,
    ensure_not_stopped,
    now,
    private_root,
    read,
    sha,
)
from sfr_enrichment.config import repository_root
from sfr_enrichment.contacts import checked_source, contact_packet, digest, safe_url
from sfr_enrichment.evidence import identifier, immutable_bytes, immutable_json
from sfr_enrichment.sources import PublicLoader, SourceUnavailable

SCHEMA = "nir_acquisition_only_v1"
RECOVERY_SCHEMA = "nir_ssl_abort_recovery_v1"
REVISION = "revisions/ssl-abort-01"
RECOVERY_FILES = {"nir_acquisition.py", "sources.py"}
MAXIMA = {
    "profile_total_cap": 60,
    "HTTP_total_cap": 600,
    "HTTP_batch_cap": 100,
    "HTTP_per_profile_cap": 15,
    "disk_byte_cap": 512 * 1024 * 1024,
    "sources_per_profile_cap": 3,
    "search_queries_per_profile_cap": 3,
}


def code_hashes() -> dict[str, str]:
    directory = Path(__file__).parent
    names = (
        "nir_acquisition",
        "sources",
        "contacts",
        "common",
        "evidence",
        "binding",
        "fragments",
        "http_policy",
        "config",
    )
    return {name + ".py": sha(directory / (name + ".py")) for name in names} | {
        "uv.lock": sha(repository_root() / "uv.lock")
    }


def save(root: Path, path: Path, value: Any, *, reserve: int = 65536) -> None:
    size = len((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())
    check_storage_budget(root, (0 if path.exists() else size) + reserve)
    immutable_json(path, value)


@contextmanager
def writer(root: Path) -> Iterator[None]:
    with (root / "acquisition.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("Campaign writer is already active") from exc
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def initialize(root: Path, profiles_path: Path, scope_path: Path) -> Path:
    profiles, scope = read(profiles_path), read(scope_path)
    for key, maximum in MAXIMA.items():
        if type(scope.get(key)) is not int or not 1 <= scope[key] <= maximum:
            raise ValueError("Invalid acquisition cap: " + key)
    if type(scope.get("model_job_cap")) is not int or scope["model_job_cap"] != 0:
        raise ValueError("Acquisition-only requires zero model jobs")
    if type(scope.get("live_authorized")) is not bool or not scope.get("authorization_reference"):
        raise ValueError("Explicit acquisition authorization is required")
    deadline = datetime.fromisoformat(scope["deadline_acquisition"])
    if deadline.tzinfo is None:
        raise ValueError("Acquisition deadline needs timezone")
    if not isinstance(profiles, list) or not 1 <= len(profiles) <= scope["profile_total_cap"]:
        raise ValueError("Invalid frozen person queue")
    ids = [identifier(p["id"]) for p in profiles]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate person IDs in queue")
    root = private_root(root)
    ensure_not_stopped(root)
    with writer(root):
        if (root / "manifest.json").exists():
            raise ValueError("Campaign already initialized; use a new root")
        immutable_json(root / "profiles.json", profiles)
        immutable_json(root / "scope.json", scope)
        immutable_json(
            root / "manifest.json",
            scope
            | {
                "schema": SCHEMA,
                "profiles_sha256": sha(root / "profiles.json"),
                "scope_sha256": sha(root / "scope.json"),
                "code_sha256": code_hashes(),
                "rate_limit_rps": 1,
                "model_jobs": 0,
                "extractor": "literal-code-v2-static-no-javascript-renderer",
            },
        )
        check_storage_budget(root, 65536)
    return root / "manifest.json"


def checked(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ensure_not_stopped(root)
    if any(path.is_symlink() for path in root.rglob("*")):
        raise ValueError("Campaign must not contain symlinks")
    manifest = read(root / "manifest.json")
    if manifest.get("schema") != SCHEMA or manifest.get("model_jobs") != 0:
        raise ValueError("Not an acquisition-only campaign")
    if (
        sha(root / "profiles.json") != manifest["profiles_sha256"]
        or sha(root / "scope.json") != manifest["scope_sha256"]
    ):
        raise ValueError("Frozen acquisition inputs/code changed")
    scope = read(root / "scope.json")
    if any(manifest.get(key) != value for key, value in scope.items()):
        raise ValueError("Frozen acquisition scope changed")
    if (root / REVISION).exists():
        validate_recovery(root)
    elif manifest["code_sha256"] != code_hashes():
        raise ValueError("Frozen acquisition inputs/code changed")
    return list(read(root / "profiles.json")), manifest


def batch_directory(root: Path, name: str) -> Path:
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", name):
        raise ValueError("Invalid batch name")
    return root / "batches" / name


def batches(root: Path) -> list[tuple[Path, dict[str, Any]]]:
    found = []
    for path in (root / "batches").glob("*/manifest.json"):
        item = read(path)
        if sha(path.parent / "plan.json") != item["plan_sha256"]:
            raise ValueError("Frozen batch plan changed")
        found.append((path.parent, item))
    ordered = sorted(found, key=lambda entry: entry[1]["start_index"])
    profiles = read(root / "profiles.json")
    expected_start = 0
    for directory, item in ordered:
        rows = read(directory / "plan.json")["profiles"]
        if (
            item["start_index"] != expected_start
            or not 1 <= len(rows) <= 10
            or item["people"] != len(rows)
            or item["campaign_manifest_sha256"] != sha(root / "manifest.json")
            or [r["author_id"] for r in rows]
            != [p["id"] for p in profiles[expected_start : expected_start + len(rows)]]
        ):
            raise ValueError("Frozen batch sequence changed")
        expected_start += len(rows)
    return ordered


def preserved_snapshot(root: Path) -> dict[str, str]:
    """Exact pre-recovery snapshot; the writer's empty lock is not evidence."""
    return {
        str(path.relative_to(root)): sha(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path != root / "acquisition.lock"
    }


def validate_recovery_decision(root: Path, decision: dict[str, Any], *, initial: bool) -> None:
    """One reviewed SSL-abort revision, not a generic bypass for code or unknown jobs."""
    ensure_not_stopped(root)
    if any(path.is_symlink() for path in root.rglob("*")):
        raise ValueError("Campaign must not contain symlinks")
    if decision.get("schema") != RECOVERY_SCHEMA or any(
        not isinstance(decision.get(key), str) or not decision[key].strip()
        for key in ("authorization_reference", "independent_review_reference")
    ):
        raise ValueError("Recovery requires explicit authorization and independent review")
    manifest = read(root / "manifest.json")
    scope = read(root / "scope.json")
    if (
        decision["campaign_manifest_sha256"] != sha(root / "manifest.json")
        or manifest["profiles_sha256"] != sha(root / "profiles.json")
        or manifest["scope_sha256"] != sha(root / "scope.json")
        or any(manifest.get(key) != value for key, value in scope.items())
        or scope.get("model_job_cap") != 0
    ):
        raise ValueError("Recovery cannot change campaign inputs or budgets")
    old, new = decision["original_code_sha256"], decision["replacement_code_sha256"]
    if (
        old != manifest["code_sha256"]
        or new != code_hashes()
        or set(old) != set(new)
        or {key for key in old if old[key] != new[key]} != RECOVERY_FILES
    ):
        raise ValueError("Recovery allows only the reviewed SSL/acquisition runtime revision")
    preserved = decision["preserved_files_sha256"]
    if not isinstance(preserved, dict) or not preserved:
        raise ValueError("Recovery requires a complete prior evidence snapshot")
    for name, expected in preserved.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()) or sha(path) != expected:
            raise ValueError("Preserved recovery evidence changed")
    if initial and preserved != preserved_snapshot(root):
        raise ValueError("Recovery snapshot must cover every existing campaign artifact")
    directory = batch_directory(root, decision["batch"])
    item = read(directory / "manifest.json")
    ordered = batches(root)
    if any(
        not (p / "result.json").exists()
        for p, m in ordered
        if m["start_index"] < item["start_index"]
    ):
        raise ValueError("Earlier batches must be complete before recovery")
    if initial and any(
        (p / "started.json").exists() for p, m in ordered if m["start_index"] > item["start_index"]
    ):
        raise ValueError("Later batches already attempted")
    failure = read(directory / "failure.json")
    if failure.get("error_type") != "SSLError" or failure.get("retry_allowed") is not False:
        raise ValueError("Only the recorded SSL transport abort is recoverable")
    rows = read(directory / "plan.json")["profiles"]
    aborted = decision["aborted_author_id"]
    positions = [i for i, row in enumerate(rows) if row["author_id"] == aborted]
    if len(positions) != 1:
        raise ValueError("Aborted person is outside the frozen batch")
    offset = positions[0]
    if (
        decision["aborted_queue_index"] != item["start_index"] + offset
        or decision["resume_author_ids"] != [row["author_id"] for row in rows[offset + 1 :]]
        or not decision["resume_author_ids"]
    ):
        raise ValueError("Recovery must continue only the exact unattempted tail")
    required = {"manifest.json", "scope.json", "profiles.json"}
    prefix = str(directory.relative_to(root))
    required.update(
        prefix + "/" + name
        for name in ("manifest.json", "plan.json", "started.json", "failure.json", "console.log")
    )
    for row in rows[:offset]:
        for name in ("result.json", "collector.json", "corpus.json"):
            required.add(f"{prefix}/people/{row['author_id']}/{name}")
        if read(directory / "people" / row["author_id"] / "result.json").get("status") not in (
            "candidates",
            "no_candidate",
            "no_usable_source",
        ):
            raise ValueError("Recovery prefix is not an existing completed result")
    ticket = decision["reserved_ticket"]
    if not isinstance(ticket, str) or not re.fullmatch(r"\d{4}", ticket):
        raise ValueError("Invalid exact recovery ticket")
    reservation = f"HTTP-ledger/{ticket}-reserved.json"
    local_ticket = f"{prefix}/sources/{aborted}/requests/{ticket}.json"
    required.update((reservation, local_ticket))
    if not required <= set(preserved):
        raise ValueError("Recovery snapshot lacks required bindings")
    reserved = read(root / reservation)
    if reserved["author_id"] != aborted or read(root / local_ticket) != reserved:
        raise ValueError("Recovery ticket does not belong to the aborted person")
    if (root / "HTTP-ledger" / f"{ticket}-finished.json").exists():
        raise ValueError("Unknown outcome must not be converted to a finished receipt")
    reserved_before = {p for p in preserved if re.fullmatch(r"HTTP-ledger/\d{4}-reserved.json", p)}
    finished_before = {p for p in preserved if re.fullmatch(r"HTTP-ledger/\d{4}-finished.json", p)}
    missing = {
        p for p in reserved_before if p.replace("-reserved", "-finished") not in finished_before
    }
    if (
        missing != {reservation}
        or len(reserved_before) != decision["reserved_requests_before"]
        or len(finished_before) != decision["finished_requests_before"]
    ):
        raise ValueError("Only one exact unknown HTTP outcome can be retired")
    if initial:
        if (root / REVISION).exists() or (directory / "result.json").exists():
            raise ValueError("Recovery revision already exists or batch has completed")
        for row in rows[offset:]:
            if (directory / "people" / row["author_id"]).exists():
                raise ValueError("Aborted/tail person already has results")
        if any(
            read(root / p)["author_id"] in decision["resume_author_ids"] for p in reserved_before
        ):
            raise ValueError("Recovery tail has already consumed HTTP attempts")
        originals = decision["original_runtime_files"]
        if set(originals) != RECOVERY_FILES or any(
            sha(Path(originals[k])) != old[k] for k in originals
        ):
            raise ValueError("Original runtime snapshots are required")


def retirement_record(decision: dict[str, Any], decision_sha: str, at: str) -> dict[str, Any]:
    ticket = decision["reserved_ticket"]
    return {
        "schema": "nir_http_retirement_v1",
        "ticket": ticket,
        "reserved_sha256": decision["preserved_files_sha256"][
            f"HTTP-ledger/{ticket}-reserved.json"
        ],
        "author_id": decision["aborted_author_id"],
        "outcome": "unknown_transport_outcome",
        "HTTP_started": None,
        "evidence_usable": False,
        "budget_consumed": True,
        "retry_allowed": False,
        "decision_sha256": decision_sha,
        "revision_path": REVISION,
        "retired_at": at,
    }


def abort_result(decision: dict[str, Any], retirement_sha: str) -> dict[str, Any]:
    return {
        "author_id": decision["aborted_author_id"],
        "model_jobs": 0,
        "status": "technical_abort",
        "candidates": None,
        "usable_sources": None,
        "source_failures": None,
        "reason": "ssl_transport_outcome_unknown_no_retry",
        "retirement_path": f"HTTP-ledger/{decision['reserved_ticket']}-retired.json",
        "retirement_sha256": retirement_sha,
    }


def register_ssl_abort(root: Path, decision_path: Path) -> Path:
    """Offline only: seal a reviewed revision and discard the unknown attempt."""
    root = root.resolve()
    with writer(root):
        decision = read(decision_path)
        validate_recovery_decision(root, decision, initial=True)
        revision = root / REVISION
        check_storage_budget(root, decision_path.stat().st_size + 1024 * 1024)
        immutable_bytes(revision / "decision.json", decision_path.read_bytes())
        for name in RECOVERY_FILES:
            immutable_bytes(
                revision / "original-code" / name,
                Path(decision["original_runtime_files"][name]).read_bytes(),
            )
            immutable_bytes(
                revision / "replacement-code" / name, (Path(__file__).parent / name).read_bytes()
            )
        at, decision_sha = now(), sha(revision / "decision.json")
        retired = root / "HTTP-ledger" / f"{decision['reserved_ticket']}-retired.json"
        save(root, retired, retirement_record(decision, decision_sha, at))
        save(
            root,
            batch_directory(root, decision["batch"])
            / "people"
            / decision["aborted_author_id"]
            / "result.json",
            abort_result(decision, sha(retired)),
        )
        save(
            root,
            revision / "manifest.json",
            {
                "schema": "nir_acquisition_revision_v1",
                "registered_at": at,
                "predecessor_manifest_sha256": decision["campaign_manifest_sha256"],
                "decision_sha256": decision_sha,
                "retirement_sha256": sha(retired),
            },
        )
        validate_recovery(root)
    return revision / "manifest.json"


def validate_recovery(root: Path) -> dict[str, Any]:
    """Read-only binding check; safe for the acquisition→selection compiler."""
    revision = root / REVISION
    record, decision = read(revision / "manifest.json"), read(revision / "decision.json")
    if (
        record.get("schema") != "nir_acquisition_revision_v1"
        or record["decision_sha256"] != sha(revision / "decision.json")
        or record["predecessor_manifest_sha256"] != sha(root / "manifest.json")
    ):
        raise ValueError("Recovery revision binding changed")
    validate_recovery_decision(root, decision, initial=False)
    for kind, hashes in (
        ("original-code", decision["original_code_sha256"]),
        ("replacement-code", decision["replacement_code_sha256"]),
    ):
        if any(sha(revision / kind / name) != hashes[name] for name in RECOVERY_FILES):
            raise ValueError("Recovery runtime snapshot changed")
    retired = root / "HTTP-ledger" / f"{decision['reserved_ticket']}-retired.json"
    if sha(retired) != record["retirement_sha256"] or read(retired) != retirement_record(
        decision, record["decision_sha256"], record["registered_at"]
    ):
        raise ValueError("Retired outcome binding changed")
    result = (
        batch_directory(root, decision["batch"])
        / "people"
        / decision["aborted_author_id"]
        / "result.json"
    )
    if read(result) != abort_result(decision, sha(retired)):
        raise ValueError("Technical-abort result changed")
    return dict(decision)


def prepare(root: Path, name: str, plan_path: Path) -> Path:
    root = root.resolve()
    directory = batch_directory(root, name)
    with writer(root):
        profiles, manifest = checked(root)
        if directory.exists():
            raise ValueError("Batch already prepared; no resubmission")
        previous = batches(root)
        start = sum(row["people"] for _, row in previous)
        rows = read(plan_path)["profiles"]
        if not isinstance(rows, list) or not 1 <= len(rows) <= 10:
            raise ValueError("A batch must contain 1–10 people")
        if [r["author_id"] for r in rows] != [p["id"] for p in profiles[start : start + len(rows)]]:
            raise ValueError("Batch must follow frozen queue without replacement")
        for row in rows:
            queries, sources = row["search_queries"], row["sources"]
            if (
                not isinstance(queries, list)
                or len(queries) > manifest["search_queries_per_profile_cap"]
                or any(not isinstance(q, str) or not q.strip() for q in queries)
                or len(set(queries)) != len(queries)
            ):
                raise ValueError("Invalid frozen search queries")
            if not isinstance(sources, list) or len(sources) > manifest["sources_per_profile_cap"]:
                raise ValueError("Invalid source count")
            urls = []
            for source in sources:
                url, discovery = source["url"], source["discovery"]
                safe_url(url)
                if (
                    source["kind"] not in ("direct_http", "direct_pdf")
                    or discovery.get("observed_url") != url
                    or discovery.get("method") not in ("agent_search", "observed_href")
                    or not str(discovery.get("note", "")).strip()
                ):
                    raise ValueError("Observed public HTML/PDF provenance required")
                if discovery["method"] == "agent_search" and discovery.get("query") not in queries:
                    raise ValueError("Source query is outside frozen discovery log")
                urls.append(url)
            if len(set(urls)) != len(urls):
                raise ValueError("Duplicate source URL")
        save(root, directory / "plan.json", {"profiles": rows})
        save(
            root,
            directory / "manifest.json",
            {
                "schema": SCHEMA,
                "start_index": start,
                "people": len(rows),
                "plan_sha256": sha(directory / "plan.json"),
                "campaign_manifest_sha256": sha(root / "manifest.json"),
            },
        )
    return directory / "manifest.json"


class CampaignLoader(PublicLoader):
    """Reuse source acquisition with one campaign ledger and an extra batch cap."""

    def __init__(
        self, root: Path, urls: list[str], campaign: Path, author_id: str, batch_ids: set[str]
    ) -> None:
        super().__init__(root, urls, campaign, author_id)
        self.batch_ids = batch_ids
        self.retired_tickets = set()
        if (campaign / REVISION).exists():
            self.retired_tickets.add(validate_recovery(campaign)["reserved_ticket"])

    async def request(
        self, client: httpx.AsyncClient, url: str, kind: str, cap: int
    ) -> dict[str, Any]:
        key = digest((kind + "\0" + url).encode())
        if not (self.root / f"request-result-{key}.json").exists():
            reserved = list(self.ledger.glob("*-reserved.json"))
            if any(
                not p.with_name(p.name.replace("-reserved", "-finished")).exists()
                and p.name.split("-")[0] not in self.retired_tickets
                for p in reserved
            ):
                raise ValueError("Unfinished HTTP attempt: no retry or new requests")
            count = sum(read(p)["author_id"] in self.batch_ids for p in reserved)
            if count >= self.manifest["HTTP_batch_cap"]:
                raise ValueError("Frozen batch HTTP budget")
            finished = [read(p)["finished_timestamp"] for p in self.ledger.glob("*-finished.json")]
            if finished:
                await asyncio.sleep(max(0.0, 1.0 - (time.time() - max(finished))))
        return await super().request(client, url, kind, cap)


async def collect_person(
    root: Path, directory: Path, profile: dict[str, Any], plan: dict[str, Any], batch_ids: set[str]
) -> dict[str, Any]:
    aid = profile["id"]
    source_root = directory / "sources" / aid
    loader = CampaignLoader(source_root, [s["url"] for s in plan["sources"]], root, aid, batch_ids)
    source_paths = []
    failures = []
    for spec in plan["sources"]:
        try:
            source = await loader.load(spec["url"], kind=spec["kind"])
        except SourceUnavailable as exc:
            failure = {
                "url": spec["url"],
                "error": str(exc),
                "scope": exc.scope,
                "receipt_path": exc.receipt_path,
                "at": now(),
                "retries": 0,
            }
            save(
                root,
                directory / "failures" / aid / (digest(spec["url"].encode()) + ".json"),
                failure,
            )
            failures.append(failure)
            continue
        path = source_root / ("source-" + digest(source["url"].encode()) + ".json")
        checked_source(path.parent, source)
        if path not in source_paths:
            source_paths.append(path)
    candidates: dict[str, dict[str, Any]] = {}
    pool: dict[str, Any] = {}
    for path in source_paths:
        part = contact_packet(
            path.parent, profile, [read(path)], candidate_cap=32, flexible_literals=True
        )
        refs = {ref: f"E{len(pool) + i + 1:04d}" for i, ref in enumerate(part["evidence_pool"])}
        pool.update({refs[ref]: value for ref, value in part["evidence_pool"].items()})
        for item in part["items"]:
            candidate = candidates.setdefault(item["value"], {"email": item["value"], "refs": []})
            candidate["refs"] = list(
                dict.fromkeys(candidate["refs"] + [refs[r] for r in item["evidence_refs"]])
            )
    corpus = SourceHost(directory, profile, "live").full_corpus()
    save(root, directory / "people" / aid / "corpus.json", corpus)
    save(
        root,
        directory / "people" / aid / "collector.json",
        {
            "author_id": aid,
            "candidates": list(candidates.values()),
            "evidence_pool": pool,
            "model_jobs": 0,
            "candidate_cap_per_source": 32,
            "normalization": "literal-code-v2-whitespace-around-at-only",
            "javascript_rendered": False,
        },
    )
    result = {
        "author_id": aid,
        "model_jobs": 0,
        "usable_sources": len(source_paths),
        "source_failures": len(failures),
        "candidates": len(candidates),
        "status": "candidates"
        if candidates
        else ("no_candidate" if source_paths else "no_usable_source"),
    }
    save(root, directory / "people" / aid / "result.json", result)
    return result


async def run(root: Path, name: str, *, live: bool = False) -> Path:
    root = root.resolve()
    directory = batch_directory(root, name)
    with writer(root):
        profiles, manifest = checked(root)
        if not live or manifest["live_authorized"] is not True:
            raise ValueError("Explicit --live acquisition authorization required")
        if datetime.now(UTC) >= datetime.fromisoformat(manifest["deadline_acquisition"]):
            raise ValueError("Acquisition deadline")
        previous = batches(root)
        item = next((row for path, row in previous if path == directory), None)
        if item is None or item["campaign_manifest_sha256"] != sha(root / "manifest.json"):
            raise ValueError("Unknown or changed batch campaign")
        if any(
            not (path / "result.json").exists()
            for path, row in previous
            if row["start_index"] < item["start_index"]
        ):
            raise ValueError("Previous batch has not completed")
        if (directory / "started.json").exists():
            raise ValueError("Batch already attempted; no resubmission")
        save(root, directory / "started.json", {"at": now(), "model_jobs": 0})
        try:
            plan = read(directory / "plan.json")["profiles"]
            batch_ids = {p["author_id"] for p in plan}
            results = []
            for profile, row in zip(profiles[item["start_index"] :], plan, strict=False):
                results.append(await collect_person(root, directory, profile, row, batch_ids))
            save(root, directory / "result.json", {"people": results, "model_jobs": 0})
        except Exception as exc:
            save(
                root,
                directory / "failure.json",
                {
                    "at": now(),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "model_jobs": 0,
                    "retry_allowed": False,
                },
                reserve=0,
            )
            raise
    return directory / "result.json"


async def continue_ssl_abort(root: Path, *, live: bool = False) -> Path:
    """One new attempt for the exact tail; never retry the aborted person/request."""
    root = root.resolve()
    with writer(root):
        profiles, manifest = checked(root)
        decision = validate_recovery(root)
        if not live or manifest["live_authorized"] is not True:
            raise ValueError("Explicit --live acquisition authorization required")
        if datetime.now(UTC) >= datetime.fromisoformat(manifest["deadline_acquisition"]):
            raise ValueError("Acquisition deadline")
        directory = batch_directory(root, decision["batch"])
        attempt = root / REVISION / "continuation"
        if (attempt / "started.json").exists() or (directory / "result.json").exists():
            raise ValueError("Continuation already attempted; no resubmission")
        rows = read(directory / "plan.json")["profiles"]
        by_id = {p["id"]: p for p in profiles}
        batch_ids = {row["author_id"] for row in rows}
        save(
            root,
            attempt / "started.json",
            {
                "at": now(),
                "decision_sha256": sha(root / REVISION / "decision.json"),
                "author_ids": decision["resume_author_ids"],
                "model_jobs": 0,
            },
        )
        try:
            for row in rows:
                if row["author_id"] in decision["resume_author_ids"]:
                    await collect_person(root, directory, by_id[row["author_id"]], row, batch_ids)
            results = [
                read(directory / "people" / row["author_id"] / "result.json") for row in rows
            ]
            save(
                root,
                directory / "result.json",
                {
                    "people": results,
                    "model_jobs": 0,
                    "technical_aborts": 1,
                    "continuation_decision_sha256": sha(root / REVISION / "decision.json"),
                },
            )
            save(
                root,
                attempt / "finished.json",
                {
                    "at": now(),
                    "batch_result_sha256": sha(directory / "result.json"),
                    "model_jobs": 0,
                },
            )
        except Exception as exc:
            save(
                root,
                attempt / "failure.json",
                {
                    "at": now(),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "retry_allowed": False,
                    "model_jobs": 0,
                },
                reserve=0,
            )
            raise
    return directory / "result.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("init", "prepare", "run", "register-ssl-abort", "continue-ssl-abort"):
        item = sub.add_parser(command)
        item.add_argument("--root", type=Path, required=True)
        if command == "init":
            item.add_argument("--profiles", type=Path, required=True)
            item.add_argument("--scope", type=Path, required=True)
        elif command in ("prepare", "run"):
            item.add_argument("--batch", required=True)
        elif command == "register-ssl-abort":
            item.add_argument("--decision", type=Path, required=True)
        if command == "prepare":
            item.add_argument("--plan", type=Path, required=True)
        if command in ("run", "continue-ssl-abort"):
            item.add_argument("--live", action="store_true", required=True)
    args = parser.parse_args()
    if args.command == "init":
        result = initialize(args.root, args.profiles, args.scope)
    elif args.command == "prepare":
        result = prepare(args.root, args.batch, args.plan)
    elif args.command == "register-ssl-abort":
        result = register_ssl_abort(args.root, args.decision)
    elif args.command == "continue-ssl-abort":
        result = asyncio.run(continue_ssl_abort(args.root, live=args.live))
    else:
        result = asyncio.run(run(args.root, args.batch, live=args.live))
    print(result)


if __name__ == "__main__":
    main()
