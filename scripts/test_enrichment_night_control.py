"""Одноответный контроль не выдумывает B и проверяет полный объём судейства."""

import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from enrichment_night_control import freeze, validate_single
from enrichment_verifier_benchmark import AXES


class FreshControlTests(unittest.TestCase):
    def test_failed_comparison_does_not_create_or_select_fresh_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "fresh"
            comparison = Path(directory) / "comparison"
            comparison.mkdir()
            with (
                patch(
                    "enrichment_night_control.comparison_metrics",
                    return_value={"eligible_for_fresh_control": False},
                ),
                self.assertRaisesRegex(ValueError, "критерий"),
            ):
                freeze(root, comparison)
            self.assertFalse(root.exists())

    def test_single_response_accepts_zero_atoms_and_all_axes_without_fake_B(self) -> None:
        packet = {"profiles": [{"author_id": "a", "items": [], "evidence_pool": {}}]}
        result: dict[str, Any] = {
            "input_sha256": "digest",
            "atom_evaluations": [],
            "profile_evaluations": [
                {
                    "author_id": "a",
                    "response": "A",
                    "axis": axis,
                    "grade": "correct",
                    "error_types": [],
                    "severity": "none",
                    "evidence_refs": [],
                    "basis": "Unknown сохранено корректно",
                }
                for axis in AXES
            ],
        }
        validate_single(packet, result, "digest")
        result["profile_evaluations"][0]["response"] = "B"
        with self.assertRaises(ValueError):
            validate_single(packet, result, "digest")
        result["profile_evaluations"][0]["response"] = "A"
        result["profile_evaluations"].pop()
        with self.assertRaisesRegex(ValueError, "полностью"):
            validate_single(packet, result, "digest")

    def test_single_response_requires_real_atoms_and_consistent_errors_and_refs(self) -> None:
        packet = {
            "profiles": [
                {"author_id": "a", "items": [{"item_id": "i"}], "evidence_pool": {"e": {}}}
            ]
        }
        common = {
            "author_id": "a",
            "response": "A",
            "grade": "correct",
            "error_types": [],
            "severity": "none",
            "evidence_refs": ["e"],
            "basis": "Дословный источник",
        }
        result: dict[str, Any] = {
            "input_sha256": "digest",
            "atom_evaluations": [common | {"item_id": "i"}],
            "profile_evaluations": [common | {"axis": axis} for axis in AXES],
        }
        validate_single(packet, result, "digest")
        result["atom_evaluations"][0]["evidence_refs"] = ["missing"]
        with self.assertRaisesRegex(ValueError, "refs"):
            validate_single(packet, result, "digest")
        result["atom_evaluations"][0]["evidence_refs"] = ["e"]
        result["atom_evaluations"][0]["severity"] = "high"
        with self.assertRaisesRegex(ValueError, "Correct"):
            validate_single(packet, result, "digest")


if __name__ == "__main__":
    unittest.main()
