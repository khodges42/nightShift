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
            artifacts.run_summary_path.write_text("# Summary\n\nok", encoding="utf-8")

            runs = list_runs(root / ".nightshift")
            content = read_artifact(root / ".nightshift" / "runs" / "test-run", "run-summary.md")
            escaped = read_artifact(root / ".nightshift" / "runs" / "test-run", "../project-context.md")

            self.assertEqual(len(runs), 1)
            self.assertIn("ok", content)
            self.assertIn("escapes", escaped)


if __name__ == "__main__":
    unittest.main()
