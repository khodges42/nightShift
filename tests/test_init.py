from pathlib import Path
import tempfile
import unittest

from nightshift.errors import InitError
from nightshift.init import available_templates, init_project


class InitProjectTests(unittest.TestCase):
    def test_init_creates_expected_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            written = init_project(root)

            self.assertIn(root / "nightshift.yaml", written)
            self.assertTrue((root / "nightshift.yaml").exists())
            self.assertTrue((root / "tasks.md").exists())
            self.assertTrue((root / "agents" / "planner.md").exists())
            self.assertTrue((root / "agents" / "implementer.md").exists())
            self.assertTrue((root / "agents" / "reviewer.md").exists())

    def test_init_refuses_to_overwrite_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root)

            with self.assertRaises(InitError):
                init_project(root)

    def test_init_can_overwrite_with_force(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root)
            (root / "tasks.md").write_text("changed", encoding="utf-8")

            init_project(root, force=True)

            self.assertIn("TASK-001", (root / "tasks.md").read_text(encoding="utf-8"))

    def test_init_imageboard_template_creates_control_and_source_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            written = init_project(root, template="tutorial-imageboard")

            self.assertIn(root / "nightshift.yaml", written)
            self.assertTrue((root / ".nightshift" / "tasks.md").exists())
            self.assertTrue((root / ".nightshift" / "agents" / "planner.md").exists())
            self.assertTrue((root / "src" / "imageboard" / ".gitkeep").exists())
            self.assertTrue((root / "tests" / ".gitkeep").exists())
            self.assertIn(
                "task_file: .nightshift/tasks.md",
                (root / "nightshift.yaml").read_text(encoding="utf-8"),
            )

    def test_available_templates_includes_filesystem_templates(self) -> None:
        self.assertIn("basic", available_templates())
        self.assertIn("real-long-running", available_templates())
        self.assertIn("real-simple", available_templates())
        self.assertIn("tutorial-imageboard", available_templates())
        self.assertIn("tutorial-pastebin", available_templates())

    def test_init_pastebin_template_creates_skeleton_and_tdd_model_fallback_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            init_project(root, template="tutorial-pastebin")

            config = (root / "nightshift.yaml").read_text(encoding="utf-8")
            self.assertTrue((root / ".nightshift" / "tasks.md").exists())
            self.assertTrue((root / ".nightshift" / "agents" / "test-writer.md").exists())
            self.assertTrue((root / "src" / "pastebin_app" / "app.py").exists())
            self.assertTrue((root / "tests" / ".gitkeep").exists())
            self.assertFalse((root / "tests" / "test_pastebin.py").exists())
            self.assertIn("type: semantic_context", config)
            self.assertIn("id: write_tests", config)
            self.assertIn("id: review_tests", config)
            self.assertIn("max_task_retries: 6", config)
            self.assertIn("implementer_qwen", config)
            self.assertIn("carstenuhlig/omnicoder-9b", config)
            self.assertIn("deepseek-coder-v2:16b", config)

    def test_pastebin_example_tutorial_docs_exist(self) -> None:
        root = Path(__file__).resolve().parents[1]
        tutorial = root / "examples" / "tutorial" / "03-pastebin"

        self.assertTrue((tutorial / "README.md").exists())
        self.assertTrue((tutorial / "tasks.md").exists())
        self.assertTrue((tutorial / "nightshift.yaml").exists())
        self.assertIn(
            "nightshift init --template tutorial-pastebin",
            (tutorial / "README.md").read_text(encoding="utf-8"),
        )

    def test_init_rejects_unknown_template(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(InitError, "Unknown template"):
                init_project(Path(directory), template="missing")


if __name__ == "__main__":
    unittest.main()
