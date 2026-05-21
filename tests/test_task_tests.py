from pathlib import Path
import tempfile
import unittest

from nightshift.config import validate_config
from nightshift.task_tests import check_task_test_files, missing_task_test_paths
from nightshift.tasks import parse_task_file


class TaskTestValidationTests(unittest.TestCase):
    def test_check_task_test_files_renders_task_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "agents").mkdir()
            (root / "agents" / "planner.md").write_text("Prompt", encoding="utf-8")
            (root / "tests").mkdir()
            (root / "tests" / "test_task001.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
            (root / "nightshift.yaml").write_text(
                "\n".join(
                    [
                        "project:",
                        "  name: task-test-validation",
                        "  root: .",
                        "  task_file: tasks.md",
                        "  artifact_dir: .nightshift",
                        "",
                        "safety:",
                        "  require_clean_worktree: false",
                        "  scoped_paths:",
                        "    - .",
                        "  allowed_commands:",
                        "    - python -m pytest -q tests/test_{task_id_compact}.py",
                        "  forbidden_commands:",
                        "    - rm -rf",
                        "",
                        "agents:",
                        "  planner:",
                        "    backend: command",
                        "    command: python -c \"print('ok')\"",
                        "    system_prompt: agents/planner.md",
                        "",
                        "pipeline:",
                        "  stages:",
                        "    - id: test",
                        "      type: command",
                        "      commands:",
                        "        - python -m pytest -q tests/test_{task_id_compact}.py",
                    ]
                ),
                encoding="utf-8",
            )
            (root / "tasks.md").write_text(
                """# Tasks

- [ ] TASK-001: One

Acceptance Criteria:
- passes

- [ ] TASK-002: Two

Acceptance Criteria:
- reports missing test
""",
                encoding="utf-8",
            )

            config = validate_config(root / "nightshift.yaml")
            tasks = parse_task_file(config.project.root, config.project.task_file)
            checks = check_task_test_files(config, tasks)

            self.assertEqual([check.path for check in checks], ["tests/test_task001.py", "tests/test_task002.py"])
            self.assertEqual(tuple(path.as_posix() for path in missing_task_test_paths(checks)), ("tests/test_task002.py",))


if __name__ == "__main__":
    unittest.main()
