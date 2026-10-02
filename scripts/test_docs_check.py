"""Regressions for one accepted state and direct checks against measured artifacts."""

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

import docs_check as check

SCREEN = """# Brief
## Где мы сейчас
12 вузов, 9 002 профиля. frida_clean-9002p-35e591d4.
0.33 / 0.40 / 0.49. Success@5 = 87,5 %, Success@1 = 66,7 %.
[метрики](../metrics/quality.json). Открытой итерации нет. Спека MVP — v1.16.
## Контекст
"""


class BriefChecks(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.addCleanup(patch.stopall)
        patch.object(check, "ROOT", self.root).start()
        self.put("docs/product/brief.md", SCREEN)
        self.put("docs/DECISIONS.md", "# Decisions\nИстория без копии текущего состояния.")
        self.put("docs/product/mvp_spec.md", "**Версия:** v1.16")
        self.metrics: dict[str, Any] = {
            "index_version": "frida_clean-9002p-35e591d4",
            "n_profiles": 9002,
            "sets": {
                "golden_in_domain_24": {
                    "blind": {
                        "success_at_5": 0.875,
                        "success_at_1": 0.667,
                    }
                }
            },
        }
        self.put("docs/metrics/quality.json", json.dumps(self.metrics))

    def put(self, name: str, value: str) -> None:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)

    def test_brief_is_sufficient_without_state_in_decisions(self) -> None:
        findings: list[str] = []
        state = check.check_brief(findings)
        check.check_brief_metrics(state, findings)
        check.check_iteration(findings)
        check.check_spec_version(findings)
        self.assertEqual(findings, [])
        self.assertEqual(state["profiles"], 9002)

    def test_missing_index_is_rejected(self) -> None:
        self.put("docs/product/brief.md", SCREEN.replace("frida_clean-9002p-35e591d4", ""))
        findings: list[str] = []
        check.check_brief(findings)
        self.assertTrue(any("index_version" in item for item in findings))

    def test_quality_claim_must_match_measurement(self) -> None:
        self.metrics["sets"]["golden_in_domain_24"]["blind"]["success_at_5"] = 0.5
        self.put("docs/metrics/quality.json", json.dumps(self.metrics))
        findings: list[str] = []
        check.check_brief_metrics(check.check_brief(findings), findings)
        self.assertTrue(any("s5" in item for item in findings))

    def test_missing_measurement_is_rejected(self) -> None:
        (self.root / "docs/metrics/quality.json").unlink()
        findings: list[str] = []
        check.check_brief_metrics(check.check_brief(findings), findings)
        self.assertTrue(findings)

    def test_open_spec_contradicts_no_iteration(self) -> None:
        self.put("SPEC_SFR7_ranking.md", "# Future spec")
        findings: list[str] = []
        check.check_iteration(findings)
        self.assertTrue(findings)

    def test_settings_and_index_are_still_verified(self) -> None:
        self.put(
            "apps/api/src/sfr_api/settings.py",
            """
score_threshold: float = 0.20
score_weak: float = 0.40
score_high: float = 0.49
""",
        )
        self.put(
            "data/indexes_sfr5c/frida_clean/meta.json",
            json.dumps(
                {
                    "model_key": "frida",
                    "clean": True,
                    "n_profiles": 9001,
                    "corpus_sha": "35e591d4",
                    "thresholds": {"none": 0.33, "weak": 0.40, "high": 0.49},
                }
            ),
        )
        findings: list[str] = []
        with patch.dict(
            "os.environ",
            {"SFR_INDEX_META": str(self.root / "data/indexes_sfr5c/frida_clean/meta.json")},
        ):
            check.check_state_vs_index(check.check_brief(findings), findings)
        self.assertTrue(any("profiles" in item for item in findings))
        self.assertTrue(any("ApiSettings" in item for item in findings))


if __name__ == "__main__":
    unittest.main()
