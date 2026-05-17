from pathlib import Path
import tempfile
import unittest

from nightshift.artifacts import ArtifactStore
from nightshift.reports import ReportGenerator
from nightshift.stages import StageResult
from nightshift.tasks import parse_tasks


TASK_MD = """# Tasks

- [ ] TASK-001: Report results

Description:
Write summaries.

Acceptance Criteria:
- Final notes explain status
- Run summary includes artifacts
"""


class ReportGeneratorTests(unittest.TestCase):
    def test_writes_final_notes_stage_results_and_run_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = ArtifactStore(root, ".nightshift", run_id="test-run")
            reporter = ReportGenerator(root, artifacts)
            task = parse_tasks(TASK_MD)[0]
            context_out = artifacts.write_stage_output(task.id, "context-out.md", "# Context Out\n")
            artifacts.run_log_path.write_text(
                "\n".join(
                    [
                        "2026-05-17T00:00:00Z | stage.start | Starting stage | stage_id=plan | stage_type=agent",
                        "2026-05-17T00:00:01Z | tool.call | Running repo lookup tool | path=. | pattern=def parse\\( | tool=grep",
                        "2026-05-17T00:00:02Z | stage.start | Starting stage | stage_id=implement | stage_type=file_writer",
                        "2026-05-17T00:00:03Z | tool.call | Running repo lookup tool | path=lisp.py | tool=read_file",
                        "2026-05-17T00:00:04Z | command.start | Starting command | command=python -m unittest | stage_id=test",
                    ]
                ),
                encoding="utf-8",
            )

            report = reporter.write_reports(
                task,
                "complete",
                "done",
                1,
                [
                    StageResult(
                        stage_id="test",
                        status="pass",
                        reason="ok",
                        output_path=".nightshift/runs/test-run/tasks/TASK-001/test-output.txt",
                    )
                ],
                context_out_path=context_out,
            )

            self.assertTrue(report.final_notes_path.exists())
            self.assertTrue(report.stage_results_path.exists())
            self.assertTrue(report.run_summary_path.exists())
            self.assertTrue(report.devlog_path.exists())
            self.assertIn("Retry count: 1", report.final_notes_path.read_text(encoding="utf-8"))
            self.assertIn("test", report.stage_results_path.read_text(encoding="utf-8"))
            self.assertIn("Final notes", report.run_summary_path.read_text(encoding="utf-8"))
            devlog = report.devlog_path.read_text(encoding="utf-8")
            self.assertIn("Tests reported", devlog)
            self.assertIn("Planner: searched", devlog)
            self.assertIn("Implementer: read `lisp.py`", devlog)
            self.assertIn("test: ran `python -m unittest`", devlog)


if __name__ == "__main__":
    unittest.main()
