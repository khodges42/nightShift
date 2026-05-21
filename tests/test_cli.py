from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class CliTests(unittest.TestCase):
    def test_run_all_keeps_completed_dependencies_in_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "dummy.md").write_text("Unused.", encoding="utf-8")
            (root / "nightshift.yaml").write_text(
                "\n".join(
                    [
                        "project:",
                        "  name: cli-test",
                        "  root: .",
                        "  task_file: tasks.md",
                        "  artifact_dir: .nightshift",
                        "",
                        "safety:",
                        "  require_clean_worktree: false",
                        "  scoped_paths:",
                        "    - .",
                        "  allowed_commands:",
                        "    - python -c \"print('ok')\"",
                        "  forbidden_commands:",
                        "    - rm -rf",
                        "",
                        "agents:",
                        "  dummy:",
                        "    backend: command",
                        "    command: python -c \"print('unused')\"",
                        "    system_prompt: dummy.md",
                        "",
                        "pipeline:",
                        "  max_task_retries: 0",
                        "  stages:",
                        "    - id: test",
                        "      type: command",
                        "      commands:",
                        "        - python -c \"print('ok')\"",
                        "      output: test-output.txt",
                    ]
                ),
                encoding="utf-8",
            )
            (root / "tasks.md").write_text(
                """# Tasks

- [x] TASK-001: Already complete

Acceptance Criteria:
- done

- [ ] TASK-002: Depends on completed task

Dependencies:
- TASK-001

Acceptance Criteria:
- runs
""",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "nightshift.cli",
                    "run",
                    "--config",
                    str(root / "nightshift.yaml"),
                    "--all",
                    "--no-animation",
                ],
                cwd=root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertIn("Completed: 1", completed.stdout)
            self.assertIn("- [x] TASK-002", (root / "tasks.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
