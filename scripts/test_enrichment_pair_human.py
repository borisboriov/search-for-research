"""Парное ослепление, связывание доказательств и честный частичный просмотр."""

import copy
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from enrichment_experiment import read, sha, write_new
from enrichment_pair_human import generate, import_answers
from test_enrichment_semantics import fixture


class PairHumanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source, self.result = fixture()
        self.source["profile"] = {"name": "Test <script>alert(1)</script>", "institution": "Вуз"}
        self.source["items"][0].update(value="Тема", evidence_refs=["E0001"])
        self.source["evidence_pool"]["E0001"].update(
            url="https://example.org/source", checked_at="2026-10-09", information_date=None
        )
        self.source_path = self.root / "source.json"
        write_new(self.source_path, self.source)
        self.paths = {}
        for name in ("pi", "native"):
            result = copy.deepcopy(self.result)
            result["input_sha256"] = sha(self.source_path)
            result["provenance"].update(agent_id=name, model=f"secret-model-{name}")
            path = self.root / f"{name}.json"
            write_new(path, result)
            self.paths[name] = str(path)
        self.entries: list[dict[str, Any]] = [
            {
                "input_path": str(self.source_path),
                "result_paths": self.paths,
                "selection_reason": "Зафиксированный новый случайный профиль",
            }
        ]

    def packet(self, seed: str = "seed", packet_id: str = "three") -> Path:
        return generate(self.root / "private", packet_id, self.entries, seed)

    def answers(self, page: Path, **changes: object) -> Path:
        manifest_path = page.parent / "manifest.json"
        manifest = read(manifest_path)
        value = {
            "schema": "paired_human_answers_v1",
            "packet_id": "three",
            "packet_sha256": sha(manifest_path),
            "human_name": "Тестовый просмотр",
            "actual_human_attestation": True,
            "minutes": 1.5,
            "reviewed_at": "2026-10-09T12:00:00+03:00",
            "answers": [dict(manifest["questions"][0], grade="incorrect", note="Тест")],
            **changes,
        }
        path = self.root / "answers.json"
        path.write_text(json.dumps(value, ensure_ascii=False))
        return path

    def test_invalid_missing_atoms_remain_visible_without_acceptance(self) -> None:
        from enrichment_semantics import validate

        bad = read(Path(self.paths["pi"]))
        bad["items"] = []
        bad["profile_assessments"]["identity"]["evidence_refs"] = ["missing-source"]
        try:
            validate(self.source, bad, sha(self.source_path))
        except ValueError as exc:
            failure = str(exc)
        else:
            self.fail("Invalid response unexpectedly accepted")
        path = self.root / "invalid.json"
        write_new(
            path,
            {
                "result": bad,
                "input_sha256": sha(self.source_path),
                "classifications": None,
                "validation": {"succeeded": False, "errors": [failure]},
            },
        )
        self.entries[0]["result_paths"]["pi"] = str(path)
        page = self.packet()
        self.assertIn("Исходный ответ с ошибками", page.read_text())
        self.assertIn("missing-source", page.read_text())
        self.assertFalse(read(page.parent / "manifest.json")["human_reviewed"])

    def test_blinding_separate_and_immutable_with_exact_quote(self) -> None:
        page = self.packet()
        text = page.read_text()
        self.assertNotIn("secret-model", text)
        self.assertNotIn("executor", text)
        self.assertNotIn("<script>alert", text)
        self.assertIn("&lt;script&gt;alert", text)
        self.assertIn("Точная цитата", text)
        self.assertIn("не доказывает их правильность", text)
        manifest = read(page.parent / "manifest.json")
        self.assertFalse(manifest["human_reviewed"])
        self.assertNotIn("provenance", json.dumps(manifest))
        unblind = read(self.root / "private/paired-human/unblinding/three.json")
        self.assertEqual(
            {v["executor"] for v in unblind["profiles"][0]["responses"].values()}, {"pi", "native"}
        )
        self.assertEqual(self.packet(), page)
        with self.assertRaises(ValueError):
            self.packet("different")

    def test_seed_can_reverse_order_and_does_not_fix_model_order(self) -> None:
        orders = set()
        for number in range(12):
            self.packet(str(number), f"packet{number}")
            mapping = read(self.root / f"private/paired-human/unblinding/packet{number}.json")
            orders.add(mapping["profiles"][0]["responses"]["A"]["executor"])
        self.assertEqual(orders, {"pi", "native"})

    def test_partial_review_is_not_full_and_import_is_idempotent(self) -> None:
        page = self.packet()
        answer = self.answers(page)
        destination = import_answers(self.root / "private", page.parent / "manifest.json", answer)
        self.assertEqual(read(destination)["fully_reviewed_profiles"], [])
        self.assertEqual(read(destination)["reviewed_responses"], 1)
        self.assertEqual(
            import_answers(self.root / "private", page.parent / "manifest.json", answer),
            destination,
        )
        self.assertFalse(read(page.parent / "manifest.json")["human_reviewed"])

    def test_both_answers_can_be_wrong_and_full_requires_every_response(self) -> None:
        page = self.packet()
        manifest = read(page.parent / "manifest.json")
        answer = self.answers(
            page, answers=[dict(q, grade="incorrect", note="") for q in manifest["questions"]]
        )
        record = read(import_answers(self.root / "private", page.parent / "manifest.json", answer))
        self.assertEqual(record["fully_reviewed_profiles"], ["A1"])
        self.assertEqual({row["grade"] for row in record["answers"]["answers"]}, {"incorrect"})

    def test_reject_fake_attestation_time_duplicate_and_foreign_packet(self) -> None:
        page = self.packet()
        for changes in (
            {"actual_human_attestation": False},
            {"minutes": 0},
            {"minutes": True},
            {"minutes": float("nan")},
            {"human_name": " "},
            {"packet_sha256": "other"},
            {"reviewed_at": "2026-10-09T12:00:00"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                import_answers(
                    self.root / "private",
                    page.parent / "manifest.json",
                    self.answers(page, **changes),
                )
        q = read(page.parent / "manifest.json")["questions"][0]
        row = dict(q, grade="correct")
        with self.assertRaises(ValueError):
            import_answers(
                self.root / "private",
                page.parent / "manifest.json",
                self.answers(page, answers=[row, row]),
            )

    def test_reject_input_mismatch_same_executor_and_exposed_model(self) -> None:
        for change in ("input", "executor", "self"):
            with self.subTest(change=change):
                result = read(Path(self.paths["native"]))
                if change == "input":
                    result["input_sha256"] = "other"
                elif change == "executor":
                    result["provenance"]["agent_id"] = "pi"
                else:
                    result["summary"]["known"] = "Я Codex, мои выводы"
                path = self.root / f"bad-{change}.json"
                write_new(path, result)
                entries = copy.deepcopy(self.entries)
                entries[0]["result_paths"]["native"] = str(path)
                with self.assertRaises(ValueError):
                    generate(self.root / "private", f"bad-{change}", entries, "seed")

    def test_empty_profile_is_kept_and_has_reviewable_unknowns(self) -> None:
        source = dict(self.source, items=[])
        source_path = self.root / "empty.json"
        write_new(source_path, source)
        paths = {}
        for name in ("pi", "native"):
            result = read(Path(self.paths[name]))
            result.update(items=[], input_sha256=sha(source_path))
            path = self.root / f"empty-{name}.json"
            write_new(path, result)
            paths[name] = str(path)
        page = generate(
            self.root / "private",
            "empty",
            [
                {
                    "input_path": str(source_path),
                    "result_paths": paths,
                    "selection_reason": "Не заменён пустой профиль",
                }
            ],
            "seed",
        )
        self.assertIn("не доказательство отсутствия", page.read_text())
        self.assertEqual(len(read(page.parent / "manifest.json")["questions"]), 8)

    def test_item_identifier_cannot_collide_with_summary_question(self) -> None:
        source = copy.deepcopy(self.source)
        source["items"][0]["item_id"] = "summary"
        path = self.root / "collision-source.json"
        write_new(path, source)
        paths = {}
        for name in ("pi", "native"):
            result = read(Path(self.paths[name]))
            result["items"][0]["item_id"] = "summary"
            result["input_sha256"] = sha(path)
            result_path = self.root / f"collision-{name}.json"
            write_new(result_path, result)
            paths[name] = str(result_path)
        page = generate(
            self.root / "private",
            "collision",
            [{"input_path": str(path), "result_paths": paths, "selection_reason": "Случайный"}],
            "seed",
        )
        questions = read(page.parent / "manifest.json")["questions"]
        self.assertEqual(len(questions), len({tuple(q.values()) for q in questions}))
        self.assertIn("item:summary", {q["question_id"] for q in questions})

    def test_reject_more_than_three_duplicate_profiles(self) -> None:
        for entries in (self.entries * 2, self.entries * 4):
            with self.assertRaises(ValueError):
                generate(self.root / "private", "invalid", entries, "seed")


if __name__ == "__main__":
    unittest.main()
