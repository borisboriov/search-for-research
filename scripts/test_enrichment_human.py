"""Проверки безопасной карточки и фактического, частичного просмотра."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from enrichment_experiment import read, sha, write_new
from enrichment_human import assessed_date_summary, human_metrics, import_human, make_packet, proof


def fixture_packet(tmp_path: Path, stratum: str = "random") -> tuple[Path, Path]:
    source_path, assessment_path = tmp_path / "source.json", tmp_path / "assessment.json"
    claim = {
        "claim_id": "claim1",
        "field": "workload",
        "value": "One-year appointment <script>alert(1)</script>",
        "evidence": [
            {
                "url": "javascript:alert(1)",
                "excerpt": "</script><script>bad</script>",
                "information_date": None,
                "checked_at": "2026-10-09",
            }
        ],
    }
    source = {
        "author_id": "A1",
        "profile": {"name": "Dummy person", "institution": "Dummy"},
        "collector": {"claims": [claim, dict(claim, claim_id="claim2")]},
    }
    write_new(source_path, source)
    assessment = {
        "author_id": "A1",
        "input_sha256": sha(source_path),
        "claim_assessments": [
            {
                "claim_id": key,
                "text_verdict": "supported",
                "identity_verdict": "insufficient",
                "field_verdict": "misclassified",
                "corrected_field": "appointment_duration",
                "object_type": "offer",
                "student_level": ["postdoc"],
                "current_applicability": "undated",
                "explanation": "Длительность не является нагрузкой.",
                "evidence": claim["evidence"],
            }
            for key in ("claim1", "claim2")
        ],
        "new_findings": [],
        "identity": {"verdict": "insufficient"},
    }
    write_new(assessment_path, assessment)
    packet = make_packet(
        tmp_path / "private",
        "packet1",
        [
            {
                "input_path": str(source_path),
                "assessment_path": str(assessment_path),
                "stratum": stratum,
                "selection_reason": "Заранее зафиксированная причина",
            }
        ],
    )
    return packet, packet.parent / "manifest.json"


def answers(tmp_path: Path, manifest: Path, **changes: object) -> Path:
    value = {
        "schema": "human_answers_v3",
        "packet_id": "packet1",
        "packet_sha256": sha(manifest),
        "human_name": "Тестовый человек",
        "reviewed_at": "2026-10-09T10:00:00+03:00",
        "minutes": 2.5,
        "actual_human_attestation": True,
        "answers": [
            {
                "author_id": "A1",
                "claim_id": "claim1",
                "decision": "agree",
                "note": "Проверен фрагмент",
            }
        ],
    }
    value.update(changes)
    path = tmp_path / "answers.json"
    path.write_text(json.dumps(value, ensure_ascii=False))
    return path


class HumanPacketTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.tmp_path = Path(self.directory.name)

    def test_unestablished_date_is_not_presented_as_a_fact_date(self) -> None:
        for basis in ["url_only", "conflicting", "unknown", None]:
            with self.subTest(basis=basis):
                page = assessed_date_summary(
                    {"information_date": "2022-07-01", "date_basis": basis}
                )
                assert "2022-07-01" not in page
                assert "Дата сведений по оценке проверяющего:</strong> Неизвестно" in page
                assert "Дата чтения страницы не обновляет эти сведения" in page
                if basis == "conflicting":
                    assert "Даты противоречат друг другу" in page
                if basis == "url_only":
                    assert "Есть только дата в адресе страницы" in page

    def test_established_date_is_shown_with_its_basis(self) -> None:
        for basis in ["content", "source_metadata"]:
            with self.subTest(basis=basis):
                page = assessed_date_summary(
                    {"information_date": "2022-07-01", "date_basis": basis}
                )
                assert "Дата сведений по оценке проверяющего:</strong> 2022-07-01" in page
                assert "Основание даты:" in page

    def test_original_metadata_and_check_date_do_not_refresh_source_quote(self) -> None:
        quote = "Appointment closed in 2022 & no new opening."
        page = proof(
            [
                {
                    "url": "https://example.org/2023",
                    "excerpt": quote,
                    "information_date": "2023",
                    "checked_at": "2026-10-09",
                }
            ]
        )
        assert "Appointment closed in 2022 &amp; no new opening." in page
        assert "Дата в исходных метаданных: 2023" in page
        assert "Дата проверки источника: 2026-10-09" in page
        assert "не подтверждают дату факта или текущую применимость" in page

    def test_partial_human_record_does_not_accept_whole_profile(self) -> None:
        tmp_path = self.tmp_path
        packet, manifest = fixture_packet(tmp_path)
        page = packet.read_text()
        assert "Длительность договора" in page
        assert "Аспирантура / PhD" not in page
        assert "Постдок" in page
        assert "Неверно отнесено к полю" in page
        assert "<script>alert(1)</script>" not in page
        assert 'href="javascript:' not in page
        assert "&lt;/script&gt;" in page
        assert read(manifest)["human_reviewed"] is False
        record = import_human(
            tmp_path / "private", manifest, answers(tmp_path, manifest), "record1"
        )
        result = read(record)
        assert result["reviewed_claims"] == 1
        assert result["profile_review"][0]["all_original_claims_reviewed"] is False
        assert result["profile_review"][0]["human_reviewed"] is False
        assert result["comparisons"][0]["collector_field"] == "workload"
        assert result["comparisons"][0]["verifier"]["corrected_field"] == "appointment_duration"
        assert read(manifest)["human_reviewed"] is False
        with self.assertRaises(FileExistsError):
            import_human(tmp_path / "private", manifest, tmp_path / "answers.json", "record1")

    def test_reject_fabricated_or_unbound_human_record(self) -> None:
        scenarios: list[dict[str, object]] = [
            {"packet_sha256": "wrong"},
            {"actual_human_attestation": False},
            {"human_name": ""},
            {"minutes": float("nan")},
            {"minutes": True},
            {"answers": []},
            {
                "answers": [
                    {"author_id": "A2", "claim_id": "claim1", "decision": "agree", "note": ""}
                ]
            },
            {"answers": [{"author_id": "A1", "claim_id": "claim1", "decision": "yes", "note": ""}]},
        ]
        for changes in scenarios:
            with self.subTest(changes=changes), TemporaryDirectory() as directory:
                tmp_path = Path(directory)
                _, manifest = fixture_packet(tmp_path)
                with self.assertRaises(ValueError):
                    import_human(
                        tmp_path / "private",
                        manifest,
                        answers(tmp_path, manifest, **changes),
                        "bad",
                    )
                assert not (tmp_path / "private" / "human-v3" / "records" / "bad.json").exists()

    def test_random_and_targeted_are_not_pooled(self) -> None:
        tmp_path = self.tmp_path
        records = []
        for group in ("random", "targeted"):
            directory = tmp_path / group
            directory.mkdir()
            _, manifest = fixture_packet(directory, group)
            records.append(
                import_human(
                    directory / "private", manifest, answers(directory, manifest), "actual"
                )
            )
        metrics = human_metrics(records)
        assert metrics["strata"]["random"]["reviewed_claims"] == 1
        assert metrics["strata"]["targeted"]["reviewed_claims"] == 1
        assert metrics["actual_human_minutes"] == 5
        with self.assertRaises(ValueError):
            human_metrics([records[0], records[0]])

    def test_packet_preserves_hash_binding_and_rejects_overwrite(self) -> None:
        tmp_path = self.tmp_path
        packet, _ = fixture_packet(tmp_path)
        source = tmp_path / "source.json"
        source.write_text(source.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "другим входом"):
            make_packet(
                tmp_path / "private",
                "packet1",
                [
                    {
                        "input_path": str(source),
                        "assessment_path": str(tmp_path / "assessment.json"),
                        "stratum": "random",
                        "selection_reason": "Заранее зафиксированная причина",
                    }
                ],
            )
        assert packet.exists()

    def test_actual_v3_wrapper_checks_eligibility_and_keeps_candidates(self) -> None:
        tmp_path = self.tmp_path
        from enrichment_semantics import RULES_VERSION, validate

        source = {
            "author_id": "A1",
            "profile": {"name": "Dummy", "institution": "Dummy"},
            "collector_agent_id": "collector",
            "old_verifier_agent_id": "old",
            "items": [
                {
                    "item_id": "c1",
                    "origin": "collector",
                    "original_field": "workload",
                    "value": "One-yearpostdocappointmentwithpossibleextension",
                    "evidence_refs": ["E1"],
                },
                {
                    "item_id": "candidate_001",
                    "origin": "verifier_candidate",
                    "original_field": "topic",
                    "value": "Dummy topic",
                    "evidence_refs": ["E1"],
                },
            ],
            "evidence_pool": {
                "E1": {
                    "url": "https://example.org/dummy",
                    "excerpt": "One year",
                    "information_date": None,
                    "checked_at": "2026-10-09",
                    "object_type": "offer",
                }
            },
        }
        source_path = tmp_path / "v3input.json"
        write_new(source_path, source)
        profile_axis: dict[str, Any] = {
            "verdict": "insufficient",
            "evidence_refs": [],
            "explanation": "Связь не установлена",
            "information_date": None,
            "date_basis": "unknown",
        }
        row = {
            "item_id": "c1",
            "text_verdict": "supported",
            "identity_verdict": "insufficient",
            "field_verdict": "misclassified",
            "corrected_field": "appointment_duration",
            "fact_kind": "appointment_duration",
            "object_type": "offer",
            "object_relation": "supported",
            "student_level": ["postdoc"],
            "information_date": None,
            "date_basis": "unknown",
            "current_applicability": "undated",
            "evidence_refs": ["E1"],
            "explanation": "Длительность не нагрузка",
            "value_ru": "Срок договора составляет один год; часы работы не указаны.",
            "question": "Согласны с переносом в длительность?",
        }
        result = {
            "author_id": "A1",
            "input_sha256": sha(source_path),
            "rules_version": RULES_VERSION,
            "provenance": {
                "agent_id": "new",
                "runtime_status": "runtime_not_exposed",
                "model": None,
                "effort": None,
                "tokens": None,
                "cost_usd": None,
            },
            "items": [
                row,
                dict(
                    row,
                    item_id="candidate_001",
                    field_verdict="correct",
                    corrected_field=None,
                    fact_kind="literal",
                ),
            ],
            "profile_assessments": {
                "identity": profile_axis,
                "current_affiliation": profile_axis,
                "activity": dict(
                    profile_axis, status="deceased", verdict="supported", evidence_refs=["E1"]
                ),
            },
            "summary": {
                "known": "Известен срок договора",
                "unknown": "Нагрузка неизвестна",
                "identity": "Личность не установлена",
                "current_opportunity": "Дата неизвестна",
            },
        }
        wrapper: dict[str, Any] = {
            "input_sha256": sha(source_path),
            "result": result,
            "classifications": validate(source, result, sha(source_path)),
        }
        assessed_path = tmp_path / "v3output.json"
        write_new(assessed_path, wrapper)
        entries = [
            {
                "input_path": str(source_path),
                "assessment_path": str(assessed_path),
                "stratum": "random",
                "selection_reason": "Предварительный отбор",
            }
        ]
        page = make_packet(tmp_path / "private", "actual", entries).read_text()
        assert "Известен срок договора" in page
        assert "Нагрузка неизвестна" in page
        assert "Кандидат: новая находка проверяющего" in page
        assert "without" not in page
        import re

        visible = re.sub(
            r"<details>.*?</details>|<script[^>]*>.*?</script>", "", page, flags=re.DOTALL
        )
        assert "One-yearpostdocappointmentwithpossibleextension" not in visible
        assert "Исходная запись сборщика" in page
        assert "Срок договора составляет один год; часы работы не указаны." in visible
        assert "Есть подтверждение смерти" in visible
        assert "Подтверждена профессиональная активность" not in visible
        assert "Не увеличивает положительное покрытие поля" in visible
        assert "Срок договора или обучения не означает рабочую нагрузку" in visible
        assert "Новая находка остаётся кандидатом без независимого подтверждения" in visible
        assert "Нынешняя аффилиация" in visible
        wrapper["classifications"]["c1"]["usable_coverage"] = True
        assessed_path.write_text(json.dumps(wrapper))
        with self.assertRaisesRegex(ValueError, "классификация отличается"):
            make_packet(tmp_path / "private", "tampered", entries)


if __name__ == "__main__":
    unittest.main()
