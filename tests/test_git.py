from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from nightshift.artifacts import ArtifactStore
from nightshift.errors import SafetyError
from nightshift.git import (
    GitCommandResult,
    ensure_clean_worktree,
    format_git_unavailable_status,
    git_failure_reason,
    write_diff_artifact,
    write_git_artifacts,
)


def git_available() -> bool:
    return shutil.which("git") is not None


@unittest.skipUnless(git_available(), "git is not available")
class GitSafetyTests(unittest.TestCase):
    def test_clean_worktree_requirement_blocks_dirty_repo(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True, text=True)
            (root / "file.txt").write_text("dirty", encoding="utf-8")

            with self.assertRaisesRegex(SafetyError, "repository is dirty"):
                ensure_clean_worktree(root, True)

    def test_git_artifacts_are_written_for_repo(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True, text=True)
            (root / "file.txt").write_text("dirty", encoding="utf-8")
            artifacts = ArtifactStore(root, ".nightshift", run_id="test-run")

            status_path = write_git_artifacts(artifacts, "TASK-001", "before")
            diff_path = write_diff_artifact(artifacts, "TASK-001")

            self.assertTrue(status_path.exists())
            self.assertTrue(diff_path.exists())
            self.assertIn("Git Status before", status_path.read_text(encoding="utf-8"))

    def test_diff_artifact_is_concise_outside_git_repo(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = ArtifactStore(root, ".nightshift", run_id="test-run")

            diff_path = write_diff_artifact(artifacts, "TASK-001")

            content = diff_path.read_text(encoding="utf-8")
            self.assertIn("Project root is not a git repository", content)
            self.assertNotIn("usage: git diff", content)

    def test_git_status_artifact_is_readable_outside_git_repo(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = ArtifactStore(root, ".nightshift", run_id="test-run")

            status_path = write_git_artifacts(artifacts, "TASK-001", "before")

            content = status_path.read_text(encoding="utf-8")
            self.assertIn("Git repository: false", content)
            self.assertIn("Project root is not a git repository", content)
            self.assertNotIn("fatal:", content)

    def test_safe_directory_failure_gets_actionable_guidance(self) -> None:
        root = Path("C:/repo/project")
        result = GitCommandResult(
            available=False,
            exit_code=128,
            stdout="",
            stderr=(
                "fatal: detected dubious ownership in repository at 'C:/repo/project'\n"
                "To add an exception for this directory, call:\n"
                "git config --global --add safe.directory C:/repo/project\n"
            ),
        )

        reason = git_failure_reason(result, root)
        formatted = format_git_unavailable_status(result, "before", root)

        self.assertIn("ownership is not trusted", reason)
        self.assertIn("git config --global --add safe.directory C:/repo/project", reason)
        self.assertIn("NightShift will not change global Git configuration", formatted)


if __name__ == "__main__":
    unittest.main()
