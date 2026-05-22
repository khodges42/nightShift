from pathlib import Path
import tempfile
import unittest

from nightshift.errors import NightShiftError
from nightshift.sandbox_run import format_sandbox_run_result, run_sandbox_project


class SandboxRunTests(unittest.TestCase):
    def test_sandbox_run_dry_run_copies_existing_project_and_keeps_animation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "nightshift.yaml").write_text("project:\n  name: demo\n", encoding="utf-8")
            (source / "pyproject.toml").write_text("[project]\nname = 'demo'\nversion = '0.1.0'\n", encoding="utf-8")
            (source / ".nightshift").mkdir()
            (source / ".nightshift" / "tasks.md").write_text("- [ ] TASK-001: Demo\n\nAcceptance Criteria:\n- done\n", encoding="utf-8")
            (source / ".nightshift" / "runs").mkdir()
            (source / ".nightshift" / "runs" / "old.txt").write_text("old artifact", encoding="utf-8")
            output = root / "sandbox"

            result = run_sandbox_project(
                source,
                output=output,
                task="TASK-001",
                dry_run=True,
            )

            rendered = format_sandbox_run_result(result)
            self.assertIn("Dry run: true", rendered)
            self.assertEqual(result.project_dir, output / "project")
            self.assertTrue((output / "project" / "nightshift.yaml").exists())
            self.assertTrue((output / "project" / ".nightshift" / "tasks.md").exists())
            self.assertFalse((output / "project" / ".nightshift" / "runs").exists())
            self.assertIn("--animation", result.command)
            self.assertNotIn("--no-animation", result.command)
            self.assertIn("TASK-001", result.command)

    def test_sandbox_run_timestamped_uses_integ_runs_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "nightshift.yaml").write_text("project:\n  name: demo\n", encoding="utf-8")
            (source / "pyproject.toml").write_text("[project]\nname = 'demo'\nversion = '0.1.0'\n", encoding="utf-8")

            result = run_sandbox_project(
                source,
                root=root,
                timestamped=True,
                all_tasks=True,
                dry_run=True,
            )

            self.assertEqual(result.directory.parent, root / "integ_runs")
            self.assertIn("--all", result.command)

    def test_sandbox_run_requires_output_or_timestamped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.mkdir()
            (source / "nightshift.yaml").write_text("project:\n  name: demo\n", encoding="utf-8")

            with self.assertRaisesRegex(NightShiftError, "provide --output or --timestamped"):
                run_sandbox_project(source, task="TASK-001", dry_run=True)


if __name__ == "__main__":
    unittest.main()
