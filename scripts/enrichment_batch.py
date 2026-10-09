"""Ограниченная файловая очередь; реальные агенты подключаются явным submit.

Никаких сетевых вызовов, запуска CLI или фонового сервиса. Незавершённые
резервации после прерывания требуют решения координатора, а не повторного запроса.
"""

import argparse
import fcntl
import hashlib
import json
import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from enrichment_experiment import private_root, verified_sample

STAGES = ("collect", "verify", "validate", "humanpacket", "metrics")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def immutable(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        with path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        path.chmod(0o600)
    except FileExistsError:
        if path.read_bytes() != data:
            raise ValueError("Попытка перезаписи доказательства") from None


class Batch:
    """Состояние восстанавливается только из проверенной цепочки событий."""

    def __init__(self, root: Path):
        self.root = private_root(root)
        self.config = json.loads((self.root / "batch.json").read_bytes())
        self._check_inputs()

    @classmethod
    def create(
        cls,
        root: Path,
        frozen_root: Path,
        ids: list[str],
        rules_path: Path,
        concurrency: int = 2,
        stopped_domains: list[str] | None = None,
    ) -> "Batch":
        root = private_root(root)
        profiles = {row["id"]: row for row in verified_sample(frozen_root)}
        if not 1 <= len(ids) <= 5 or len(set(ids)) != len(ids) or not set(ids) <= profiles.keys():
            raise ValueError("Нужны 1–5 уникальных ID из замороженных 100")
        if concurrency not in (1, 2):
            raise ValueError("Параллельность не более двух")
        with (root / "lock").open("a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if (root / "batch.json").exists():
                raise ValueError("Партия уже создана; используйте возобновление")
            config = {
                "version": "enrichment_batch_v3",
                "created_at_epoch": time.time(),
                "ids": ids,
                "profiles": [profiles[aid] for aid in ids],
                "sample_sha256": digest((frozen_root / "sample.json").read_bytes()),
                "frozen_root": str(frozen_root.resolve()),
                "rules_path": str(rules_path.resolve()),
                "rules_sha256": digest(rules_path.read_bytes()),
                "concurrency": concurrency,
                "initial_stopped_domains": stopped_domains or [],
                "global_limits": {"search": 20, "page": 40},
                "profile_limits": {"search": 4, "page": 8},
            }
            immutable(root / "batch.json", encoded(config))
            immutable(root / "batch.sha256", digest(encoded(config)).encode())
        return cls(root)

    def _check_inputs(self) -> None:
        if (
            digest((self.root / "batch.json").read_bytes())
            != (self.root / "batch.sha256").read_text()
        ):
            raise ValueError("Конфигурация партии изменена")
        if self.config["global_limits"] != {"search": 20, "page": 40}:
            raise ValueError("Общие лимиты нельзя ослаблять")
        if self.config["profile_limits"] != {"search": 4, "page": 8}:
            raise ValueError("Лимиты профиля нельзя ослаблять")
        if digest(Path(self.config["rules_path"]).read_bytes()) != self.config["rules_sha256"]:
            raise ValueError("Правила изменены после фиксации партии")
        frozen = Path(self.config["frozen_root"])
        verified_sample(frozen)
        if digest((frozen / "sample.json").read_bytes()) != self.config["sample_sha256"]:
            raise ValueError("Входная выборка изменена")

    @contextmanager
    def locked(self) -> Iterator[list[dict[str, Any]]]:
        with (self.root / "lock").open("a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            self._check_inputs()
            events: list[dict[str, Any]] = []
            previous = None
            for index, path in enumerate(sorted((self.root / "events").glob("*.json"))):
                event_bytes = path.read_bytes()
                if digest(event_bytes) != path.with_suffix(".sha256").read_text():
                    raise ValueError("Событие повреждено")
                row = json.loads(event_bytes)
                if row["sequence"] != index or row["previous_sha256"] != previous:
                    raise ValueError("Цепочка событий повреждена")
                previous = digest(path.read_bytes())
                events.append(row)
            # All published blobs are checked on every resume, not merely at submission.
            for row in events:
                for key in (
                    "input_sha256",
                    "result_sha256",
                    "artifact_sha256",
                    "proof_sha256",
                    "cache_sha256",
                    "evidence_sha256",
                ):
                    if key in row:
                        blob = self.root / "blobs" / row[key]
                        if not blob.exists() or digest(blob.read_bytes()) != row[key]:
                            raise ValueError("Доказательство повреждено")
            yield events

    def append(self, events: list[dict[str, Any]], action: str, **data: Any) -> None:
        index = len(events)
        previous = (
            digest((self.root / "events" / f"{index - 1:06d}.json").read_bytes()) if index else None
        )
        row = {
            "sequence": index,
            "previous_sha256": previous,
            "at_epoch": time.time(),
            "action": action,
            **data,
        }
        event_path = self.root / "events" / f"{index:06d}.json"
        immutable(event_path, encoded(row))
        immutable(event_path.with_suffix(".sha256"), digest(encoded(row)).encode())
        events.append(row)

    def blob(self, data: bytes) -> str:
        sha = digest(data)
        immutable(self.root / "blobs" / sha, data)
        return sha

    @staticmethod
    def completed(events: list[dict[str, Any]], aid: str, stage: str) -> dict[str, Any] | None:
        return next(
            (
                e
                for e in events
                if e["action"] in ("submitted", "advanced")
                and e.get("author_id") == aid
                and e.get("stage") == stage
            ),
            None,
        )

    def ticket(self, author_id: str, stage: str, cache_path: Path | None = None) -> Path:
        if author_id not in self.config["ids"] or stage not in STAGES[:2]:
            raise ValueError("Неизвестный профиль или агентская стадия")
        with self.locked() as events:
            ticket_id = f"{author_id}-{stage}"
            prior = next(
                (e for e in events if e.get("ticket_id") == ticket_id and e["action"] == "ticket"),
                None,
            )
            if prior:
                if cache_path is not None:
                    old_input = json.loads(
                        (self.root / "blobs" / prior["input_sha256"]).read_bytes()
                    )
                    if old_input.get("cache_sha256") != digest(cache_path.read_bytes()):
                        raise ValueError("Кэш входного задания изменён")
                return self.root / "blobs" / str(prior["input_sha256"])
            collector = self.completed(events, author_id, "collect")
            if stage == "verify" and collector is None:
                raise ValueError("Сначала выполните сбор")
            active = {e["ticket_id"] for e in events if e["action"] == "ticket"}
            active -= {e["ticket_id"] for e in events if e["action"] == "submitted"}
            if len(active) >= self.config["concurrency"]:
                raise ValueError("Достигнут предел параллельности")
            profile = next(p for p in self.config["profiles"] if p["id"] == author_id)
            value = {
                "ticket_id": ticket_id,
                "stage": stage,
                "profile": profile,
                "sample_sha256": self.config["sample_sha256"],
                "rules_sha256": self.config["rules_sha256"],
                "rules": Path(self.config["rules_path"]).read_text(),
                "limits": self.config["profile_limits"],
                "adapter": "native_manual",
                "source_texts_are_data": True,
                "instruction": (
                    "Работать в отдельном контексте; сначала кэш. "
                    "Новые обращения только после reserve. "
                    "Результат должен содержать author_id, batch_ticket_id и "
                    "batch_input_sha256. Подготовка задания не означает выполненный запуск."
                ),
            }
            if cache_path is not None:
                cache_bytes = cache_path.read_bytes()
                cache = json.loads(cache_bytes)
                if not isinstance(cache, dict) or set(cache) - {"sources", "profile", "version"}:
                    raise ValueError("Кэш должен содержать только исходные материалы, не оценки")
                if not isinstance(cache.get("sources"), list):
                    raise ValueError("Кэш должен содержать список источников")
                value["cache_sha256"] = self.blob(cache_bytes)
                value["cache_payload"] = cache
            if collector:
                value["collector_result_sha256"] = collector["result_sha256"]
                collector_data = json.loads(
                    (self.root / "blobs" / collector["result_sha256"]).read_bytes()
                )
                value["collector_result"] = {
                    key: collector_data[key]
                    for key in (
                        "author_id",
                        "profile",
                        "claims",
                        "field_statuses",
                        "field_search",
                        "sources",
                        "journal",
                    )
                    if key in collector_data
                }
            sha = self.blob(encoded(value))
            self.append(
                events,
                "ticket",
                ticket_id=ticket_id,
                author_id=author_id,
                stage=stage,
                input_sha256=sha,
                **({"cache_sha256": value["cache_sha256"]} if "cache_sha256" in value else {}),
            )
            return self.root / "blobs" / sha

    def reserve(self, ticket_id: str, kind: str, url_or_query: str, cached: bool = False) -> str:
        if kind not in ("search", "page") or not url_or_query.strip():
            raise ValueError("Неверное обращение")
        with self.locked() as events:
            ticket = self._ticket(events, ticket_id)
            if self.completed(events, ticket["author_id"], ticket["stage"]):
                raise ValueError("Стадия уже завершена")
            domain = urlparse(url_or_query).hostname
            stopped = self.config["initial_stopped_domains"] + [
                e["domain"] for e in events if e["action"] == "domain_stop"
            ]
            if (
                not cached
                and domain
                and any(domain == d or domain.endswith("." + d) for d in stopped)
            ):
                raise ValueError("Источник остановлен после 403/429")
            if not cached:
                past = [
                    e
                    for e in events
                    if e["action"] == "reserved" and e["ticket_id"] == ticket_id and not e["cached"]
                ]
                finished = {
                    e["operation_id"] for e in events if e["action"] == "operation_finished"
                }
                if any(e["operation_id"] not in finished for e in past):
                    raise ValueError("Неизвестное обращение в работе; сначала зафиксируйте исход")
                if any(e["kind"] == kind and e["target"] == url_or_query for e in past):
                    raise ValueError("Повторный сетевой запрос запрещён; используйте кэш")
            reservations = [
                e
                for e in events
                if e["action"] == "reserved"
                and not e["cached"]
                and e["kind"] == kind
                and e["stage"] == ticket["stage"]
            ]
            if not cached and (
                len(reservations) >= self.config["global_limits"][kind]
                or sum(e["ticket_id"] == ticket_id for e in reservations)
                >= self.config["profile_limits"][kind]
            ):
                raise ValueError("Бюджет исчерпан")
            operation_id = f"operation-{len(events):06d}"
            self.append(
                events,
                "reserved",
                operation_id=operation_id,
                ticket_id=ticket_id,
                author_id=ticket["author_id"],
                stage=ticket["stage"],
                kind=kind,
                target=url_or_query,
                domain=domain,
                cached=cached,
            )
            return operation_id

    def finish_operation(
        self, operation_id: str, outcome: str, elapsed_seconds: float | None = None
    ) -> None:
        if outcome not in ("ok", "403", "429", "error", "not_executed"):
            raise ValueError("Неизвестный исход")
        if elapsed_seconds is not None and elapsed_seconds < 0:
            raise ValueError("Некорректное время")
        with self.locked() as events:
            reservation = next(
                (
                    e
                    for e in events
                    if e.get("operation_id") == operation_id and e["action"] == "reserved"
                ),
                None,
            )
            if reservation is None or any(
                e.get("operation_id") == operation_id and e["action"] == "operation_finished"
                for e in events
            ):
                raise ValueError("Неизвестная или уже закрытая резервация")
            self.append(
                events,
                "operation_finished",
                operation_id=operation_id,
                outcome=outcome,
                elapsed_seconds=elapsed_seconds,
            )
            if outcome in ("403", "429") and reservation["domain"]:
                self.append(events, "domain_stop", domain=reservation["domain"], outcome=outcome)

    @staticmethod
    def _ticket(events: list[dict[str, Any]], ticket_id: str) -> dict[str, Any]:
        ticket = next(
            (e for e in events if e["action"] == "ticket" and e["ticket_id"] == ticket_id), None
        )
        if ticket is None:
            raise ValueError("Задание не подготовлено")
        return ticket

    def submit(self, ticket_id: str, result_path: Path, provenance: dict[str, Any]) -> str:
        data = result_path.read_bytes()
        result = json.loads(data)
        if not isinstance(result, dict):
            raise ValueError("Результат должен быть объектом JSON")
        if (
            not provenance.get("agent_id")
            or "model" not in provenance
            or "effort" not in provenance
        ):
            raise ValueError("Нужны фактическое происхождение и модель/effort либо null")
        with self.locked() as events:
            ticket = self._ticket(events, ticket_id)
            if (
                result.get("batch_ticket_id") != ticket_id
                or result.get("batch_input_sha256") != ticket["input_sha256"]
                or result.get("author_id") != ticket["author_id"]
                or provenance.get("stage") != ticket["stage"]
            ):
                raise ValueError("Результат не связан с заданием")
            previous = self.completed(events, ticket["author_id"], ticket["stage"])
            if previous:
                if (
                    previous["result_sha256"] != digest(data)
                    or previous["provenance"] != provenance
                ):
                    raise ValueError("Повторная отправка отличается")
                return str(previous["result_sha256"])
            operations = {
                e["operation_id"]
                for e in events
                if e["action"] == "reserved" and e["ticket_id"] == ticket_id
            }
            finished = {e["operation_id"] for e in events if e["action"] == "operation_finished"}
            if operations - finished:
                raise ValueError("Неизвестный исход обращений; автоматический повтор запрещён")
            reported = result.get("network_operations", [])
            actual_network = {
                e["operation_id"]
                for e in events
                if e["action"] == "reserved" and e["ticket_id"] == ticket_id and not e["cached"]
            }
            if not isinstance(reported, list) or set(reported) != actual_network:
                raise ValueError("Журнал результата не соответствует сетевым резервациям")
            collector = self.completed(events, ticket["author_id"], "collect")
            if (
                ticket["stage"] == "verify"
                and collector
                and collector["provenance"]["agent_id"] == provenance["agent_id"]
            ):
                raise ValueError("Проверяющий не может быть автором сбора")
            sha = self.blob(data)
            self.append(
                events,
                "submitted",
                ticket_id=ticket_id,
                author_id=ticket["author_id"],
                stage=ticket["stage"],
                result_sha256=sha,
                provenance=provenance,
            )
            return sha

    def advance(
        self,
        author_id: str,
        stage: str,
        artifact_path: Path,
        validator: Callable[[dict[str, Any], dict[str, Any]], None] | None = None,
    ) -> str:
        if author_id not in self.config["ids"] or stage not in STAGES[2:]:
            raise ValueError("Неизвестная стадия")
        data = artifact_path.read_bytes()
        artifact = json.loads(data)
        with self.locked() as events:
            previous_stage = STAGES[STAGES.index(stage) - 1]
            previous = self.completed(events, author_id, previous_stage)
            if previous is None:
                raise ValueError("Предыдущая стадия не завершена")
            sha_key = "result_sha256" if previous_stage == "verify" else "artifact_sha256"
            if (
                artifact.get("author_id") != author_id
                or artifact.get("stage") != stage
                or artifact.get("previous_sha256") != previous[sha_key]
                or artifact.get("completed") is not True
            ):
                raise ValueError("Артефакт стадии не подтверждает выполнение или SHA входа")
            if stage == "validate":
                if validator is None or artifact.get("succeeded") is not True:
                    raise ValueError("Нужен реально выполняемый валидатор")
                result_data = json.loads((self.root / "blobs" / previous[sha_key]).read_bytes())
                validator(result_data, artifact)
            else:
                proof_path = Path(artifact.get("proof_path", ""))
                if not proof_path.is_file():
                    raise ValueError("Отсутствует настоящий пакет или агрегат")
                proof = proof_path.read_bytes()
                if digest(proof) != artifact.get("proof_sha256"):
                    raise ValueError("Доказательство стадии изменено")
                if stage == "humanpacket" and b"<html" not in proof.lower():
                    raise ValueError("Нужен HTML-пакет")
                if stage == "metrics" and not isinstance(json.loads(proof), dict):
                    raise ValueError("Нужен JSON агрегатов")
                self.blob(proof)
            old = self.completed(events, author_id, stage)
            if old:
                if old["artifact_sha256"] != digest(data):
                    raise ValueError("Изменён повторный артефакт")
                return str(old["artifact_sha256"])
            sha = self.blob(data)
            self.append(
                events,
                "advanced",
                author_id=author_id,
                stage=stage,
                artifact_sha256=sha,
                **({"proof_sha256": artifact["proof_sha256"]} if stage != "validate" else {}),
            )
            return sha

    def record_adapter_error(
        self,
        author_id: str,
        stage: str,
        error_code: str,
        evidence_path: Path,
        occurred_at_epoch: float | None = None,
    ) -> str:
        """Дописывает отказ и исходное доказательство; время записи не время отказа.

        Повтор той же записи идемпотентен. Не меняет выполненные стадии и не
        разрешает повтор агента. occurred_at_epoch=None означает неизвестное время.
        """
        if author_id not in self.config["ids"] or stage not in STAGES:
            raise ValueError("Неизвестный профиль или стадия отказа")
        if not error_code or not isinstance(error_code, str):
            raise ValueError("Нужен код отказа")
        evidence = evidence_path.read_bytes()
        with self.locked() as events:
            evidence_sha = self.blob(evidence)
            if any(
                e["action"] == "adapter_error"
                and e["author_id"] == author_id
                and e["stage"] == stage
                and e["error_code"] == error_code
                and e["evidence_sha256"] == evidence_sha
                for e in events
            ):
                return evidence_sha
            self.append(
                events,
                "adapter_error",
                author_id=author_id,
                stage=stage,
                error_code=error_code,
                evidence_sha256=evidence_sha,
                occurred_at_epoch=occurred_at_epoch,
                recorded_retrospectively=occurred_at_epoch is None,
            )
            return evidence_sha

    def status(self) -> dict[str, Any]:
        with self.locked() as events:
            reservations = [e for e in events if e["action"] == "reserved"]
            finished = {e["operation_id"] for e in events if e["action"] == "operation_finished"}
            all_done = all(self.completed(events, aid, "metrics") for aid in self.config["ids"])
            end_time = (
                max(
                    e["at_epoch"]
                    for e in events
                    if e["action"] == "advanced" and e["stage"] == "metrics"
                )
                if all_done
                else time.time()
            )
            submissions = [e for e in events if e["action"] == "submitted"]
            wall = [e["provenance"].get("wall_elapsed_seconds") for e in submissions]
            known_wall = [v for v in wall if isinstance(v, int | float) and v >= 0]
            return {
                "ids": self.config["ids"],
                "stages": {
                    aid: {stage: self.completed(events, aid, stage) is not None for stage in STAGES}
                    for aid in self.config["ids"]
                },
                "wall_elapsed_seconds": end_time - self.config["created_at_epoch"],
                "writing_state": "completed" if all_done else "active",
                "event_count": len(events),
                "durable_coordinator_actions": sum(e["action"] != "domain_stop" for e in events),
                "coordinator_interventions": None,
                "reported_agent_wall_seconds_known_sum": sum(known_wall),
                "reported_agent_wall_seconds_unknown_count": len(wall) - len(known_wall),
                "network_reservations": sum(not e["cached"] for e in reservations),
                "cached_operations": sum(e["cached"] for e in reservations),
                "unknown_inflight": sorted(
                    e["operation_id"] for e in reservations if e["operation_id"] not in finished
                ),
                "errors": sum(
                    e["action"] == "adapter_error"
                    or (
                        e["action"] == "operation_finished"
                        and e["outcome"] in ("403", "429", "error")
                    )
                    for e in events
                ),
                "adapter_errors": sum(e["action"] == "adapter_error" for e in events),
                "automatic_retries": 0,
                "tokens": None,
                "cost": None,
                "active_runtime_seconds": None,
                "adapter": (
                    "codex_exec_ephemeral_cache_only"
                    if submissions
                    and all(
                        e["provenance"].get("agent_id", "").startswith("codex-ephemeral:")
                        for e in submissions
                    )
                    else "native_manual"
                    if submissions
                    else "not_executed"
                ),
            }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("--frozen-root", type=Path, required=True)
    create.add_argument("--rules", type=Path, required=True)
    create.add_argument("--ids", nargs="+", required=True)
    sub.add_parser("status")
    ticket = sub.add_parser("ticket")
    ticket.add_argument("author_id")
    ticket.add_argument("stage", choices=STAGES[:2])
    ticket.add_argument("--cache-file", type=Path)
    reserve = sub.add_parser("reserve")
    reserve.add_argument("ticket_id")
    reserve.add_argument("kind", choices=("search", "page"))
    reserve.add_argument("target")
    reserve.add_argument("--cached", action="store_true")
    finish = sub.add_parser("finish")
    finish.add_argument("operation_id")
    finish.add_argument("outcome")
    submit = sub.add_parser("submit")
    submit.add_argument("ticket_id")
    submit.add_argument("result", type=Path)
    submit.add_argument("--provenance", type=Path, required=True)
    advance = sub.add_parser("advance")
    advance.add_argument("author_id")
    advance.add_argument("stage", choices=STAGES[2:])
    advance.add_argument("artifact", type=Path)
    args = parser.parse_args()
    if args.command == "create":
        value: Any = Batch.create(args.root, args.frozen_root, args.ids, args.rules).status()
    else:
        batch = Batch(args.root)
        if args.command == "status":
            value = batch.status()
        elif args.command == "ticket":
            value = str(batch.ticket(args.author_id, args.stage, args.cache_file))
        elif args.command == "reserve":
            value = batch.reserve(args.ticket_id, args.kind, args.target, args.cached)
        elif args.command == "finish":
            batch.finish_operation(args.operation_id, args.outcome)
            value = None
        elif args.command == "submit":
            value = batch.submit(
                args.ticket_id, args.result, json.loads(args.provenance.read_bytes())
            )
        else:
            value = batch.advance(args.author_id, args.stage, args.artifact)
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
