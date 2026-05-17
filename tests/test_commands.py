from pathlib import Path
import tempfile
import unittest

from nightshift.artifacts import ArtifactStore
from nightshift.commands import CommandExecutor
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


if __name__ == "__main__":
    unittest.main()
