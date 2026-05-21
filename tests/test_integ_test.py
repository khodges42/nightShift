from pathlib import Path
import tempfile
import unittest

from nightshift.integ_report import build_integration_report, format_integration_report
from nightshift.integ_test import format_integration_test_result, run_integration_test


class IntegrationTestCommandTests(unittest.TestCase):
    def test_run_integration_test_dry_run_builds_task_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run_integration_test(
                directory,
                template="tutorial-pastebin",
                task="TASK-001",
                dry_run=True,
            )

            rendered = format_integration_test_result(result)
            self.assertIn("Dry run: true", rendered)
            self.assertIn("TASK-001", " ".join(result.command))
            self.assertTrue((result.run.directory / "project" / "nightshift.yaml").exists())

    def test_build_integration_report_summarizes_latest_task_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            summary = root / "integ_runs" / "20260521T000000.000000Z" / "project" / ".nightshift" / "runs" / "run1" / "tasks" / "TASK-001" / "run-summary.md"
            summary.parent.mkdir(parents=True)
            summary.write_text(
                "\n".join(
                    [
                        "# Run Summary",
                        "",
                        "- Task: TASK-001",
                        "- Status: complete",
                        "- Retry count: 1",
                        "- Reason: Done.",
                    ]
                ),
                encoding="utf-8",
            )

            report = build_integration_report(root)
            rendered = format_integration_report(report)

            self.assertIn("TASK-001 complete after 1 retries", rendered)
            self.assertIn("Reason: Done.", rendered)


if __name__ == "__main__":
    unittest.main()
