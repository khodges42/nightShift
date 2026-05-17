"""Command stage execution."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shlex
import subprocess
import time

from .artifacts import ArtifactStore
from .config import SafetyConfig, StageConfig
from .errors import CommandError, SafetyError
from .safety import ensure_command_allowed, resolve_inside_root, resolve_project_root
from .stages import StageResult


DEFAULT_COMMAND_TIMEOUT_SECONDS = 300


@dataclass(frozen=True)
class CommandRun:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False


class CommandExecutor:
    """Run configured command stages and persist their output."""

    def __init__(
        self,
        project_root: str | Path,
        safety: SafetyConfig,
        artifacts: ArtifactStore,
        timeout_seconds: int = DEFAULT_COMMAND_TIMEOUT_SECONDS,
    ) -> None:
        self.project_root = resolve_project_root(project_root)
        self.safety = safety
        self.artifacts = artifacts
        self.timeout_seconds = timeout_seconds

    def run_stage(self, stage: StageConfig, task_id: str) -> StageResult:
        if stage.type != "command":
            raise CommandError(
                f"Command error: stage '{stage.id}' has type '{stage.type}', expected 'command'."
            )
        if not stage.commands:
            raise CommandError(f"Command error: stage '{stage.id}' has no commands.")

        runs: list[CommandRun] = []
        status = "pass"
        reason = "All commands passed."

        for command in stage.commands:
            run = self.run_command(
                command,
                shell=stage.shell,
                timeout_seconds=stage.timeout_seconds,
                working_dir=stage.working_dir,
            )
            runs.append(run)
            if run.timed_out:
                status = "fail"
                timeout = stage.timeout_seconds or self.timeout_seconds
                reason = f"Command timed out after {timeout}s: {run.command}"
                break
            if run.exit_code != 0:
                status = "fail"
                reason = f"Command exited with code {run.exit_code}: {run.command}"
                break

        output_filename = stage.output or f"{stage.id}-output.txt"
        output_path = self.artifacts.write_command_output(
            task_id,
            output_filename,
            format_command_runs(stage.id, runs),
        )
        return StageResult(
            stage_id=stage.id,
            status=status,  # type: ignore[arg-type]
            reason=reason,
            output_path=str(output_path.relative_to(self.project_root)),
        )

    def run_command(
        self,
        command: str,
        shell: bool = True,
        timeout_seconds: int | None = None,
        working_dir: Path | None = None,
    ) -> CommandRun:
        try:
            normalized = ensure_command_allowed(
                command,
                self.safety.allowed_commands,
                self.safety.forbidden_commands,
            )
        except SafetyError as exc:
            raise CommandError(str(exc)) from exc

        cwd = self.project_root
        if working_dir is not None:
            try:
                cwd = resolve_inside_root(self.project_root, working_dir, "command working_dir")
            except SafetyError as exc:
                raise CommandError(str(exc)) from exc
        timeout = timeout_seconds or self.timeout_seconds
        args: str | list[str] = normalized if shell else shlex.split(normalized)
        env = None
        if self.safety.allowed_env:
            env = {name: os.environ[name] for name in self.safety.allowed_env if name in os.environ}
            if "PATH" in os.environ:
                env.setdefault("PATH", os.environ["PATH"])

        started = time.monotonic()
        try:
            completed = subprocess.run(
                args,
                cwd=cwd,
                shell=shell,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                env=env,
            )
            duration = time.monotonic() - started
            return CommandRun(
                command=normalized,
                exit_code=completed.returncode,
                stdout=_coerce_output(completed.stdout),
                stderr=_coerce_output(completed.stderr),
                duration_seconds=duration,
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.monotonic() - started
            return CommandRun(
                command=normalized,
                exit_code=-1,
                stdout=_coerce_output(exc.stdout),
                stderr=_coerce_output(exc.stderr),
                duration_seconds=duration,
                timed_out=True,
            )


def format_command_runs(stage_id: str, runs: list[CommandRun]) -> str:
    lines = [f"# Command Output: {stage_id}", ""]
    for index, run in enumerate(runs, start=1):
        stdout = _coerce_output(run.stdout)
        stderr = _coerce_output(run.stderr)
        lines.extend(
            [
                f"## Command {index}",
                "",
                f"Command: `{run.command}`",
                f"Exit code: {run.exit_code}",
                f"Duration seconds: {run.duration_seconds:.3f}",
                f"Timed out: {str(run.timed_out).lower()}",
                "",
                "### stdout",
                "",
                "```text",
                stdout.rstrip(),
                "```",
                "",
                "### stderr",
                "",
                "```text",
                stderr.rstrip(),
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def _coerce_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
