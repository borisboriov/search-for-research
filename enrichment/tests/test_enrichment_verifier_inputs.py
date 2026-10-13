"""Фиксированный поднабор сохраняет байты и скрывает старое происхождение."""

import copy
import unittest
from typing import Any

from sfr_enrichment_legacy.enrichment_verifier_inputs import CASES, common_input


def source(author: str = "A1", ids: tuple[str, ...] = ("c1",)) -> dict[str, Any]:
    return {
        "author_id": author,
        "profile": {
            "id": author,
            "name": "Человек",
            "institution": "Вуз",
            "profile_text": "Тема",
            "cohort": "old_model_group",
        },
        "collector_agent_id": "secret-model",
        "old_verifier_agent_id": "old-model",
        "old_output_sha256": "secret-sha",
        "items": [
            {
                "item_id": f"{author}_{key}",
                "origin": "collector",
                "original_field": "topic",
                "value": "Точный факт\n",
                "evidence_refs": ["E1"],
            }
            for key in ids
        ],
        "evidence_pool": {
            "E1": {
                "url": "https://example.test/person",
                "excerpt": "Exact quote\n",
                "object_type": "scientist",
                "expected_verdict": "secret",
            },
            "E2": {"url": "https://example.test/unused", "excerpt": "unused"},
        },
        "profile_evidence": {"identity": ["E1"], "current_affiliation": []},
    }


class InputsTests(unittest.TestCase):
    def test_allowlist_preserves_quotes_and_values(self) -> None:
        old = source()
        before = copy.deepcopy(old)
        value = common_input(old, ["A1_c1"], "rules")
        self.assertEqual(old, before)
        self.assertEqual(value["items"][0]["value"], old["items"][0]["value"])
        self.assertEqual(value["evidence_pool"]["E1"]["excerpt"], "Exact quote\n")
        self.assertEqual(set(value["evidence_pool"]), {"E1"})
        self.assertNotIn("cohort", value["profile"])
        self.assertNotIn("expected_verdict", value["evidence_pool"]["E1"])
        self.assertNotIn("collector_agent_id", value)

    def test_empty_unknown_and_invalid_ref(self) -> None:
        value = common_input(source(ids=()), [], "rules")
        self.assertEqual(value["items"], [])
        old = source()
        old["items"][0]["evidence_refs"] = ["missing"]
        with self.assertRaises(ValueError):
            common_input(old, ["A1_c1"], "rules")
        old = source()
        old["items"][0]["origin"] = "verifier_candidate"
        with self.assertRaises(ValueError):
            common_input(old, ["A1_c1"], "rules")

    def test_exact37_selection(self) -> None:
        self.assertEqual(len(CASES), 12)
        self.assertEqual(sum(len(ids) for _, ids, _ in CASES), 37)
        self.assertEqual(sum(not ids for _, ids, _ in CASES), 2)
