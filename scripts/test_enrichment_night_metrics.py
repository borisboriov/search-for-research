"""Учёт физической работы: копии receipts и вложенные токены не удваиваются."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from enrichment_batch import encoded, immutable
from enrichment_night_metrics import physical_jobs, profile_metrics, tokens, total


class NightMetricsTests(unittest.TestCase):
    def test_proven_empty_gate_has_zero_usage_without_a_fabricated_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.json"
            immutable(source, encoded({"items": [], "evidence_pool": {}, "profile_evidence": {}}))
            immutable(root / "results/a.json", encoded({}))
            wrapper = {
                "input_path": str(source),
                "classifications": {},
                "rejected_candidates": 0,
                "result": {"items": [], "profile_assessments": {}},
                "verifier_receipt": None,
                "model_not_called": True,
                "collector_receipt": {
                    "wall_elapsed_seconds": 10,
                    "model_requests": 1,
                    "budget": {},
                    "usage_complete": True,
                    "token_usage": {
                        "input": 20,
                        "cacheRead": 0,
                        "cacheWrite": 0,
                        "output": 10,
                        "totalTokens": 30,
                    },
                },
            }
            with (
                patch("enrichment_night_metrics.verified_sample", return_value=[{"id": "a"}]),
                patch("enrichment_night_metrics.checked_result", return_value=wrapper),
            ):
                row = profile_metrics(root)[0]
                self.assertTrue(row["model_not_called"])
                self.assertEqual(row["verifier_tokens"]["input_plus_output"], 0)
                self.assertEqual(row["verifier_seconds"], 0)
                self.assertEqual(row["pipeline_seconds"], 10)
                wrapper["model_not_called"] = False
                with self.assertRaisesRegex(ValueError, "доказанного"):
                    profile_metrics(root)

    def test_copied_collector_receipts_are_one_physical_job(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            receipt = {
                "agent_id": "pi-cli:one",
                "token_usage": {
                    "input": 100,
                    "cacheRead": 40,
                    "cacheWrite": 0,
                    "output": 30,
                    "reasoning": 20,
                    "totalTokens": 170,
                },
                "usage_complete": True,
                "wall_elapsed_seconds": 12,
                "model_requests": 5,
            }
            for root in ("one", "copy"):
                immutable(
                    parent / root / "runs" / "a" / "collector" / "receipt.json", encoded(receipt)
                )
            with patch("enrichment_night_metrics.NIGHT_ROOTS", ("one", "copy")):
                jobs = physical_jobs(parent)
                self.assertEqual(len(jobs), 1)
                self.assertEqual(len(jobs[0]["receipt_copies"]), 2)
                summed = total(jobs)
                self.assertEqual(summed["tokens"]["input_tokens"], 140)
                self.assertEqual(summed["tokens"]["input_plus_output"], 170)
                self.assertEqual(summed["model_requests"], 5)
                receipt["wall_elapsed_seconds"] = 13
                (parent / "copy" / "runs" / "a" / "collector" / "receipt.json").write_bytes(
                    encoded(receipt)
                )
                with self.assertRaisesRegex(ValueError, "разными receipts"):
                    physical_jobs(parent)

    def test_native_timeout_without_receipt_is_counted_with_unknown_usage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            run = parent / "one" / "runs" / "a" / "native_verifier"
            immutable(
                run / "started.json",
                encoded(
                    {
                        "started_at_epoch": 100,
                        "requested_config": {"model": "gpt-6.1-sol", "effort": "high"},
                    }
                ),
            )
            immutable(
                run / "finished.json",
                encoded(
                    {
                        "finished_at_epoch": 700,
                        "timed_out": True,
                        "exit_code": -9,
                        "full_job_usage": None,
                    }
                ),
            )
            with patch("enrichment_night_metrics.NIGHT_ROOTS", ("one",)):
                jobs = physical_jobs(parent)
            summed = total(jobs)
            self.assertEqual(summed["jobs"], 1)
            self.assertEqual(summed["receipt_missing_jobs"], 1)
            self.assertEqual(summed["wall_seconds"], 600)
            self.assertFalse(summed["usage_complete"])
            self.assertIsNone(summed["tokens"]["input_plus_output"])
            self.assertIsNone(summed["model_requests"])
            self.assertEqual(summed["known_token_subtotals"]["input_plus_output"], 0)
            immutable(
                run / "events.jsonl",
                encoded(
                    {
                        "type": "turn.completed",
                        "usage": {
                            "input_tokens": 100,
                            "cached_input_tokens": 20,
                            "output_tokens": 30,
                        },
                    }
                ),
            )
            # JSONL events are one JSON per line, not an indented JSON object.
            (run / "events.jsonl").write_text(
                '{"type":"turn.completed","usage":{"input_tokens":100,"cached_input_tokens":20,"output_tokens":30}}\n'
            )
            with patch("enrichment_night_metrics.NIGHT_ROOTS", ("one",)):
                known = total(physical_jobs(parent))
            self.assertIsNone(known["tokens"]["input_plus_output"])
            self.assertEqual(known["known_token_subtotals"]["input_plus_output"], 130)

    def test_comparison_and_judge_attempts_are_kept_as_separate_stages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            for relative in ("runs/a/baseline", "judges/packet-01"):
                run = parent / "one" / relative
                immutable(run / "started.json", encoded({"started_at_epoch": 100}))
                immutable(
                    run / "finished.json", encoded({"finished_at_epoch": 200, "exit_code": -9})
                )
            with patch("enrichment_night_metrics.NIGHT_ROOTS", ("one",)):
                jobs = physical_jobs(parent)
            self.assertEqual({row["stage"] for row in jobs}, {"comparison_verifier", "judge"})
            self.assertEqual(total(jobs)["jobs"], 2)
            self.assertIsNone(next(row for row in jobs if row["stage"] == "judge")["author_id"])

    def test_native_cached_and_reasoning_are_subsets(self) -> None:
        result = tokens(
            {
                "tokens": {
                    "input_tokens": 100,
                    "cached_input_tokens": 40,
                    "output_tokens": 30,
                    "reasoning_output_tokens": 20,
                }
            },
            "native_verifier",
        )
        self.assertEqual(result["input_plus_output"], 130)
        self.assertEqual(result["cached_input_tokens"], 40)
        self.assertEqual(result["reasoning_output_tokens"], 20)


if __name__ == "__main__":
    unittest.main()
