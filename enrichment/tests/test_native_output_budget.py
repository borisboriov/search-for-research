"""Task-owned native output caps do not affect client files or stdin deadlines."""

import io
import subprocess
import sys
import time
import unittest

from sfr_enrichment.native import bounded_output_run


class NativeOutputBudgetTests(unittest.TestCase):
    def test_small_stream_is_exact(self) -> None:
        out, err = io.BytesIO(), io.BytesIO()
        result = bounded_output_run(
            [sys.executable, "-c", "import sys; sys.stdout.write('exact')"],
            b"",
            out,
            err,
            2,
            100,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(out.getvalue(), b"exact")
        self.assertEqual(err.getvalue(), b"")

    def test_large_task_stream_is_rejected_without_overwrite(self) -> None:
        out, err = io.BytesIO(), io.BytesIO()
        with self.assertRaisesRegex(ValueError, "stream cap"):
            bounded_output_run(
                [sys.executable, "-c", "import sys; sys.stdout.write('x'*1000)"],
                b"",
                out,
                err,
                2,
                10,
            )
        self.assertLessEqual(len(out.getvalue()), 10)

    def test_timeout_includes_blocked_stdin(self) -> None:
        out, err = io.BytesIO(), io.BytesIO()
        started = time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired):
            bounded_output_run(
                [sys.executable, "-c", "import time; time.sleep(5)"],
                b"x" * 1_000_000,
                out,
                err,
                0.05,
                100,
            )
        self.assertLess(time.monotonic() - started, 2)


if __name__ == "__main__":
    unittest.main()
