from pathlib import Path
import tempfile
import unittest

from nightshift.artifacts import ArtifactStore, default_run_id
from nightshift.errors import ArtifactError
from nightshift.init import init_project
from nightshift.tasks import parse_task_file


class ArtifactStoreTests(unittest.TestCase):
    def test_initialize_run_creates_base_artifact_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ArtifactStore(root, ".nightshift", run_id="test-run")

            store.initialize_run()

            self.assertTrue((root / ".nightshift").is_dir())
            self.assertTrue((root / ".nightshift" / "project-context.md").exists())
            self.assertTrue((root / ".nightshift" / "runs" / "test-run").is_dir())
            self.assertTrue((root / ".nightshift" / "runs" / "test-run" / "tasks").is_dir())
            self.assertTrue((root / ".nightshift" / "runs" / "test-run" / "run-summary.md").exists())

    def test_writes_config_task_stage_and_final_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root)
            task = parse_task_file(root, "tasks.md")[0]
            store = ArtifactStore(root, ".nightshift", run_id="test-run")

            config_path = store.write_config_snapshot(root / "nightshift.yaml")
            task_path = store.write_task_snapshot(task)
            stage_path = store.write_stage_output(task.id, "plan.md", "# Plan\n")
            command_path = store.write_command_output(task.id, "test-output.txt", "ok\n")
            notes_path = store.write_final_task_notes(task.id, "# Notes\n")

            self.assertTrue(config_path.exists())
            self.assertIn("project:", config_path.read_text(encoding="utf-8"))
            self.assertTrue(task_path.exists())
            self.assertIn(task.id, task_path.read_text(encoding="utf-8"))
            self.assertEqual(stage_path.read_text(encoding="utf-8"), "# Plan\n")
            self.assertEqual(command_path.read_text(encoding="utf-8"), "ok\n")
            self.assertEqual(notes_path.read_text(encoding="utf-8"), "# Notes\n")

    def test_stage_output_cannot_escape_task_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ArtifactStore(root, ".nightshift", run_id="test-run")

            with self.assertRaisesRegex(ArtifactError, "escapes task directory"):
                store.write_stage_output("TASK-001", "../leak.txt", "nope")

    def test_run_id_and_task_id_must_be_safe_path_segments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            with self.assertRaisesRegex(ArtifactError, "run id contains unsafe"):
                ArtifactStore(root, ".nightshift", run_id="../run")

            store = ArtifactStore(root, ".nightshift", run_id="safe-run")
            with self.assertRaisesRegex(ArtifactError, "task id contains unsafe"):
                store.create_task_dir("../TASK-001")

    def test_default_run_id_has_subsecond_precision(self) -> None:
        run_id = default_run_id()

        self.assertRegex(run_id, r"^\d{8}T\d{6}\.\d{6}Z$")


if __name__ == "__main__":
    unittest.main()
