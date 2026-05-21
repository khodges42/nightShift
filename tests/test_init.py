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
        self.assertIn("tutorial-deaddrop", available_templates())

    def test_init_DeadDrop_template_creates_skeleton_and_qwen3_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            init_project(root, template="tutorial-deaddrop")

            config = (root / "nightshift.yaml").read_text(encoding="utf-8")
            self.assertTrue((root / ".nightshift" / "tasks.md").exists())
            self.assertTrue((root / ".nightshift" / "agents" / "test-writer.md").exists())
            self.assertTrue((root / "src" / "deaddrop_app" / "app.py").exists())
            self.assertTrue((root / "tests" / "test_task001.py").exists())
            self.assertTrue((root / "tests" / ".gitkeep").exists())
            self.assertFalse((root / "tests" / "test_deaddrop.py").exists())
            self.assertIn("def create_app(database_path", (root / "src" / "deaddrop_app" / "app.py").read_text(encoding="utf-8"))
            self.assertIn("type: semantic_context", config)
            self.assertNotIn("id: write_tests", config)
            self.assertNotIn("id: review_tests", config)
            self.assertIn("python -m pytest -q tests/test_{task_id_compact}.py", config)
            self.assertIn("max_task_retries: 6", config)
            self.assertIn("implementer:", config)
            self.assertIn("qwen3-coder:30b", config)
            self.assertIn("num_ctx: 8192", config)
            self.assertIn("num_predict: 4096", config)
            self.assertNotIn("agent_pool:", config)
            self.assertNotIn("carstenuhlig/omnicoder-9b", config)
            self.assertNotIn("deepseek-coder-v2:16b", config)

    def test_deaddrop_example_tutorial_docs_exist(self) -> None:
        root = Path(__file__).resolve().parents[1]
        tutorial = root / "examples" / "tutorial" / "03-deaddrop"

        self.assertTrue((tutorial / "README.md").exists())
        self.assertTrue((tutorial / "tasks.md").exists())
        self.assertTrue((tutorial / "nightshift.yaml").exists())
        self.assertIn(
            "nightshift init --template tutorial-deaddrop",
            (tutorial / "README.md").read_text(encoding="utf-8"),
        )

    def test_init_rejects_unknown_template(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(InitError, "Unknown template"):
                init_project(Path(directory), template="missing")


if __name__ == "__main__":
    unittest.main()
