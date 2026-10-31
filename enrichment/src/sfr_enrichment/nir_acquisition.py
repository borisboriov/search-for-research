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
from sfr_enrichment.evidence import identifier, immutable_json
from sfr_enrichment.sources import PublicLoader, SourceUnavailable

SCHEMA = "nir_acquisition_only_v1"
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
        or manifest["code_sha256"] != code_hashes()
    ):
        raise ValueError("Frozen acquisition inputs/code changed")
    scope = read(root / "scope.json")
    if any(manifest.get(key) != value for key, value in scope.items()):
        raise ValueError("Frozen acquisition scope changed")
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

    async def request(
        self, client: httpx.AsyncClient, url: str, kind: str, cap: int
    ) -> dict[str, Any]:
        key = digest((kind + "\0" + url).encode())
        if not (self.root / f"request-result-{key}.json").exists():
            reserved = list(self.ledger.glob("*-reserved.json"))
            if any(
                not p.with_name(p.name.replace("-reserved", "-finished")).exists() for p in reserved
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("init", "prepare", "run"):
        item = sub.add_parser(command)
        item.add_argument("--root", type=Path, required=True)
        if command == "init":
            item.add_argument("--profiles", type=Path, required=True)
            item.add_argument("--scope", type=Path, required=True)
        else:
            item.add_argument("--batch", required=True)
        if command == "prepare":
            item.add_argument("--plan", type=Path, required=True)
        if command == "run":
            item.add_argument("--live", action="store_true", required=True)
    args = parser.parse_args()
    if args.command == "init":
        result = initialize(args.root, args.profiles, args.scope)
    elif args.command == "prepare":
        result = prepare(args.root, args.batch, args.plan)
    else:
        result = asyncio.run(run(args.root, args.batch, live=args.live))
    print(result)


if __name__ == "__main__":
    main()
