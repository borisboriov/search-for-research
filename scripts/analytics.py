"""Operator-only analytics: explicit period reports, private exports, diagnostics.

No HTTP exports. Database credentials come from environment; failures expose only
exception classes. Export schema v1 includes sensitive context and must stay private.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import shutil
import statistics
from collections import Counter, defaultdict
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, func, select, text

from sfr_api.analytics.models import Context, EventContext, ProductEvent, Search

TABLES = ("analytics_searches", "analytics_events", "analytics_context", "analytics_event_context")
STAGES = ("visit", "attempt", "display", "profile", "letter_copy")


def diagnostic_problems(result: dict[str, Any]) -> list[str]:
    """Exit zero only for verified current DB and a clean delivery history.

    Replay may remove the backlog, but it does not erase historical errors or
    prove that every attempted observation survived. Never clear that history
    to produce a green check. Reasons are categorical, without private payloads.
    """
    problems = []
    if result.get("database_available") is not True:
        problems.append("database_unavailable")
    if not (
        result.get("migration_current") is True
        and result.get("expected_migration")
        and result.get("migration") == result["expected_migration"]
    ):
        problems.append("migration_not_current")
    for field, reason in (
        ("pending_count", "pending_records"),
        ("quarantine_count", "quarantined_records"),
        ("error_count", "historical_errors"),
    ):
        if result.get(field, 0):
            problems.append(reason)
    if result.get("incomplete") is not False:
        problems.append("incomplete_observations")
    if result.get("last_error"):
        problems.append("unresolved_storage_error")
    if result.get("disk_free_bytes", result.get("free_bytes", 0)) < result.get("reserve_bytes", 0):
        problems.append("disk_below_reserve")
    return problems


def private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or path.stat().st_mode & 0o077:
        raise PermissionError("output directory must be private (0700)")


def write_private(path: Path, value: str) -> None:
    # O_EXCL avoids following an existing symlink or overwriting an earlier export.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())


def instant(value: str, timezone: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        zone = ZoneInfo(timezone)
        first, second = parsed.replace(tzinfo=zone, fold=0), parsed.replace(tzinfo=zone, fold=1)
        if first.utcoffset() != second.utcoffset():
            raise ValueError("ambiguous/nonexistent local time; supply explicit UTC offset")
        parsed = first
    return parsed.astimezone(UTC)


def database_url() -> str:
    url = os.environ.get("SFR_ANALYTICS_OPERATOR_DATABASE_URL") or os.environ.get(
        "SFR_ANALYTICS_MIGRATION_DATABASE_URL", ""
    )
    if not url:
        raise ValueError("set SFR_ANALYTICS_OPERATOR_DATABASE_URL")
    return url


def read_database(
    start: datetime | None = None, end: datetime | None = None, *, include_context: bool = True
) -> dict[str, Any]:
    engine = create_engine(
        database_url(),
        pool_size=1,
        max_overflow=0,
        pool_timeout=2,
        connect_args={"connect_timeout": 2, "options": "-c timezone=UTC -c statement_timeout=5000"},
    )
    output: dict[str, Any] = {"schema_version": 1, "exported_at": datetime.now(UTC).isoformat()}
    try:
        with engine.connect() as connection, connection.begin():
            connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            for model in (Search, ProductEvent, Context, EventContext):
                if not include_context and model in (Context, EventContext):
                    continue
                table = model.__table__
                statement = select(table)
                if start is not None and end is not None:
                    if model is Context:
                        ids = select(Search.search_id).where(
                            Search.received_at >= start, Search.received_at < end
                        )
                        statement = statement.where(table.c.search_id.in_(ids))
                    elif model is EventContext:
                        ids = select(ProductEvent.event_id).where(
                            ProductEvent.received_at >= start, ProductEvent.received_at < end
                        )
                        statement = statement.where(table.c.event_id.in_(ids))
                    else:
                        statement = statement.where(
                            table.c.received_at >= start, table.c.received_at < end
                        )
                output[model.__tablename__] = [
                    dict(row) for row in connection.execute(statement).mappings()
                ]
            output["migration"] = connection.execute(
                text("SELECT version_num FROM analytics_alembic_version")
            ).scalar()
    finally:
        engine.dispose()
    return output


def time_value(row: dict[str, Any], field: str) -> datetime:
    value = row[field]
    return value if isinstance(value, datetime) else instant(str(value), "UTC")


def event_order(row: dict[str, Any]) -> tuple[int, str]:
    # client_seq supplies logical order within a visit, independent of delivery or
    # browser wall-clock; event_id resolves duplicate/invalid sequence ties.
    return int(row["client_seq"]), str(row["event_id"])


def copied_after_profile(
    event: dict[str, Any], events: list[dict[str, Any]], displayed: dict[str, Any]
) -> bool:
    author = event.get("data", {}).get("author_id")
    return bool(author) and any(
        row["name"] == "profile_opened"
        and str(row["visit_id"]) == str(event["visit_id"])
        and row.get("data", {}).get("author_id") == author
        and event_order(displayed) < event_order(row) < event_order(event)
        for row in events
    )


def observed_sequence_gaps(events: list[dict[str, Any]]) -> dict[str, tuple[int, int]]:
    """Missing internal seq values and gap intervals, bounded by observations.

    No assertion about a missing prefix/tail or loss cause. Late delivery can
    fill these gaps when the report period includes its server reception time.
    """
    sequences: dict[str, set[int]] = defaultdict(set)
    for event in events:
        sequences[str(event["visit_id"])].add(int(event["client_seq"]))
    gaps = {}
    for visit, values in sequences.items():
        missing = [right - left - 1 for left, right in pairwise(sorted(values)) if right > left + 1]
        gaps[visit] = (sum(missing), len(missing))
    return gaps


def summarize(data: dict[str, Any], start: datetime, end: datetime) -> dict[str, Any]:
    events = [e for e in data["analytics_events"] if start <= time_value(e, "received_at") < end]
    events = list({str(e["event_id"]): e for e in events}.values())
    searches = [
        s for s in data["analytics_searches"] if start <= time_value(s, "received_at") < end
    ]
    searches = list({str(s["search_id"]): s for s in searches}.values())
    context = {str(c["search_id"]): c for c in data.get("analytics_context", [])}
    traffic_by_search: dict[str, str] = {}
    for sid, row in context.items():
        headers = {str(k).lower(): str(v) for k, v in row.get("diagnostic_headers", {}).items()}
        agent = headers.get("user-agent", "")
        traffic_by_search[sid] = (
            "declared_technical"
            if re.search(r"(?i)sfr-(rehearsal|technical|test)", agent)
            else "suspected_bot"
            if re.search(r"(?i)bot|crawler|spider|headless", agent)
            else "unclassified"
        )
    all_events, all_searches = events, searches
    sequence_gaps = observed_sequence_gaps(all_events)
    visit_traffic: dict[str, str] = {}
    for row in searches:
        kind = row.get("payload", {}).get("traffic_type") or traffic_by_search.get(
            str(row["search_id"]), "unclassified"
        )
        if row.get("visit_id") and kind != "unclassified":
            visit_traffic[str(row["visit_id"])] = kind
    for row in events:
        if row.get("traffic_type", "unclassified") != "unclassified":
            visit_traffic[str(row["visit_id"])] = row["traffic_type"]
    events = [e for e in events if str(e["visit_id"]) not in visit_traffic]
    searches = [
        s
        for s in searches
        if str(s.get("visit_id")) not in visit_traffic
        and s.get("payload", {}).get("traffic_type", "unclassified") == "unclassified"
    ]
    by_visit: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_search: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        by_visit[str(event["visit_id"])].append(event)
        if event.get("search_id"):
            by_search[str(event["search_id"])].append(event)
    visits = {v for v, rows in by_visit.items() if any(e["name"] == "visit_started" for e in rows)}
    search_by_id = {str(s["search_id"]): s for s in searches}
    counts: Counter[str] = Counter({stage: 0 for stage in STAGES})
    counts["visit"] = len(visits)
    reached_visits: dict[str, set[str]] = {stage: set() for stage in STAGES}
    reached_visits["visit"] = visits
    attempts: list[dict[str, Any]] = []
    for search_id, rows in sorted(by_search.items()):
        rows.sort(key=event_order)
        attempted = next((e for e in rows if e["name"] == "search_attempt"), None)
        stages = {stage: False for stage in STAGES}
        if attempted:
            visit_id = str(attempted["visit_id"])
            start_event = next(
                (
                    e
                    for e in sorted(by_visit[visit_id], key=event_order)
                    if e["name"] == "visit_started"
                ),
                None,
            )
            stages["visit"] = bool(
                start_event and event_order(start_event) < event_order(attempted)
            )
            stages["attempt"] = stages["visit"]
            previous = attempted
            displayed = attempted
            expected = (
                ("results_shown", "weak_shown", "empty_shown"),
                ("profile_opened",),
                ("letter_copy_success",),
            )
            for stage, names in zip(STAGES[2:], expected, strict=True):
                match = next(
                    (
                        e
                        for e in rows
                        if e["name"] in names
                        and str(e["visit_id"]) == visit_id
                        and event_order(e) > event_order(previous)
                        and (stage != "letter_copy" or copied_after_profile(e, rows, displayed))
                    ),
                    None,
                )
                # A browser claim of display must have a recorded successful server result.
                server = search_by_id.get(search_id, {})
                server_ok = server.get("outcome") == "success"
                if not stages[STAGES[STAGES.index(stage) - 1]] or not match or not server_ok:
                    break
                stages[stage] = True
                if stage == "display":
                    displayed = match
                previous = match
            for stage in STAGES[1:]:
                if stages[stage]:
                    counts[stage] += 1
                    reached_visits[stage].add(visit_id)
        server = search_by_id.get(search_id, {})
        payload = server.get("payload", {})
        attempts.append(
            {
                "search_id": search_id,
                "visit_id": attempted.get("visit_id") if attempted else None,
                "observed_attempt": bool(attempted),
                **stages,
                "server_status": server.get("status"),
                "confidence": payload.get("confidence"),
                "release": payload.get("app_version"),
                "index": payload.get("index_version"),
                "server_ms": payload.get("wall_ms"),
                "display_ms": next(
                    (
                        e.get("data", {}).get("elapsed_ms")
                        for e in rows
                        if e["name"] in {"results_shown", "weak_shown", "empty_shown"}
                    ),
                    None,
                ),
            }
        )
    # Include server facts with missing client attempt: absence is observable incompleteness.
    missing = set(search_by_id) - set(by_search)
    for sid in sorted(missing):
        server = search_by_id[sid]
        attempts.append(
            {
                "search_id": sid,
                "observed_attempt": False,
                **dict.fromkeys(STAGES, False),
                "server_status": server["status"],
                "confidence": server["payload"].get("confidence"),
            }
        )
    traffic_funnels: dict[str, Counter[str]] = defaultdict(Counter)
    for attempt in attempts:
        traffic = search_by_id.get(str(attempt["search_id"]), {}).get("payload", {}).get(
            "traffic_type"
        ) or traffic_by_search.get(str(attempt["search_id"]), "unclassified")
        attempt["traffic"] = traffic
        for stage in STAGES[1:]:
            traffic_funnels[traffic][stage] += int(attempt[stage])
    dimensions: dict[str, Counter[str]] = {
        "confidence": Counter(
            str(s["payload"].get("confidence", "unknown"))
            for s in searches
            if s["outcome"] == "success"
        ),
        "server_status": Counter(str(s["status"]) for s in searches),
        "release": Counter(str(s["payload"].get("app_version", "unknown")) for s in searches),
        "index": Counter(str(s["payload"].get("index_version", "unknown")) for s in searches),
        "device": Counter(
            str(e.get("data", {}).get("viewport", "unknown"))
            for e in events
            if e["name"] == "visit_started"
        ),
        "event": Counter(e["name"] for e in events),
        "traffic": Counter(
            traffic_by_search.get(str(s["search_id"]), "unclassified") for s in searches
        ),
    }
    server_ms = [
        float(s["payload"]["wall_ms"]) for s in searches if s["payload"].get("wall_ms") is not None
    ]
    display_ms = [
        float(e["data"]["elapsed_ms"])
        for e in events
        if e["name"] in {"results_shown", "weak_shown", "empty_shown"}
        and e.get("data", {}).get("elapsed_ms") is not None
    ]
    clock_anomalies = sum(
        abs((time_value(e, "client_at") - time_value(e, "received_at")).total_seconds()) > 300
        for e in events
    )
    replay_lags = [
        (time_value(row, "persisted_at") - time_value(row, "received_at")).total_seconds()
        for row in events + searches
        if row.get("persisted_at")
    ]
    traffic_groups: dict[str, Any] = {}
    for category in ("unclassified", "declared_technical", "suspected_bot"):
        group_searches = [
            s
            for s in all_searches
            if (
                s.get("payload", {}).get("traffic_type")
                or traffic_by_search.get(str(s["search_id"]), "unclassified")
            )
            == category
        ]
        group_events = [e for e in all_events if e.get("traffic_type", "unclassified") == category]
        group_gaps = [
            values
            for visit, values in sequence_gaps.items()
            if visit_traffic.get(visit, "unclassified") == category
        ]
        traffic_groups[category] = {
            "observed_sequence_gap_count": sum(values[0] for values in group_gaps),
            "observed_sequence_gap_intervals": sum(values[1] for values in group_gaps),
            "visits_with_sequence_gaps": sum(values[0] > 0 for values in group_gaps),
            "server_searches": len(group_searches),
            "events": len(group_events),
            "visits": len(
                {str(e["visit_id"]) for e in group_events if e["name"] == "visit_started"}
            ),
            "server_status": dict(Counter(str(s["status"]) for s in group_searches)),
            "confidence": dict(
                Counter(
                    str(s["payload"].get("confidence", "unknown"))
                    for s in group_searches
                    if s["outcome"] == "success"
                )
            ),
            "event": dict(Counter(e["name"] for e in group_events)),
        }
    return {
        "traffic_groups": traffic_groups,
        "observed_sequence_gap_count": sum(values[0] for values in sequence_gaps.values()),
        "observed_sequence_gap_intervals": sum(values[1] for values in sequence_gaps.values()),
        "visits_with_sequence_gaps": sum(values[0] > 0 for values in sequence_gaps.values()),
        "schema_version": 1,
        "start_utc": start.isoformat(),
        "end_utc": end.isoformat(),
        "visits": len(visits),
        "all_searches": len(all_searches),
        "all_events": len(all_events),
        "excluded_visits": dict(Counter(visit_traffic.values())),
        "traffic_server_searches": dict(
            Counter(
                s.get("payload", {}).get("traffic_type")
                or traffic_by_search.get(str(s["search_id"]), "unclassified")
                for s in all_searches
            )
        ),
        "searches": len(searches),
        "events": len(events),
        "funnel_visits": {stage: len(reached_visits[stage]) for stage in STAGES},
        "funnel_attempts": dict(counts),
        "attempts": attempts,
        "traffic_attempt_funnels": {k: dict(v) for k, v in traffic_funnels.items()},
        "direct_profile_traffic": dict(
            Counter(
                e.get("traffic_type", "unclassified")
                for e in events
                if e["name"] == "profile_direct"
            )
        ),
        "dimensions": {key: dict(value) for key, value in dimensions.items()},
        "repeat_attempts": sum(
            max(0, sum(e["name"] == "search_attempt" for e in rows) - 1)
            for rows in by_visit.values()
        ),
        "direct_profiles": sum(e["name"] == "profile_direct" for e in events),
        "server_without_client_attempt": sum(
            not a["observed_attempt"] for a in attempts if a.get("server_status")
        ),
        "client_attempt_without_server": sum(
            a["observed_attempt"] and not a.get("server_status") for a in attempts
        ),
        "clock_anomalies": clock_anomalies,
        "replay_lag_max_seconds": max(replay_lags, default=0),
        "server_ms_median": statistics.median(server_ms) if server_ms else None,
        "display_ms_median": statistics.median(display_ms) if display_ms else None,
        "migration": data.get("migration"),
        "exported_at": data.get("exported_at"),
    }


def write_report(summary: dict[str, Any], directory: Path, timezone: str) -> None:
    private_dir(directory)
    write_private(
        directory / "summary.json", json.dumps(summary, ensure_ascii=False, indent=2, default=str)
    )
    rows = []
    for stage in STAGES:
        previous = STAGES[max(0, STAGES.index(stage) - 1)]
        denominator = summary["funnel_visits"][previous]
        rows.append(
            {
                "stage": stage,
                "visits": summary["funnel_visits"][stage],
                "denominator_visits": denominator,
                "attempts": summary["funnel_attempts"][stage] if stage != "visit" else None,
            }
        )
    dimensions = [
        {
            "dimension": dimension,
            "value": value,
            "count": count,
            "denominator": sum(values.values()),
        }
        for dimension, values in summary["dimensions"].items()
        for value, count in values.items()
    ]
    for row in rows:
        previous = STAGES[max(0, STAGES.index(row["stage"]) - 1)]
        row["denominator_attempts"] = (
            summary["funnel_attempts"][previous]
            if row["stage"] not in {"visit", "attempt"}
            else None
        )
    for name, table in (
        ("funnel", rows),
        ("attempts", summary["attempts"]),
        ("dimensions", dimensions),
    ):
        fields = list(dict.fromkeys(key for row in table for key in row))
        fd = os.open(directory / f"{name}.csv", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(table)
    # Only aggregate values, never query/context/author names/browser arbitrary text.
    safe = {k: v for k, v in summary.items() if k != "attempts"}
    body = html.escape(json.dumps(safe, ensure_ascii=False, indent=2, default=str))
    content = f"""<!doctype html><html lang="ru"><meta charset="utf-8">
<title>Search For Research — analytics</title>
<style>body{{max-width:1000px;margin:2em auto;font:16px system-ui}}
pre{{white-space:pre-wrap}}</style>
<h1>Наблюдаемые визиты и попытки поиска</h1>
<p>Период [{html.escape(summary["start_utc"])}, {html.escape(summary["end_utc"])});
часовой пояс ввода {html.escape(timezone)}.</p>
<p>Последовательная воронка связывает события одной попытки search_id и visit_id по client_seq,
а не по IP. Число визитов не равно числу людей. Серверная задержка и монотонное время
браузера до показа указаны отдельно.</p>
<p>Копирование письма — поведенческий сигнал, не отправка или оценка качества.
Отсутствие следующего события означает отсутствие наблюдения.
Закрытие вкладки и потеря сети могут терять события. Технические прогоны и предполагаемые
боты выделяются явно; UA не доказывает личность. Отчёт отражает только полученные записи;
после догрузки период нужно пересчитать. Воронка ограничена событиями, принятыми в периоде:
визит, начавшийся до периода, не включается в последовательную воронку.</p>
<p>Разрывы client_seq — ненаблюдаемые номера между двумя принятыми событиями одного визита.
Начало и хвост последовательности не объявляются потерянными. Разрыв может заполниться
поздней доставкой при пересчёте периода, включающего её серверное время приёма.
Это отсутствие наблюдений, а не доказанная причина ухода или безвозвратной потери.</p>
<pre>{body}</pre></html>"""
    write_private(directory / "report.html", content)


def main() -> int:
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    report = commands.add_parser("report")
    report.add_argument("--start", required=True)
    report.add_argument("--end", required=True)
    report.add_argument("--timezone", required=True)
    report.add_argument(
        "--export", type=Path, help="private schema-v1 JSON export instead of live DB"
    )
    report.add_argument("--out", type=Path, required=True)
    export = commands.add_parser("export")
    export.add_argument("--out", type=Path, required=True)
    export.add_argument("--format", choices=("json", "match-jsonl"), default="json")
    export.add_argument("--start")
    export.add_argument("--end")
    export.add_argument("--timezone", default="UTC")
    commands.add_parser("check")
    commands.add_parser("replay")
    args = parser.parse_args()
    try:
        if args.command == "report":
            start, end = instant(args.start, args.timezone), instant(args.end, args.timezone)
            if start >= end:
                raise ValueError("start must precede end")
            data = (
                json.loads(args.export.read_text())
                if args.export
                else read_database(start, end, include_context=False)
            )
            if data.get("schema_version") != 1:
                raise ValueError("unsupported export schema")
            summary = summarize(data, start, end)
            write_report(summary, args.out, args.timezone)
            print(
                json.dumps(
                    {
                        "report": str(args.out),
                        "visits": summary["visits"],
                        "searches": summary["searches"],
                    }
                )
            )
        elif args.command == "export":
            if bool(args.start) != bool(args.end):
                raise ValueError("provide both start and end")
            export_start = instant(args.start, args.timezone) if args.start else None
            export_end = instant(args.end, args.timezone) if args.end else None
            if export_start and export_end and export_start >= export_end:
                raise ValueError("start must precede end")
            private_dir(args.out.parent)
            data = read_database(export_start, export_end)
            if args.format == "match-jsonl":
                contexts = {str(row["search_id"]): row for row in data["analytics_context"]}
                lines = []
                for row in sorted(data["analytics_searches"], key=lambda r: str(r["received_at"])):
                    if row["outcome"] == "success":
                        legacy = dict(row["payload"]["legacy"])
                        legacy["query"] = contexts[str(row["search_id"])]["normalized_query"]
                        lines.append(json.dumps(legacy, ensure_ascii=False, default=str))
                content = "\n".join(lines) + ("\n" if lines else "")
            else:
                content = json.dumps(data, ensure_ascii=False, default=str)
            write_private(args.out, content)
            print(json.dumps({"private_export": str(args.out)}))
        else:
            from sfr_api.analytics.store import DurableStore
            from sfr_api.settings import ApiSettings

            settings = ApiSettings()
            store = DurableStore(settings.analytics_database_url, settings.analytics_spool_dir)
            if args.command == "replay":
                print(json.dumps(store.replay(), default=str))
            else:
                result = store.diagnostics()
                usage = shutil.disk_usage(settings.analytics_spool_dir)
                result["disk_free_bytes"] = usage.free
                result["disk_total_bytes"] = usage.total
                try:
                    engine = create_engine(
                        database_url(),
                        pool_size=1,
                        max_overflow=0,
                        pool_timeout=2,
                        connect_args={
                            "connect_timeout": 2,
                            "options": "-c timezone=UTC -c statement_timeout=5000",
                        },
                    )
                    try:
                        with engine.connect() as connection:
                            connection.execute(text("SET TRANSACTION READ ONLY"))
                            result["migration"] = connection.execute(
                                text("SELECT version_num FROM analytics_alembic_version")
                            ).scalar()
                            from alembic.config import Config
                            from alembic.script import ScriptDirectory

                            from sfr_api.analytics import migrate

                            config = Config()
                            config.set_main_option(
                                "script_location", str(Path(migrate.__file__).parent / "alembic")
                            )
                            result["expected_migration"] = ScriptDirectory.from_config(
                                config
                            ).get_current_head()
                            result["migration_current"] = (
                                result["migration"] == result["expected_migration"]
                            )
                            for model, label in ((Search, "searches"), (ProductEvent, "events")):
                                statement = select(
                                    func.count().label("count"),
                                    func.max(model.received_at).label("last_received_at"),
                                    func.max(model.persisted_at).label("last_persisted_at"),
                                ).select_from(model)
                                stats = connection.execute(statement).mappings().one()
                                result[label] = dict(stats)
                        result["database_available"] = True
                    finally:
                        engine.dispose()
                except Exception as exc:
                    result["database_available"] = False
                    result["database_error_class"] = type(exc).__name__
                problems = diagnostic_problems(result)
                result["check_ok"] = not problems
                result["check_reasons"] = problems
                print(json.dumps(result, default=str))
                return 1 if problems else 0
    except Exception as exc:
        # SQL errors can contain parameters/full queries/credentials. Keep diagnostic categorical.
        print(json.dumps({"ok": False, "error_class": type(exc).__name__}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
