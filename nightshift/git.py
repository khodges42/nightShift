"""Git safety and diff artifact helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from .artifacts import ArtifactStore
from .errors import SafetyError


@dataclass(frozen=True)
class GitCommandResult:
    available: bool
    exit_code: int
    stdout: str
    stderr: str


def run_git(project_root: Path, args: list[str], timeout_seconds: int = 15) -> GitCommandResult:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return GitCommandResult(False, -1, "", str(exc))
    return GitCommandResult(
        completed.returncode == 0,
        completed.returncode,
        completed.stdout or "",
        completed.stderr or "",
    )


def get_git_status(project_root: Path) -> GitCommandResult:
    return run_git(project_root, ["status", "--short"])


def ensure_clean_worktree(project_root: Path, require_clean: bool) -> None:
    if not require_clean:
        return
    status = get_git_status(project_root)
    if not status.available:
        raise SafetyError(
            "Safety error: clean worktree is required, but git status could not be read: "
            f"{status.stderr.strip() or 'unknown git error'}"
        )
    if status.stdout.strip():
        raise SafetyError("Safety error: clean worktree is required, but repository is dirty.")


def write_git_artifacts(artifacts: ArtifactStore, task_id: str, when: str) -> Path:
    status = get_git_status(artifacts.project_root)
    content = format_git_status(status, when)
    return artifacts.write_stage_output(task_id, f"git-status-{when}.txt", content)


def write_diff_artifact(artifacts: ArtifactStore, task_id: str) -> Path:
    diff = run_git(artifacts.project_root, ["diff", "--binary"], timeout_seconds=30)
    if not diff.available:
        content = "Git diff unavailable.\n\n" + (diff.stderr or "")
    elif diff.stdout:
        content = diff.stdout
    else:
        content = "No tracked-file diff detected.\n"
    return artifacts.write_stage_output(task_id, "diff.patch", content)


def format_git_status(status: GitCommandResult, when: str) -> str:
    lines = [
        f"# Git Status {when}",
        "",
        f"Available: {str(status.available).lower()}",
        f"Exit code: {status.exit_code}",
        "",
        "## stdout",
        "",
        "```text",
        status.stdout.rstrip(),
        "```",
        "",
        "## stderr",
        "",
        "```text",
        status.stderr.rstrip(),
        "```",
        "",
    ]
    return "\n".join(lines)
