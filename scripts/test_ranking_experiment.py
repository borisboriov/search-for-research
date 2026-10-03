"""Ranking experiment contracts, using fake models and small in-memory rankings."""

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Any, ClassVar
from unittest.mock import patch

from ranking_experiment import (
    VARIANTS,
    blind_pool,
    fuse,
    measure,
    query_inputs,
    rss_bytes,
    run_worker,
    write_json,
    write_jsonl,
)

from sfr_match.evalset import profile_fingerprint
from sfr_match.index import IndexMeta
from sfr_match.search import Hit


def hit(author: str, score: float = 1.0, text: str = "displayed profile") -> Hit:
    return Hit(1, author, "name", score, [], text)


class FakeDense:
    meta = IndexMeta("frida", "ai-forever/FRIDA", "dense", True, 2, 2, 0)
    docs: ClassVar[list[dict[str, Any]]] = [{"id": "a"}, {"id": "b"}]
    calls: list[tuple[str, int]]
    searcher = type("Searcher", (), {"name": "fake"})()
    embedder = None

    def __init__(self, *args: Any) -> None:
        self.calls = []

    def warmup(self) -> None:
        pass

    def search(self, text: str, k: int) -> list[Hit]:
        self.calls.append((text, k))
        return [hit("a", 0.4), replace(hit("b", 0.2), rank=2)][:k]


class FakeLexical:
    def __init__(self, *args: Any) -> None:
        pass

    def search(self, text: str, k: int) -> list[Hit]:
        return [hit("b", 1.0), hit("a", 0)]


class RankingExperimentTests(unittest.TestCase):
    def test_fusion_ties_zero_matches_and_no_mutation(self) -> None:
        dense = [hit("b"), hit("a")]
        lexical = [hit("a"), hit("b")]
        self.assertEqual([item.author_id for item in fuse(dense, lexical)], ["a", "b"])
        self.assertEqual(fuse(dense, [hit("x", 0), hit("z", -1)]), fuse(dense, []))
        self.assertEqual(dense[0].score, 1)
        self.assertEqual(fuse([], []), [])
        self.assertEqual(fuse(dense, lexical, 0), [])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            fuse([hit("a"), hit("a")], [])

    def test_blind_pool_sorted_deduplicated_exact_displayed_text(self) -> None:
        queries = [{"id": "q", "text": "query"}]
        runs: list[dict[str, Any]] = [
            {
                "results": [
                    {
                        "query_id": "q",
                        "hits": [
                            {
                                "author_id": "b",
                                "profile_text": "display",
                                "name": "B",
                                "score": 0.8,
                            },
                            {"author_id": "a", "profile_text": "other", "name": "A", "rank": 1},
                        ],
                    }
                ]
            }
        ]
        pool = blind_pool(runs * 2, queries)
        self.assertEqual([item["author_id"] for item in pool], ["a", "b"])
        self.assertEqual(pool[1]["profile_fp"], profile_fingerprint("display"))
        self.assertTrue(all(not {"rank", "score", "variant", "judged"} & set(row) for row in pool))
        runs[0]["results"][0]["hits"][0]["profile_text"] = "different"
        with self.assertRaisesRegex(ValueError, "inconsistent snapshot"):
            blind_pool(
                [
                    {
                        "results": [
                            {
                                "query_id": "q",
                                "hits": [
                                    {"author_id": "b", "profile_text": "display", "name": "B"}
                                ],
                            }
                        ]
                    },
                    *runs,
                ],
                queries,
            )

    def test_worker_baseline_matches_api_strip_and_k(self) -> None:
        backend = FakeDense()
        index_dir = Path(self.enterContext(tempfile.TemporaryDirectory()))
        queries = [{"id": "q", "text": "  query long enough  "}]
        with patch("ranking_experiment.DenseBackend", return_value=backend):
            baseline = run_worker(index_dir, queries, "baseline")
        self.assertEqual(backend.calls, [("query long enough", 5), ("query long enough", 50)])
        self.assertEqual([row["author_id"] for row in baseline["results"][0]["hits"]], ["a", "b"])
        backend = FakeDense()
        with (
            patch("ranking_experiment.DenseBackend", return_value=backend),
            patch("ranking_experiment.Bm25Backend", FakeLexical),
        ):
            hybrid = run_worker(index_dir, queries, "hybrid")
        self.assertEqual(backend.calls, [("query long enough", 50)])
        self.assertEqual(hybrid["results"][0]["hits"][0]["author_id"], "b")
        with patch("ranking_experiment.DenseBackend", FakeDense):
            error = run_worker(index_dir, [{"id": "q", "text": "x"}], "baseline")
        self.assertEqual(error["results"][0]["error"]["type"], "QueryError")
        self.assertEqual(error["results"][0]["hits"], [])

    def test_units_exclusive_writes_and_duplicate_queries(self) -> None:
        self.assertEqual(rss_bytes(12, "darwin"), 12)
        self.assertEqual(rss_bytes(12, "linux"), 12 * 1024)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "q.jsonl"
            write_jsonl(path, [{"id": "q", "text": "some query", "expect": "in-domain"}])
            with self.assertRaises(FileExistsError):
                write_json(path, {})
            with self.assertRaisesRegex(ValueError, "duplicate query"):
                query_inputs([path, path])

    def test_measure_requires_fresh_complete_labels_and_bounds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            queries = [{"id": "q", "text": "query", "group": "external", "expect": "in-domain"}]
            write_json(root / "queries.json", queries)
            rows = [
                {
                    "query_id": "q",
                    "error": None,
                    "latency_ms": 1,
                    "hits": [{"author_id": "a", "name": "A", "profile_text": "text", "score": 0.4}],
                }
            ]
            for variant in VARIANTS:
                for repeat in range(1, 4):
                    write_json(
                        root / f"{variant}-{repeat}.json",
                        {
                            "variant": variant,
                            "results": rows,
                            "build_seconds": 1,
                            "warmup_seconds": 2,
                            "peak_rss_bytes": 3,
                        },
                    )
            labels = root / "labels.jsonl"
            write_jsonl(labels, [])
            with self.assertRaisesRegex(ValueError, "missing/stale"):
                measure(root, labels, root / "empty.json")
            labels.unlink()
            write_jsonl(
                labels,
                [
                    {
                        "query_id": "q",
                        "author_id": "a",
                        "grade": 2,
                        "alternate_grade": 1,
                        "judge": "gpt-6-astra/max (sfr-judge)",
                        "profile_fp": "wrong",
                    }
                ],
            )
            with self.assertRaisesRegex(ValueError, "missing/stale"):
                measure(root, labels, root / "stale.json")
            labels.unlink()
            write_jsonl(
                labels,
                [
                    {
                        "query_id": "q",
                        "author_id": "a",
                        "grade": 2,
                        "alternate_grade": 1,
                        "judge": "gpt-6-astra/max (sfr-judge)",
                        "profile_fp": profile_fingerprint("text"),
                    }
                ],
            )
            measure(root, labels, root / "metrics.json")
            metrics = json.loads((root / "metrics.json").read_text())
            self.assertTrue(metrics["per_query"][0]["success@1"])
            self.assertFalse(metrics["per_query"][0]["success@1_lower"])
            self.assertTrue(metrics["per_query"][0]["success@1_upper"])
            self.assertEqual(metrics["groups"]["baseline/external/in-domain"]["n"], 1)
            with self.assertRaises(FileExistsError):
                measure(root, labels, root / "metrics.json")
            changed_path = root / "hybrid-3.json"
            changed = json.loads(changed_path.read_text())
            changed["model_revision"] = "different"
            changed_path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "inconsistent run snapshot"):
                measure(root, labels, root / "mismatch.json")
            changed.pop("model_revision")
            changed["results"] = []
            changed_path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "missing, extra or duplicate"):
                measure(root, labels, root / "missing-query.json")


if __name__ == "__main__":
    unittest.main()
