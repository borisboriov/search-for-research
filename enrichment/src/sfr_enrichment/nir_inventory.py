"""Bounded metadata-only reconstruction of earlier enrichment exposure; never acquire sources."""

import argparse
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from sfr_enrichment.common import sha, write_new

SCHEMA = "nir_prior_inventory_v1"
PLAN_SCHEMA = "nir_prior_inventory_plan_v1"
HASH = re.compile(r"^[0-9a-f]{64}$")
OA = re.compile(r"^(?:https?://openalex\.org/)?(A[0-9]+)/*$", re.I)
ORCID = re.compile(
    r"^(?:https?://orcid\.org/)?([0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{3}[0-9X])/*$", re.I
)
EMAIL = re.compile(r"[^\s<>@,;]+\s*@\s*[^\s<>@,;]+\.[^\s<>@,;]+")
PRUNE = {".git", ".venv", "node_modules", "__pycache__", ".cache"}
SKIP_PARTS = {"raw", "cache", "orcid", "pi-events", "session-events", "snapshots", "events"}
META_NAMES = {
    "sample.json",
    "profiles.json",
    "selection.json",
    "selection-freeze.json",
    "collector.json",
    "contacts.json",
    "plan.json",
    "search-plan.json",
    "artifact-manifest.json",
    "answers.json",
    "answers-read-snapshot.json",
    "import-provenance.json",
}
IDENTITY_LIST_KEYS = {
    "selected_ids",
    "pilot_ids",
    "evaluation_ids",
    "author_ids",
    "known_excluded_ids",
}
TEXT_SKIP_KEYS = {
    "text",
    "body",
    "content",
    "raw",
    "excerpt",
    "quote",
    "profile_text",
    "display_text",
    "indexed_text",
    "prompt",
    "raw_response",
}


def canonical_identifier(value: str) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if value.startswith("openalex:"):
        value = value[9:]
    elif value.startswith("orcid:"):
        value = value[6:]
    if match := OA.fullmatch(value):
        return "openalex:" + match[1].upper()
    if match := ORCID.fullmatch(value):
        return "orcid:" + match[1].upper()
    return None


def canonical_email(value: str) -> str:
    return re.sub(r"\s*@\s*", "@", value.strip())


def canonical_pair_key(identity: str, email: str, *, casefold: bool = False) -> str:
    address = canonical_email(email)
    if casefold:
        address = address.casefold()
    return hashlib.sha256((identity + "\n" + address).encode()).hexdigest()


def canonical_document_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value.strip())
        if (
            parsed.scheme.lower() not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or any(
                key.casefold()
                in {
                    "token",
                    "access_token",
                    "api_key",
                    "apikey",
                    "authorization",
                    "auth",
                    "password",
                    "signature",
                    "sig",
                    "x-amz-credential",
                    "x-amz-signature",
                }
                for key, _ in parse_qsl(parsed.query)
            )
        ):
            return None
        return urlunsplit(
            (parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, parsed.query, "")
        )
    except ValueError:
        return None


def candidate_identity_keys(profile: dict[str, Any], group_id: str) -> list[str]:
    values: list[str] = [group_id]

    def collect(value: Any) -> None:
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, dict):
            for nested in value.values():
                collect(nested)
        elif isinstance(value, list):
            for nested in value:
                collect(nested)

    for key in ("id", "author_id", "openalex_id", "orcid", "identifiers", "aliases"):
        collect(profile.get(key))
    return sorted({identity for value in values if (identity := canonical_identifier(value))})


def overlap_reasons(inventory: dict[str, Any], projection: dict[str, Any]) -> list[str]:
    lookup = inventory["lookup"]
    keys = projection.get("identity_keys", [])
    reasons = []
    if set(keys) & set(lookup["identity_keys"]):
        reasons.append("researcher_alias_overlap")
    known_people = {p for key in keys for p in lookup["identity_to_people"].get(key, [])}
    if len(known_people) > 1:
        reasons.append("identity_alias_conflict")
    for key in keys:
        if canonical_pair_key(key, projection["email"]) in lookup["pair_keys"]:
            reasons.append("researcher_email_pair_overlap")
        elif (
            canonical_pair_key(key, projection["email"], casefold=True)
            in lookup["casefold_pair_keys"]
        ):
            reasons.append("conservative_email_casefold_collision")
    for representation, hashes in lookup["document_sha256"].items():
        if set(projection.get("snapshot_sha256", [])) & set(hashes):
            reasons.append("document_bytes_overlap:" + representation)
    if set(projection.get("excerpt_sha256", [])) & set(
        lookup["document_sha256"].get("excerpt", [])
    ):
        reasons.append("evidence_excerpt_overlap:excerpt")
    urls = {
        u for value in projection.get("source_urls", []) if (u := canonical_document_url(value))
    }
    if urls & set(lookup["document_urls"]):
        reasons.append("document_url_overlap")
    if set(projection.get("example_keys", [])) & set(lookup["example_keys"]):
        reasons.append("scoped_example_overlap")
    return sorted(set(reasons))


def make_lookup(
    people: list[dict[str, Any]],
    pairs: list[dict[str, Any]],
    documents: list[dict[str, Any]],
    examples: list[dict[str, Any]],
) -> dict[str, Any]:
    identity_to_people: dict[str, set[str]] = defaultdict(set)
    for person in people:
        for key in person["identity_keys"]:
            identity_to_people[key].add(person["person_key"])
    pair_keys, folded = set(), set()
    people_by_key = {p["person_key"]: p for p in people}
    for pair in pairs:
        for key in people_by_key[pair["person_key"]]["identity_keys"]:
            pair_keys.add(canonical_pair_key(key, pair["email"]))
            folded.add(canonical_pair_key(key, pair["email"], casefold=True))
    hashes: dict[str, set[str]] = defaultdict(set)
    urls = set()
    for doc in documents:
        if doc.get("sha256"):
            hashes[doc["representation"]].add(doc["sha256"])
        if doc.get("url"):
            urls.add(doc["url"])
    return {
        "identity_keys": sorted(identity_to_people),
        "identity_to_people": {k: sorted(v) for k, v in sorted(identity_to_people.items())},
        "pair_keys": sorted(pair_keys),
        "casefold_pair_keys": sorted(folded),
        "document_sha256": {k: sorted(v) for k, v in sorted(hashes.items())},
        "document_urls": sorted(urls),
        "example_keys": sorted({x["example_key"] for x in examples}),
    }


def metadata_kind(path: Path, root: Path) -> str | None:
    relative = path.relative_to(root)
    lower = str(relative).lower()
    if path.suffix != ".json" or any(part in SKIP_PARTS for part in relative.parts):
        return None
    if path.name.endswith("-mcp-request.json"):
        return "source_request_metadata"
    if path.name.endswith("-http.json"):
        return "transport_metadata"
    if any(
        token in lower
        for token in (
            "session-event",
            "native_verifier/",
            "pi_verifier/",
            "pi_collector/",
            "/native/",
        )
    ):
        return None
    if path.name.startswith(("transfer-SHA-index", "preclosure-SHA-index", "final-transfer-seal")):
        return "transfer_index"
    if path.name in {"prior-roots-before.json", "exploration-render.json"}:
        return "operational_metadata"
    if path.name in {
        "source-observations.private.json",
        "html-response.json",
        "robots-response.json",
    }:
        return "source_metadata"
    if path.name in META_NAMES or path.name.startswith("manifest"):
        return "case_metadata"
    if path.name.startswith(("source-", "request-result-")) or "source-snapshots" in lower:
        return "source_metadata"
    if any(
        part in {"inputs", "outputs", "collector-sources", "verifier-sources", "records"}
        for part in relative.parts
    ):
        return "case_metadata"
    if len(relative.parts) == 1:
        return "root_metadata"
    return None


def declared_cohorts(data: Any, filename: str) -> list[dict[str, Any]]:
    """Read independently declared selected cohorts, not arbitrary frame/person mentions."""
    cohorts = []
    if filename in {"sample.json", "profiles.json", "selection.json"} and isinstance(data, list):
        cohorts.append({"selector": "$", "rows": data})
    if isinstance(data, dict):
        for key in ("pilot_ids", "evaluation_ids", "selected_ids", "profiles"):
            if isinstance(data.get(key), list):
                cohorts.append({"selector": "$." + key, "rows": data[key]})
        if filename in {"contacts_sfr5.json", "contacts_manual_sfr5.json"}:
            for key in ("raw", "manual_sample", "rows"):
                if isinstance(data.get(key), list):
                    cohorts.append({"selector": "$." + key, "rows": data[key]})
    result = []
    for cohort in cohorts:
        keys = set()
        unmapped = []
        for index, row in enumerate(cohort["rows"]):
            candidates = (
                candidate_identity_keys(row, str(row.get("author_id", "")))
                if isinstance(row, dict)
                else [canonical_identifier(row)]
                if isinstance(row, str)
                else []
            )
            known = [key for key in candidates if key]
            keys.update(known)
            if not known:
                unmapped.append(index)
        result.append(
            {
                "selector": cohort["selector"],
                "identity_keys": sorted(keys),
                "row_count": len(cohort["rows"]),
                "unmapped_rows": unmapped,
            }
        )
    return result


def decode_metadata(payload: bytes) -> tuple[Any, str]:
    """Accept one historical transport's literal terminal newline, never repair JSON values."""
    try:
        return json.loads(payload), "json"
    except json.JSONDecodeError:
        text = payload.decode("utf-8")
        value, end = json.JSONDecoder().raw_decode(text)
        if text[end:].strip() not in {r"\n", r"\r\n"}:
            raise ValueError("Metadata is not one complete JSON value") from None
        return value, "complete_json_with_literal_terminal_newline"


class Accumulator:
    def __init__(self) -> None:
        self.people: dict[str, dict[str, Any]] = {}
        self.pairs: dict[tuple[str, str], dict[str, Any]] = {}
        self.documents: dict[tuple[str, str | None, str | None], dict[str, Any]] = {}
        self.examples: dict[str, dict[str, Any]] = {}
        self.gaps: list[dict[str, Any]] = []
        self.sources: list[dict[str, Any]] = []
        self.root_people: dict[str, set[str]] = defaultdict(set)
        self.root_pairs: Counter[str] = Counter()
        self.root_documents: Counter[str] = Counter()
        self.expected: dict[str, set[str]] = defaultdict(set)
        self.references: list[dict[str, Any]] = []
        self.cohorts: list[dict[str, Any]] = []
        self.source_controls: dict[str, dict[str, str]] = {}
        self.cohort_hashes: list[dict[str, Any]] = []
        self.publications: dict[tuple[str | None, str], dict[str, Any]] = {}
        self.capture_limits: list[dict[str, Any]] = []

    def ref(self, source: dict[str, Any], selector: str) -> dict[str, Any]:
        return {"source_id": source["source_id"], "selector": selector, "role": source["role"]}

    def person(
        self, keys: list[str], node: dict[str, Any], source: dict[str, Any], selector: str
    ) -> str | None:
        if not keys:
            return None
        primary = next((key for key in keys if key.startswith("openalex:")), keys[0])
        row = self.people.setdefault(
            primary,
            {"person_key": primary, "identity_keys": [], "name_aliases": [], "provenance": []},
        )
        row["identity_keys"] = sorted(set(row["identity_keys"]) | set(keys))
        for name in (node.get("name"), node.get("display_name")):
            if isinstance(name, str) and name not in row["name_aliases"]:
                row["name_aliases"].append(name)
        ref = self.ref(source, selector)
        if ref not in row["provenance"]:
            row["provenance"].append(ref)
        self.root_people[source["root"]].add(primary)
        return primary

    def walk(
        self,
        node: Any,
        source: dict[str, Any],
        selector: str = "$",
        inherited: str | None = None,
        *,
        profile_context: bool = False,
    ) -> None:
        if isinstance(node, list):
            for i, value in enumerate(node):
                self.walk(
                    value, source, f"{selector}[{i}]", inherited, profile_context=profile_context
                )
            return
        if not isinstance(node, dict):
            return
        keys = (
            candidate_identity_keys(node, str(node.get("author_id", "")))
            if (
                profile_context
                or "author_id" in node
                or any(k in node for k in ("name", "orcid", "openalex_id"))
            )
            else []
        )
        person = self.person(keys, node, source, selector) or inherited
        if isinstance(node.get("profile"), dict):
            profile = node["profile"]
            profile_keys = candidate_identity_keys(profile, str(node.get("author_id", "")))
            person = self.person(profile_keys, profile, source, selector + ".profile") or person
            if (
                person is None
                and source["role"] == "synthetic_development_input"
                and isinstance(node.get("group_id"), str)
            ):
                person = "synthetic:" + node["group_id"]
                row = self.people.setdefault(
                    person,
                    {
                        "person_key": person,
                        "identity_keys": [],
                        "name_aliases": [],
                        "provenance": [],
                    },
                )
                row["provenance"].append(self.ref(source, selector + ".profile"))
                self.root_people[source["root"]].add(person)
        field = str(node.get("field", node.get("original_field", ""))).lower()
        candidates = []
        if ("email" in field or "contact" in field) and isinstance(node.get("value"), str):
            candidates.append(("value", node["value"]))
        for key in ("email", "normalized_email", "email_normalized"):
            if isinstance(node.get(key), str):
                candidates.append((key, node[key]))
        for key in ("orcid_emails", "crossref_emails"):
            if isinstance(node.get(key), list):
                candidates.extend((key, value) for value in node[key] if isinstance(value, str))
        if node.get("email_published") is True and not candidates:
            self.capture_limits.append(
                {
                    "kind": "publication_flag_without_recorded_address",
                    "source_id": source["source_id"],
                    "selector": selector,
                    "person_key": person,
                    "path": source["path"],
                    "document_locator_recorded": bool(
                        canonical_document_url(node.get("url", node.get("source_url")))
                    ),
                    "mitigation": (
                        "Known target identity is excluded; this does not restore unknown "
                        "email/document details or prove absence of shared-document reuse"
                    ),
                }
            )
        if isinstance(node.get("dois"), list):
            for i, value in enumerate(node["dois"]):
                if isinstance(value, str) and re.fullmatch(r"10\.[0-9]{4,9}/\S+", value, re.I):
                    publication_key = (person, value.lower())
                    publication = self.publications.setdefault(
                        publication_key,
                        {
                            "doi": value,
                            "person_key": person,
                            "role": "publication_reference_not_document_snapshot",
                            "provenance": [],
                        },
                    )
                    publication["provenance"].append(self.ref(source, f"{selector}.dois[{i}]"))
        for key, value in candidates:
            for match in EMAIL.finditer(value):
                email = canonical_email(match.group())
                if person is None:
                    self.gaps.append(
                        {
                            "kind": "email_item_without_target",
                            "path": source["path"],
                            "selector": selector + "." + key,
                            "blocking": True,
                        }
                    )
                    continue
                row = self.pairs.setdefault(
                    (person, email),
                    {
                        "pair_key": canonical_pair_key(person, email),
                        "person_key": person,
                        "email": email,
                        "provenance": [],
                    },
                )
                row["provenance"].append(self.ref(source, selector + "." + key))
                self.root_pairs[source["root"]] += 1
        url = canonical_document_url(node.get("url", node.get("source_url", "")))
        is_evidence = source["kind"] != "source_request_metadata" and (
            source["kind"] == "source_metadata"
            or any(
                part in selector
                for part in ("evidence_pool", ".sources", ".evidence", ".profile_evidence")
            )
        )
        if url and is_evidence:
            recorded = False
            for representation in ("body", "decoded", "text", "html", "static_text"):
                digest = node.get(representation + "_sha256")
                if isinstance(digest, str) and HASH.fullmatch(digest):
                    self.document(
                        representation,
                        digest,
                        url,
                        source,
                        selector + "." + representation + "_sha256",
                    )
                    recorded = True
            excerpt = node.get("excerpt", node.get("quote"))
            if isinstance(excerpt, str) and excerpt:
                self.document(
                    "excerpt",
                    hashlib.sha256(excerpt.encode()).hexdigest(),
                    url,
                    source,
                    selector + ".excerpt",
                )
                recorded = True
            if not recorded:
                self.document("url_only", None, url, source, selector + ".url")
        if source["kind"] == "source_request_metadata":
            for locator in ("url", "location", "uri", "ref_id"):
                request_url = canonical_document_url(node.get(locator))
                if request_url:
                    self.document(
                        "requested_url", None, request_url, source, selector + "." + locator
                    )
        for path_key, hash_key in (
            ("source_record_path", "source_record_sha256"),
            ("metadata_path", "metadata_sha256"),
        ):
            if isinstance(node.get(path_key), str) and isinstance(node.get(hash_key), str):
                self.references.append(
                    {
                        "path": node[path_key],
                        "sha256": node[hash_key],
                        "source_id": source["source_id"],
                        "selector": selector + "." + path_key,
                        "root": source["root"],
                    }
                )
        for key in ("sample_sha256", "profiles_sha256"):
            value = node.get(key)
            if isinstance(value, str) and HASH.fullmatch(value):
                self.cohort_hashes.append(
                    {
                        "sha256": value,
                        "source_id": source["source_id"],
                        "selector": selector + "." + key,
                        "path": source["path"],
                    }
                )
        for key in ("source_id", "fragment_id", "item_id", "claim_id"):
            value = node.get(key)
            if isinstance(value, str):
                scoped = source["sha256"] + ":" + selector + "." + key
                example_key = value if re.match(r"^A[0-9]+-S[0-9a-f]", value) else scoped
                self.examples.setdefault(
                    example_key, {"example_key": example_key, "local_id": value, "provenance": []}
                )["provenance"].append(self.ref(source, selector + "." + key))
        for key, value in node.items():
            structured_old_contacts = (
                key == "raw"
                and Path(source["path"]).name == "contacts_sfr5.json"
                and isinstance(value, list)
                and all(isinstance(item, dict) and "author_id" in item for item in value)
            )
            if key in TEXT_SKIP_KEYS and not structured_old_contacts:
                continue
            if key in IDENTITY_LIST_KEYS and isinstance(value, list):
                for i, raw in enumerate(value):
                    if isinstance(raw, str) and (identity := canonical_identifier(raw)):
                        self.person([identity], {}, source, f"{selector}.{key}[{i}]")
            if isinstance(value, list | dict):
                self.walk(
                    value,
                    source,
                    selector + "." + key,
                    person,
                    profile_context=key in {"profiles", "sample", "profile"},
                )

    def document(
        self,
        representation: str,
        digest: str | None,
        url: str | None,
        source: dict[str, Any],
        selector: str,
    ) -> None:
        key = (representation, digest, url)
        row = self.documents.setdefault(
            key, {"representation": representation, "sha256": digest, "url": url, "provenance": []}
        )
        row["provenance"].append(self.ref(source, selector))
        self.root_documents[source["root"]] += 1


def private_directory(path: Path) -> Path:
    target = path.resolve()
    if any((p / ".git").exists() for p in (target, *target.parents)):
        raise ValueError("Private inventory must remain outside Git")
    if target.exists():
        raise FileExistsError(target)
    target.mkdir(parents=True, mode=0o700)
    return target


def build_inventory(plan: dict[str, Any]) -> dict[str, Any]:
    if (
        plan.get("schema") != PLAN_SCHEMA
        or not isinstance(plan.get("scope"), str)
        or not plan["scope"].strip()
    ):
        raise ValueError("An explicit fixed metadata scope and plan schema are required")
    catalogue_path = Path(plan["catalogue"]["path"]).resolve()
    if sha(catalogue_path) != plan["catalogue"]["sha256"]:
        raise ValueError("Catalogue source hash changed")
    catalogue = json.loads(catalogue_path.read_text())
    if catalogue.get("schema") != "enrichment-storage-catalogue-v1":
        raise ValueError("Unsupported storage catalogue schema")
    base = Path(plan["experiment_base"]).resolve()
    cap = plan.get("metadata_byte_limit", 8 * 1024 * 1024)
    if type(cap) is not int or cap <= 0:
        raise ValueError("metadata_byte_limit must be a positive integer")
    accumulator = Accumulator()
    references = []
    roots = set()
    for item in catalogue.get("roots", []):
        path = Path(item["path"])
        experiment = path.name.startswith("enrichment") and path.parent.resolve() == base
        references.append(
            {
                "path": str(path),
                "exists": path.exists(),
                "role": "experiment" if experiment else "operational_or_checkout_reference",
                "primary_exposure_required": experiment,
            }
        )
        if experiment:
            if path.is_symlink():
                accumulator.gaps.append(
                    {"kind": "symlink_root_not_followed", "path": str(path), "blocking": True}
                )
                continue
            roots.add(path.resolve())
            if not path.is_dir():
                accumulator.gaps.append(
                    {"kind": "missing_experiment_root", "path": str(path), "blocking": True}
                )
    roots.update(p.resolve() for p in base.glob("enrichment*") if p.is_dir() and not p.is_symlink())
    for raw in plan.get("extra_roots", []):
        path = Path(raw)
        if path.is_symlink():
            accumulator.gaps.append(
                {"kind": "symlink_root_not_followed", "path": str(path), "blocking": True}
            )
        else:
            roots.add(path.resolve())
    development_roots = {Path(p).resolve() for p in plan.get("development_roots", [])}
    roots.update(development_roots)
    statistics: Counter[str] = Counter()
    root_rows: list[dict[str, Any]] = []
    # The catalogue is a recorded input, not an exposure cohort itself.
    accumulator.sources.append(
        {
            "source_id": "catalogue",
            "path": str(catalogue_path),
            "sha256": sha(catalogue_path),
            "bytes": catalogue_path.stat().st_size,
            "kind": "catalogue",
            "root": str(catalogue_path.parent),
            "role": "discovery_only",
            "schema": catalogue["schema"],
            "recorded_at": catalogue.get("at"),
            "versions": {},
        }
    )
    for root in sorted(roots):
        if not root.is_dir():
            if not any(g["path"] == str(root) for g in accumulator.gaps):
                accumulator.gaps.append(
                    {"kind": "missing_experiment_root", "path": str(root), "blocking": True}
                )
            continue
        files = []
        pruned: Counter[str] = Counter()
        for directory, children, names in os.walk(root, followlinks=False):
            kept = []
            for name in children:
                path = Path(directory) / name
                if name in PRUNE or name in SKIP_PARTS or path.is_symlink():
                    pruned[name] += 1
                else:
                    kept.append(name)
            children[:] = sorted(kept)
            for name in sorted(names):
                path = Path(directory) / name
                statistics["filenames_seen"] += 1
                if path.is_symlink():
                    statistics["symlink_files_not_followed"] += 1
                    continue
                kind = metadata_kind(path, root)
                if kind:
                    files.append((path, kind))
                else:
                    statistics["raw_or_unselected_files_not_read"] += 1
        parsed = 0
        for path, kind in files:
            size = path.stat().st_size
            if size > cap:
                statistics["oversized_metadata_not_read"] += 1
                accumulator.gaps.append(
                    {
                        "kind": "metadata_over_byte_limit",
                        "path": str(path),
                        "bytes": size,
                        "blocking": kind not in {"transfer_index", "operational_metadata"},
                    }
                )
                continue
            try:
                payload = path.read_bytes()
                data, encoding = decode_metadata(payload)
            except (OSError, ValueError) as exc:
                accumulator.gaps.append(
                    {
                        "kind": "unreadable_metadata",
                        "path": str(path),
                        "error": type(exc).__name__,
                        "blocking": kind != "operational_metadata",
                    }
                )
                continue
            statistics["metadata_files_read"] += 1
            statistics["metadata_bytes_read"] += len(payload)
            relative = path.relative_to(root)
            fixture = (
                root in development_roots
                or any(
                    token in str(relative).lower()
                    for token in ("fixture", "regression", "engineering-evidence", "preflight")
                )
                or "offline" in root.name
            )
            role = (
                "synthetic_development_input"
                if root in development_roots
                else "development_or_replay"
                if fixture
                else "recorded_experiment_metadata"
            )
            source = {
                "source_id": "m" + hashlib.sha256(str(path).encode()).hexdigest()[:24],
                "path": str(path),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
                "mtime_ns": path.stat().st_mtime_ns,
                "kind": kind,
                "root": str(root),
                "role": role,
                "parse_encoding": encoding,
                "schema": data.get("schema") if isinstance(data, dict) else "list",
                "recorded_at": next(
                    (
                        data[k]
                        for k in ("created_at", "at", "prepared_at", "checked_at")
                        if isinstance(data, dict) and isinstance(data.get(k), str)
                    ),
                    None,
                ),
                "versions": {
                    k: data[k]
                    for k in ("rules_version", "version", "method", "index_version")
                    if isinstance(data, dict) and isinstance(data.get(k), str)
                },
            }
            accumulator.sources.append(source)
            for cohort in declared_cohorts(data, path.name):
                accumulator.cohorts.append(
                    {**cohort, "source_id": source["source_id"], "root": str(root), "role": role}
                )
                accumulator.expected[str(root)].update(cohort["identity_keys"])
                if cohort["unmapped_rows"] and role not in {
                    "development_or_replay",
                    "synthetic_development_input",
                }:
                    accumulator.gaps.append(
                        {
                            "kind": "unmapped_declared_cohort_rows",
                            "path": str(path),
                            "selector": cohort["selector"],
                            "rows": cohort["unmapped_rows"],
                            "blocking": True,
                        }
                    )
            if (
                path.name == "contacts_sfr5.json"
                and isinstance(data, dict)
                and (
                    not isinstance(data.get("raw"), list)
                    or data.get("sample_size") != len(data["raw"])
                )
            ):
                accumulator.gaps.append(
                    {"kind": "contact_sample_size_mismatch", "path": str(path), "blocking": True}
                )
            if (
                path.name == "manifest.json"
                and isinstance(data, dict)
                and data.get("method")
                in {
                    "single-direct-http-positive-control-v1",
                    "single-canonical-direct-http-positive-control-v1",
                }
                and data.get("no_prevalence_or_fresh_people") is True
            ):
                accumulator.source_controls[str(root)] = {
                    "source_id": str(source["source_id"]),
                    "method": str(data["method"]),
                }
            if kind == "transfer_index":
                # Index hashes describe arbitrary files, not necessarily source content.
                # They are provenance only unless explicitly named body/text fields elsewhere.
                continue
            parsed += 1
            inherited = next(
                (
                    canonical_identifier(part)
                    for part in reversed(relative.parts)
                    if canonical_identifier(part)
                ),
                None,
            )
            if inherited:
                inherited = accumulator.person([inherited], {}, source, "$path_case_id")
            accumulator.walk(
                data,
                source,
                inherited=inherited,
                profile_context=path.name in {"sample.json", "profiles.json"},
            )
        persons = accumulator.root_people[str(root)]
        source_only = (
            str(root) in accumulator.source_controls and accumulator.root_documents[str(root)] > 0
        )
        synthetic_only = root in development_roots and not persons
        if (
            not persons
            and root.name != "enrichment-module-storage-20261011"
            and not source_only
            and not synthetic_only
        ):
            accumulator.gaps.append(
                {"kind": "no_identified_targets_in_metadata", "path": str(root), "blocking": True}
            )
        if not parsed and root.name != "enrichment-module-storage-20261011":
            accumulator.gaps.append(
                {"kind": "no_readable_case_metadata", "path": str(root), "blocking": True}
            )
        observed_aliases = {
            key for person_key in persons for key in accumulator.people[person_key]["identity_keys"]
        }
        uncovered = sorted(accumulator.expected[str(root)] - observed_aliases)
        if uncovered:
            accumulator.gaps.append(
                {
                    "kind": "declared_cohort_not_mapped",
                    "path": str(root),
                    "identity_keys": uncovered,
                    "blocking": True,
                }
            )
        root_rows.append(
            {
                "path": str(root),
                "discovery": "catalogue"
                if any(r["path"] == str(root) for r in references)
                else "post_catalogue_or_extra",
                "metadata_candidates": len(files),
                "metadata_parsed": parsed,
                "people_keys": sorted(persons),
                "expected_cohort_identity_keys": sorted(accumulator.expected[str(root)]),
                "uncovered_cohort_identity_keys": uncovered,
                "pair_occurrences": accumulator.root_pairs[str(root)],
                "document_occurrences": accumulator.root_documents[str(root)],
                "pruned_directories": dict(pruned),
                "coverage": "synthetic_only_development"
                if synthetic_only
                else "source_only_control"
                if source_only
                else "metadata_read"
                if parsed
                else "catalogue_only",
                "source_control_provenance": accumulator.source_controls.get(str(root)),
            }
        )
    reference_checks = []
    checked_references: dict[tuple[str, str], dict[str, Any]] = {}
    processed_paths = {source["path"] for source in accumulator.sources}
    roots_by_name = {root.name: root for root in roots}
    position = 0
    while position < len(accumulator.references):
        reference = accumulator.references[position]
        position += 1
        key = (reference["path"], reference["sha256"])
        if key in checked_references:
            reference_checks.append({**reference, **checked_references[key]})
            continue
        raw_path = Path(reference["path"])
        choices = [raw_path] if raw_path.is_absolute() else [Path(reference["root"]) / raw_path]
        for i, part in enumerate(raw_path.parts):
            if part in roots_by_name:
                choices.append(roots_by_name[part].joinpath(*raw_path.parts[i + 1 :]))
        target = next(
            (
                p.resolve()
                for p in choices
                if p.is_file()
                and not p.is_symlink()
                and p.suffix == ".json"
                and any(p.resolve().is_relative_to(root) for root in roots)
            ),
            None,
        )
        matching = next(
            (s for s in accumulator.sources if s["sha256"] == reference["sha256"]), None
        )
        if target is None and matching is not None:
            result = {
                "status": "resolved_identical_archived_metadata",
                "resolved_path": matching["path"],
            }
        elif target is None:
            result = {"status": "unresolved_metadata_reference"}
            accumulator.gaps.append(
                {
                    "kind": result["status"],
                    "path": reference["path"],
                    "selector": reference["selector"],
                    "source_id": reference["source_id"],
                    "blocking": True,
                }
            )
        elif target.stat().st_size > cap:
            result = {"status": "referenced_metadata_over_byte_limit", "resolved_path": str(target)}
            accumulator.gaps.append(
                {"kind": result["status"], "path": str(target), "blocking": True}
            )
        elif sha(target) != reference["sha256"]:
            if matching is not None:
                result = {
                    "status": "resolved_identical_archived_metadata",
                    "resolved_path": matching["path"],
                    "requested_path_now_has_other_version": str(target),
                }
            else:
                result = {
                    "status": "referenced_metadata_hash_mismatch",
                    "resolved_path": str(target),
                }
                accumulator.gaps.append(
                    {
                        "kind": result["status"],
                        "path": str(target),
                        "source_id": reference["source_id"],
                        "blocking": True,
                    }
                )
        else:
            result = {"status": "resolved_exact_metadata", "resolved_path": str(target)}
            if str(target) not in processed_paths:
                try:
                    payload = target.read_bytes()
                    data, encoding = decode_metadata(payload)
                except (OSError, ValueError) as exc:
                    accumulator.gaps.append(
                        {
                            "kind": "unreadable_referenced_metadata",
                            "path": str(target),
                            "error": type(exc).__name__,
                            "blocking": True,
                        }
                    )
                else:
                    source = {
                        "source_id": "m" + hashlib.sha256(str(target).encode()).hexdigest()[:24],
                        "path": str(target),
                        "sha256": hashlib.sha256(payload).hexdigest(),
                        "bytes": len(payload),
                        "kind": "source_metadata",
                        "root": reference["root"],
                        "role": "linked_metadata_receipt",
                        "parse_encoding": encoding,
                        "schema": data.get("schema") if isinstance(data, dict) else "list",
                        "recorded_at": data.get("checked_at") if isinstance(data, dict) else None,
                        "versions": {},
                    }
                    accumulator.sources.append(source)
                    statistics["metadata_files_read"] += 1
                    statistics["metadata_bytes_read"] += len(payload)
                    statistics["explicitly_referenced_metadata_files_read"] += 1
                    accumulator.walk(data, source)
                    processed_paths.add(str(target))
        checked_references[key] = result
        reference_checks.append({**reference, **result})
    cohort_snapshot_checks = []
    sources_by_hash = {source["sha256"]: source for source in accumulator.sources}
    for reference in accumulator.cohort_hashes:
        match = sources_by_hash.get(reference["sha256"])
        result = {
            **reference,
            "status": "resolved_exact_cohort_snapshot"
            if match
            else "unresolved_cohort_snapshot_hash",
        }
        if match:
            result["resolved_path"] = match["path"]
        else:
            accumulator.gaps.append(
                {
                    "kind": result["status"],
                    "path": reference["path"],
                    "selector": reference["selector"],
                    "blocking": True,
                }
            )
        cohort_snapshot_checks.append(result)
    for item in plan.get("development_documents", []):
        path = Path(item["path"]).resolve()
        if not path.is_file() or path.is_symlink() or path.stat().st_size > cap:
            accumulator.gaps.append(
                {"kind": "unavailable_development_document", "path": str(path), "blocking": True}
            )
            continue
        digest = sha(path)
        if item.get("sha256") != digest:
            accumulator.gaps.append(
                {"kind": "development_document_hash_changed", "path": str(path), "blocking": True}
            )
            continue
        source = {
            "source_id": "dev" + hashlib.sha256(str(path).encode()).hexdigest()[:24],
            "path": str(path),
            "sha256": digest,
            "bytes": path.stat().st_size,
            "kind": "declared_development_document",
            "root": str(path.parent),
            "role": "synthetic_development_input",
            "schema": "explicit_literal_document",
            "recorded_at": None,
            "versions": {"recorded_version": item.get("version")},
        }
        accumulator.sources.append(source)
        statistics["development_document_bytes_hashed"] += path.stat().st_size
        accumulator.document(
            item["representation"],
            digest,
            canonical_document_url(item.get("url")),
            source,
            "$file_bytes",
        )
    for row in root_rows:
        row["people_keys"] = sorted(accumulator.root_people[row["path"]])
        row["pair_occurrences"] = accumulator.root_pairs[row["path"]]
        row["document_occurrences"] = accumulator.root_documents[row["path"]]
    people = sorted(accumulator.people.values(), key=lambda r: r["person_key"])
    pairs = sorted(accumulator.pairs.values(), key=lambda r: r["pair_key"])
    documents = sorted(
        accumulator.documents.values(),
        key=lambda r: (r["representation"], r["sha256"] or "", r["url"] or ""),
    )
    examples = sorted(accumulator.examples.values(), key=lambda r: r["example_key"])
    metadata_complete = not any(g["blocking"] for g in accumulator.gaps)
    for limit in accumulator.capture_limits:
        accumulator.gaps.append(
            {
                "kind": "historical_capture_detail_missing",
                "path": limit["path"],
                "source_id": limit["source_id"],
                "selector": limit["selector"],
                "missing_fields": ["email_literal"]
                + ([] if limit["document_locator_recorded"] else ["document_locator"]),
                "blocking": True,
            }
        )
    gaps = list({json.dumps(g, sort_keys=True): g for g in accumulator.gaps}.values())
    # Completeness means the declared recorded metadata scope only, not all scientific authors.
    complete = not any(g["blocking"] for g in gaps)
    return {
        "schema": SCHEMA,
        "created_at": datetime.now(UTC).isoformat(),
        "scope": plan["scope"],
        "plan": plan,
        "sources": accumulator.sources,
        "people": people,
        "pairs": pairs,
        "documents": documents,
        "examples": examples,
        "publication_references": sorted(
            accumulator.publications.values(), key=lambda r: (r["person_key"] or "", r["doi"])
        ),
        "lookup": make_lookup(people, pairs, documents, examples),
        "coverage": {
            "catalogue_references": references,
            "roots": root_rows,
            "declared_cohorts": accumulator.cohorts,
            "source_record_reference_checks": reference_checks,
            "cohort_snapshot_hash_checks": cohort_snapshot_checks,
            "historical_capture_limits": accumulator.capture_limits,
            "metadata_scope_complete": metadata_complete,
            "statistics": dict(statistics),
            "source_read_policy": (
                "Only selected metadata JSON; no recursive text/email mining "
                "of source bodies or cumulative Pi/model events"
            ),
            "limitations": [
                "Names are recorded aliases, never automatic identity merges",
                (
                    "Sources with URL/excerpt only remain explicitly typed, "
                    "not invented full-body hashes"
                ),
                "Sampling frames are not read as exposure cohorts",
                (
                    "Operational missing logs/checkouts are retained references, "
                    "not automatic missing subjects"
                ),
            ],
        },
        "completeness": {
            "complete": complete,
            "prior_details_complete": not accumulator.capture_limits,
            "scope": plan["scope"],
            "gaps": gaps,
            "meaning": (
                "Recorded targets, candidate email fields and evidence references in "
                "declared accessible metadata; not all mentions in unparsed raw source bodies"
            ),
        },
    }


def validate_inventory(inventory: dict[str, Any], base_dir: Path | None = None) -> None:
    required = {
        "schema",
        "scope",
        "plan",
        "sources",
        "people",
        "pairs",
        "documents",
        "examples",
        "lookup",
        "coverage",
        "completeness",
    }
    if not required <= set(inventory) or inventory.get("schema") != SCHEMA:
        raise ValueError("A complete producer inventory is required, not a lookup receipt")
    if (
        not all(
            isinstance(inventory[k], list)
            for k in ("sources", "people", "pairs", "documents", "examples")
        )
        or not inventory["sources"]
    ):
        raise ValueError("Invalid inventory record tables")
    source_ids = set()
    for source in inventory["sources"]:
        path = Path(source["path"])
        if not path.is_absolute():
            if base_dir is None:
                raise ValueError("Relative provenance path without base_dir")
            path = base_dir / path
        if sha(path) != source["sha256"]:
            raise ValueError("Recorded metadata source hash changed")
        source_ids.add(source["source_id"])
    for table in ("people", "pairs", "documents", "examples"):
        for record in inventory[table]:
            if not record.get("provenance") or any(
                ref.get("source_id") not in source_ids or not isinstance(ref.get("selector"), str)
                for ref in record["provenance"]
            ):
                raise ValueError("Invalid record provenance")
    expected = make_lookup(
        inventory["people"], inventory["pairs"], inventory["documents"], inventory["examples"]
    )
    if inventory["lookup"] != expected:
        raise ValueError("Inventory lookup does not match full records")
    completeness = inventory["completeness"]
    if (
        not isinstance(completeness.get("gaps"), list)
        or completeness.get("scope") != inventory["scope"]
    ):
        raise ValueError("Invalid completeness evidence")
    if completeness.get("complete") is not (not any(g["blocking"] for g in completeness["gaps"])):
        raise ValueError("Completeness cannot override unresolved coverage gaps")
    if not inventory["coverage"].get("roots"):
        raise ValueError("Missing root coverage evidence")
    rebuilt = build_inventory(inventory["plan"])
    expected_content = {k: v for k, v in rebuilt.items() if k != "created_at"}
    supplied_content = {k: v for k, v in inventory.items() if k != "created_at"}
    if supplied_content != expected_content:
        raise ValueError("Inventory records/coverage do not reproduce from recorded metadata plan")


def write_inventory(plan_path: Path, output: Path) -> Path:
    plan = json.loads(plan_path.read_text())
    inventory = build_inventory(plan)
    validate_inventory(inventory, plan_path.parent)
    root = private_directory(output)
    write_new(root / "plan.json", plan)
    write_new(root / "inventory.json", inventory)
    projection = {
        "schema": "nir_prior_exclusions_v1",
        "complete_prior_use_inventory": inventory["completeness"]["complete"],
        "inventory_sources": [{"path": "inventory.json", "sha256": sha(root / "inventory.json")}],
        "group_ids": inventory["lookup"]["identity_keys"],
        "pair_ids": inventory["lookup"]["pair_keys"],
        "example_ids": inventory["lookup"]["example_keys"],
        "requires_canonical_registry_check": True,
        "warning": (
            "Literal IDs are compatibility projection only; "
            "full inventory and semantic overlap validation required"
        ),
    }
    write_new(root / "exclusions.json", projection)
    write_new(
        root / "build-proof.json",
        {
            "schema": "nir_prior_inventory_build_proof_v1",
            "plan_input_sha256": sha(plan_path),
            "code_sha256": sha(Path(__file__)),
            "inventory_sha256": sha(root / "inventory.json"),
            "exclusions_sha256": sha(root / "exclusions.json"),
            "sources": len(inventory["sources"]),
            "people": len(inventory["people"]),
            "pairs": len(inventory["pairs"]),
            "documents": len(inventory["documents"]),
            "examples": len(inventory["examples"]),
            "complete": inventory["completeness"]["complete"],
            "metadata_scope_complete": inventory["coverage"]["metadata_scope_complete"],
            "prior_details_complete": inventory["completeness"]["prior_details_complete"],
            "blocking_gaps": sum(g["blocking"] for g in inventory["completeness"]["gaps"]),
            "statistics": inventory["coverage"]["statistics"],
            "statistics_scope": (
                "One semantic metadata traversal; validation hashes and rebuild read metadata "
                "again. Raw experimental source bodies and cumulative model events are not read."
            ),
        },
    )
    return root / "build-proof.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    result = write_inventory(args.plan, args.out)
    print(result)


if __name__ == "__main__":
    main()
