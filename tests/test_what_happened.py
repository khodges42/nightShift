from pathlib import Path
import tempfile
import unittest

from nightshift.what_happened import build_what_happened


class WhatHappenedTests(unittest.TestCase):
    def test_build_what_happened_summarizes_latest_failed_task(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task_dir = root / ".nightshift" / "runs" / "20260520T000000.000000Z" / "tasks" / "TASK-001"
            diagnostics = task_dir / "diagnostics"
            diagnostics.mkdir(parents=True)
            run_dir = task_dir.parents[1]
            (run_dir / "run-summary.md").write_text(
                "# Run Summary\n\n- Task: TASK-001\n- Status: failed\n- Retry count: 1\n- Reason: test failed\n",
                encoding="utf-8",
            )
            (task_dir / "stage-results.md").write_text(
                "\n".join(
                    [
                        "# Stage Results",
                        "",
                        "## test",
                        "",
                        "Status: fail",
                        "Reason: Command exited with code 2: python -m pytest -q",
                        "Output: test-output-1.txt",
                    ]
                ),
                encoding="utf-8",
            )
            (task_dir / "test-output-1.txt").write_text(
                "Command: `python -m pytest -q`\nExit code: 2\nModuleNotFoundError: No module named 'deaddrop_app'\n",
                encoding="utf-8",
            )
            (diagnostics / "test-failure-retry-1.md").write_text(
                "Failure category: missing dependency\nProbable root cause: Runtime cannot import required package.\n",
                encoding="utf-8",
            )
            (task_dir / "repair-1.patch").write_text(
                "diff --git a/src/app.py b/src/app.py\n--- a/src/app.py\n+++ b/src/app.py\n",
                encoding="utf-8",
            )

            report = build_what_happened(root, ".nightshift")

            self.assertIn("Status: failed", report.content)
            self.assertIn("ModuleNotFoundError", report.content)
            self.assertIn("missing dependency", report.content)
            self.assertIn("repair-1.patch", report.content)


if __name__ == "__main__":
    unittest.main()
