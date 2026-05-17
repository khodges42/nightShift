from pathlib import Path
import tempfile
import unittest

from nightshift.artifacts import ArtifactStore
from nightshift.web import list_runs, read_artifact, render_dashboard


class WebDashboardTests(unittest.TestCase):
    def test_render_dashboard_handles_missing_runs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            html = render_dashboard(Path(directory) / ".nightshift")

            self.assertIn("No runs found", html)

    def test_lists_runs_and_reads_artifacts_safely(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = ArtifactStore(root, ".nightshift", run_id="test-run")
            artifacts.initialize_run()
            artifacts.run_summary_path.write_text("# Summary\n\n- Status: failed\n\nok", encoding="utf-8")
            (artifacts.run_dir / "devlog.md").write_text("# Devlog\n\nPlanner proposed:\n- do this", encoding="utf-8")
            artifacts.run_log_path.write_text(
                "\n".join(f"line {index}" for index in range(120)),
                encoding="utf-8",
            )

            runs = list_runs(root / ".nightshift")
            content = read_artifact(root / ".nightshift" / "runs" / "test-run", "run-summary.md")
            escaped = read_artifact(root / ".nightshift" / "runs" / "test-run", "../project-context.md")
            dashboard = render_dashboard(root / ".nightshift")

            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0].status, "failed")
            self.assertEqual(len(runs[0].log_tail), 100)
            self.assertIn("devlog.md", runs[0].artifacts)
            self.assertIn("ok", content)
            self.assertIn("escapes", escaped)
            self.assertIn("Log Tail", dashboard)
            self.assertIn("Planner proposed", dashboard)
            self.assertIn("FAILED", dashboard)
            self.assertIn("artifact-link", dashboard)
            self.assertIn("line 119", dashboard)
            self.assertNotIn("line 19\n", dashboard)


if __name__ == "__main__":
    unittest.main()
