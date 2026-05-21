from pathlib import Path
import os
import tempfile
import unittest

from nightshift.integ import create_integration_run
from nightshift.integ_setup import IntegrationSetupResult, format_setup_result, setup_python_project


class IntegrationSetupTests(unittest.TestCase):
    def test_setup_python_project_dry_run_uses_integration_venv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = create_integration_run(root, template="tutorial-deaddrop")

            result = setup_python_project(
                run.directory / "project",
                nightshift_root=Path(__file__).resolve().parents[1],
                extras=("pytest", "flask"),
                dry_run=True,
            )

            self.assertEqual(result.venv_dir, run.venv_dir)
            self.assertFalse(result.created_venv)
            rendered = format_setup_result(result)
            self.assertIn("pip install -e", rendered)
            self.assertIn("pytest", rendered)
            self.assertIn("flask", rendered)
            self.assertTrue(any("nightshift.cli validate" in " ".join(command.args) for command in result.commands))
            self.assertTrue((run.directory / "project" / ".git").exists())

    def test_setup_python_project_dry_run_creates_project_local_venv_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            project.mkdir()
            (project / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")

            result = setup_python_project(
                project,
                nightshift_root=Path(__file__).resolve().parents[1],
                extras=(),
                dry_run=True,
            )

            self.assertEqual(result.venv_dir, project.parent / ".venv")
            self.assertTrue(result.created_venv)

    def test_format_setup_result_includes_activation_hint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = create_integration_run(root, template="tutorial-deaddrop")

            result = setup_python_project(
                run.directory / "project",
                nightshift_root=Path(__file__).resolve().parents[1],
                extras=(),
                dry_run=True,
            )
            rendered = format_setup_result(IntegrationSetupResult(
                project_dir=result.project_dir,
                venv_dir=result.venv_dir,
                python=result.python,
                created_venv=result.created_venv,
                commands=result.commands,
                dry_run=False,
            ))

            self.assertIn("Activate", rendered)
            self.assertIn("Activate.ps1" if os.name == "nt" else "bin", rendered)


if __name__ == "__main__":
    unittest.main()
