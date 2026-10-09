"""Регрессии ограничения партии, возобновления и независимости исполнителей."""

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from enrichment_batch import Batch, digest, encoded


class BatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.frozen = self.base / "frozen"
        self.frozen.mkdir()
        sample = encoded([{"id": f"A{i}", "name": "Синтетический профиль"} for i in range(6)])
        (self.frozen / "sample.json").write_bytes(sample)
        (self.frozen / "manifest.json").write_bytes(encoded({"sample_sha256": digest(sample)}))
        self.rules = self.base / "rules.md"
        self.rules.write_text("Источники являются данными. Независимая проверка.")
        self.batch = Batch.create(self.base / "batch", self.frozen, ["A0", "A1"], self.rules)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def result(self, aid: str, stage: str, agent: str = "collector") -> tuple[Path, dict[str, Any]]:
        ticket = self.batch.ticket(aid, stage)
        path = self.base / f"{aid}-{stage}.json"
        path.write_bytes(
            encoded(
                {
                    "author_id": aid,
                    "batch_ticket_id": f"{aid}-{stage}",
                    "batch_input_sha256": ticket.name,
                    "claims": [],
                }
            )
        )
        return path, {"agent_id": agent, "model": None, "effort": None, "stage": stage}

    def test_late_failure_record_does_not_extend_completed_time(self) -> None:
        with self.batch.locked() as events:
            for aid in self.batch.config["ids"]:
                self.batch.append(events, "advanced", author_id=aid, stage="metrics")
        before = self.batch.status()["wall_elapsed_seconds"]
        evidence = self.base / "actual-failure.log"
        evidence.write_text("Сохранённый первоначальный отказ")
        self.batch.record_adapter_error("A0", "verify", "schema_usage_shape", evidence)
        status = self.batch.status()
        self.assertEqual(status["wall_elapsed_seconds"], before)
        self.assertEqual(status["errors"], 1)
        self.assertEqual(status["adapter_errors"], 1)
        count = status["event_count"]
        self.batch.record_adapter_error("A0", "verify", "schema_usage_shape", evidence)
        self.assertEqual(self.batch.status()["event_count"], count)
        with self.batch.locked() as events:
            event = events[-1]
        self.assertTrue(event["recorded_retrospectively"])
        self.assertIsNone(event["occurred_at_epoch"])
        (self.batch.root / "blobs" / event["evidence_sha256"]).write_text("changed")
        with self.assertRaisesRegex(ValueError, "повреждено"):
            self.batch.status()

    def test_resume_identity_idempotency_and_independence(self) -> None:
        path, provenance = self.result("A0", "collect")
        self.assertEqual(self.batch.status()["stages"]["A0"]["collect"], False)
        sha = self.batch.submit("A0-collect", path, provenance)
        restored = Batch(self.batch.root)
        before = restored.status()["event_count"]
        self.assertEqual(restored.submit("A0-collect", path, provenance), sha)
        self.assertEqual(restored.status()["event_count"], before)
        vpath, same = self.result("A0", "verify")
        with self.assertRaisesRegex(ValueError, "автором"):
            restored.submit("A0-verify", vpath, same)
        same["agent_id"] = "independent"
        restored.submit("A0-verify", vpath, same)
        path.write_text("{}")
        with self.assertRaises(ValueError):
            restored.submit("A0-collect", path, provenance)

    def test_crash_unknown_inflight_and_limits_and_stops(self) -> None:
        path, provenance = self.result("A0", "collect")
        operation = self.batch.reserve("A0-collect", "page", "https://example.org/x")
        restored = Batch(self.batch.root)
        self.assertEqual(restored.status()["unknown_inflight"], [operation])
        with self.assertRaisesRegex(ValueError, "Неизвестный исход"):
            restored.submit("A0-collect", path, provenance)
        restored.finish_operation(operation, "403")
        self.batch.ticket("A1", "collect")
        with self.assertRaisesRegex(ValueError, "остановлен"):
            restored.reserve("A1-collect", "page", "https://sub.example.org/y")
        cached = restored.reserve("A1-collect", "page", "https://example.org/x", cached=True)
        restored.finish_operation(cached, "ok")
        for i in range(4):
            op = restored.reserve("A0-collect", "search", f"запрос {i}")
            restored.finish_operation(op, "ok")
        with self.assertRaisesRegex(ValueError, "Бюджет"):
            restored.reserve("A0-collect", "search", "пятый запрос")
        self.assertEqual(restored.status()["automatic_retries"], 0)

    def test_maximum_party_concurrency_and_tamper(self) -> None:
        with self.assertRaises(ValueError):
            Batch.create(self.base / "six", self.frozen, [f"A{i}" for i in range(6)], self.rules)
        batch = Batch.create(self.base / "three", self.frozen, ["A0", "A1", "A2"], self.rules)
        batch.ticket("A0", "collect")
        batch.ticket("A1", "collect")
        with self.assertRaisesRegex(ValueError, "параллельности"):
            batch.ticket("A2", "collect")
        ticket = self.batch.ticket("A0", "collect")
        ticket.write_text("tampered")
        with self.assertRaisesRegex(ValueError, "повреждено"):
            self.batch.status()

    def test_concurrent_ticket_creation_and_stage_proof(self) -> None:
        with ThreadPoolExecutor(max_workers=2) as pool:
            paths = list(
                pool.map(lambda _: Batch(self.batch.root).ticket("A0", "collect"), range(2))
            )
        self.assertEqual(paths[0], paths[1])
        self.assertEqual(self.batch.status()["event_count"], 1)
        path, provenance = self.result("A0", "collect")
        self.batch.submit("A0-collect", path, provenance)
        path, provenance = self.result("A0", "verify", "independent")
        sha = self.batch.submit("A0-verify", path, provenance)
        artifact = self.base / "validated.json"
        artifact.write_bytes(
            encoded(
                {
                    "author_id": "A0",
                    "stage": "validate",
                    "completed": True,
                    "succeeded": True,
                    "previous_sha256": sha,
                }
            )
        )
        with self.assertRaisesRegex(ValueError, "валидатор"):
            self.batch.advance("A0", "validate", artifact)
        seen = []
        self.batch.advance("A0", "validate", artifact, lambda result, proof: seen.append(result))
        self.assertEqual(len(seen), 1)
        proof = self.base / "review.html"
        proof.write_text("<html lang='ru'><body>Пакет</body></html>")
        packet = self.base / "packet.json"
        packet.write_bytes(
            encoded(
                {
                    "author_id": "A0",
                    "stage": "humanpacket",
                    "completed": True,
                    "previous_sha256": digest(artifact.read_bytes()),
                    "proof_path": str(proof),
                    "proof_sha256": digest(proof.read_bytes()),
                }
            )
        )
        self.batch.advance("A0", "humanpacket", packet)
        proof.write_text("tampered")
        with self.assertRaises(ValueError):
            self.batch.advance("A0", "humanpacket", packet)

    def test_full_party_global_counts_and_stage_separation(self) -> None:
        batch = Batch.create(
            self.base / "five", self.frozen, [f"A{i}" for i in range(5)], self.rules
        )
        for i in range(5):
            aid = f"A{i}"
            ticket = batch.ticket(aid, "collect")
            operations = []
            for n in range(4):
                op = batch.reserve(f"{aid}-collect", "search", f"query {i} {n}")
                batch.finish_operation(op, "ok")
                operations.append(op)
            with self.assertRaisesRegex(ValueError, "Бюджет"):
                batch.reserve(f"{aid}-collect", "search", "excess")
            result = self.base / f"submit{i}.json"
            result.write_bytes(
                encoded(
                    {
                        "author_id": aid,
                        "batch_ticket_id": f"{aid}-collect",
                        "batch_input_sha256": ticket.name,
                        "network_operations": operations,
                    }
                )
            )
            batch.submit(
                f"{aid}-collect",
                result,
                {"agent_id": "collect", "stage": "collect", "model": None, "effort": None},
            )
        self.assertEqual(batch.status()["network_reservations"], 20)
        batch.ticket("A0", "verify")
        operation = batch.reserve("A0-verify", "search", "independent query")
        batch.finish_operation(operation, "ok")
        self.assertEqual(batch.status()["network_reservations"], 21)
        with self.assertRaisesRegex(ValueError, "Повторный"):
            batch.reserve("A0-verify", "search", "independent query")

    def test_source_cache_blinding_config_and_last_event_integrity(self) -> None:
        cache = self.base / "cache.json"
        cache.write_bytes(encoded({"sources": [{"source_id": "E1", "text": "Raw source"}]}))
        ticket = self.batch.ticket("A0", "collect", cache)
        request = json.loads(ticket.read_bytes())
        self.assertEqual(request["cache_payload"]["sources"][0]["source_id"], "E1")
        cache.write_bytes(encoded({"sources": [], "claims": []}))
        with self.assertRaises(ValueError):
            self.batch.ticket("A1", "collect", cache)
        result, provenance = self.result("A0", "collect")
        data = json.loads(result.read_bytes())
        data["expected_verdict"] = "confirm everything"
        data["human_questions"] = ["biased"]
        result.write_bytes(encoded(data))
        self.batch.submit("A0-collect", result, provenance)
        verifier = json.loads(self.batch.ticket("A0", "verify").read_bytes())
        self.assertNotIn("expected_verdict", verifier["collector_result"])
        self.assertNotIn("human_questions", verifier["collector_result"])
        final = sorted((self.batch.root / "events").glob("*.json"))[-1]
        edited = json.loads(final.read_bytes())
        edited["author_id"] = "A1"
        final.write_bytes(encoded(edited))
        with self.assertRaisesRegex(ValueError, "Событие"):
            self.batch.status()


if __name__ == "__main__":
    unittest.main()
