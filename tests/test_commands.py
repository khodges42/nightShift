from pathlib import Path
import tempfile
import unittest

from nightshift.artifacts import ArtifactStore
from nightshift.commands import CommandExecutor
from nightshift.commands import CommandRun, format_command_runs
from nightshift.config import SafetyConfig, StageConfig
from nightshift.errors import CommandError


PASSING_COMMAND = 'python -c "print(\'ok\')"'
FAILING_COMMAND = 'python -c "import sys; print(\'bad\'); sys.exit(7)"'


class CommandExecutorTests(unittest.TestCase):
    def test_passing_command_stage_returns_pass_and_writes_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = ArtifactStore(root, ".nightshift", run_id="test-run")
            executor = CommandExecutor(
                root,
                SafetyConfig(
                    require_clean_worktree=False,
                    scoped_paths=(".",),
                    allowed_commands=(PASSING_COMMAND,),
                    forbidden_commands=("rm -rf",),
                ),
                artifacts,
            )
            stage = StageConfig(
                id="test",
                type="command",
                commands=(PASSING_COMMAND,),
                output="test-output.txt",
            )

            result = executor.run_stage(stage, "TASK-001")

            self.assertEqual(result.status, "pass")
            output_path = root / result.output_path
            self.assertTrue(output_path.exists())
            output = output_path.read_text(encoding="utf-8")
            self.assertIn("Exit code: 0", output)
            self.assertIn("ok", output)

    def test_failing_command_stage_returns_fail_and_writes_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = ArtifactStore(root, ".nightshift", run_id="test-run")
            executor = CommandExecutor(
                root,
                SafetyConfig(
                    require_clean_worktree=False,
                    scoped_paths=(".",),
                    allowed_commands=(FAILING_COMMAND,),
                    forbidden_commands=("rm -rf",),
                ),
                artifacts,
            )
            stage = StageConfig(
                id="test",
                type="command",
                commands=(FAILING_COMMAND,),
                output="test-output.txt",
            )

            result = executor.run_stage(stage, "TASK-001")

            self.assertEqual(result.status, "fail")
            self.assertIn("code 7", result.reason)
            output = (root / result.output_path).read_text(encoding="utf-8")
            self.assertIn("Exit code: 7", output)
            self.assertIn("bad", output)

    def test_unallowlisted_command_is_rejected_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executor = CommandExecutor(
                root,
                SafetyConfig(
                    require_clean_worktree=False,
                    scoped_paths=(".",),
                    allowed_commands=(PASSING_COMMAND,),
                    forbidden_commands=("rm -rf",),
                ),
                ArtifactStore(root, ".nightshift", run_id="test-run"),
            )

            with self.assertRaisesRegex(CommandError, "not allowlisted"):
                executor.run_command(FAILING_COMMAND)

    def test_command_timeout_returns_failed_stage_and_writes_output(self) -> None:
        slow_command = 'python -c "import time; print(\'start\'); time.sleep(2)"'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = ArtifactStore(root, ".nightshift", run_id="test-run")
            executor = CommandExecutor(
                root,
                SafetyConfig(
                    require_clean_worktree=False,
                    scoped_paths=(".",),
                    allowed_commands=(slow_command,),
                    forbidden_commands=("rm -rf",),
                ),
                artifacts,
                timeout_seconds=0.1,
            )
            stage = StageConfig(
                id="test",
                type="command",
                commands=(slow_command,),
                output="test-output.txt",
            )

            result = executor.run_stage(stage, "TASK-001")

            self.assertEqual(result.status, "fail")
            self.assertIn("timed out", result.reason)
            output = (root / result.output_path).read_text(encoding="utf-8")
            self.assertIn("Timed out: true", output)

    def test_command_stage_can_run_without_shell_and_with_working_dir(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            work.mkdir()
            command = 'python -c "import pathlib; print(pathlib.Path.cwd().name)"'
            executor = CommandExecutor(
                root,
                SafetyConfig(
                    require_clean_worktree=False,
                    scoped_paths=(".",),
                    allowed_commands=(command,),
                    forbidden_commands=("rm -rf",),
                ),
                ArtifactStore(root, ".nightshift", run_id="test-run"),
            )
            stage = StageConfig(
                id="test",
                type="command",
                commands=(command,),
                output="test-output.txt",
                shell=False,
                working_dir=Path("work"),
            )

            result = executor.run_stage(stage, "TASK-001")

            self.assertEqual(result.status, "pass")
            output = (root / result.output_path).read_text(encoding="utf-8")
            self.assertIn("work", output)

    def test_command_artifact_format_tolerates_missing_streams(self) -> None:
        output = format_command_runs(
            "test",
            [
                CommandRun(
                    command="cmd",
                    exit_code=0,
                    stdout=None,  # type: ignore[arg-type]
                    stderr=None,  # type: ignore[arg-type]
                    duration_seconds=0.1,
                )
            ],
        )

        self.assertIn("Command: `cmd`", output)
        self.assertIn("### stderr", output)


if __name__ == "__main__":
    unittest.main()
