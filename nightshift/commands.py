"""Command stage execution."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time

from .artifacts import ArtifactStore
from .config import SafetyConfig, StageConfig
from .errors import CommandError, SafetyError
from .runlog import NullRunLogger, RunLogger
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
        logger: RunLogger | None = None,
    ) -> None:
        self.project_root = resolve_project_root(project_root)
        self.safety = safety
        self.artifacts = artifacts
        self.timeout_seconds = timeout_seconds
        self.logger = logger or NullRunLogger()

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

        for index, command in enumerate(stage.commands, start=1):
            self.logger.event(
                "command.start",
                "Starting command",
                stage_id=stage.id,
                command_index=index,
                command=command,
            )
            rendered_command = render_command_template(command, task_id)
            rendered_allowed_commands = tuple(
                render_command_template(allowed, task_id) for allowed in self.safety.allowed_commands
            )
            run = self.run_command(
                rendered_command,
                shell=stage.shell,
                timeout_seconds=stage.timeout_seconds,
                working_dir=stage.working_dir,
                allowed_commands=rendered_allowed_commands,
            )
            runs.append(run)
            self.logger.event(
                "command.finish",
                "Finished command",
                stage_id=stage.id,
                command_index=index,
                exit_code=run.exit_code,
                duration=f"{run.duration_seconds:.3f}s",
                timed_out=str(run.timed_out).lower(),
            )
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
        self.logger.event(
            "artifact.write",
            "Wrote command artifact",
            stage_id=stage.id,
            task_id=task_id,
            artifact_path=output_path.relative_to(self.project_root),
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
        allowed_commands: tuple[str, ...] | None = None,
    ) -> CommandRun:
        try:
            normalized = ensure_command_allowed(
                command,
                allowed_commands if allowed_commands is not None else self.safety.allowed_commands,
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
        env = _command_env(self.safety.allowed_env, project_root=self.project_root)

        started = time.monotonic()
        process = subprocess.Popen(
            args,
            cwd=cwd,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout)
            duration = time.monotonic() - started
            return CommandRun(
                command=normalized,
                exit_code=process.returncode if process.returncode is not None else -1,
                stdout=_coerce_output(stdout),
                stderr=_coerce_output(stderr),
                duration_seconds=duration,
            )
        except subprocess.TimeoutExpired:
            _kill_process_tree(process)
            try:
                stdout, stderr = process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                stdout, stderr = "", "Timed out while collecting process output after termination."
            duration = time.monotonic() - started
            return CommandRun(
                command=normalized,
                exit_code=-1,
                stdout=_coerce_output(stdout),
                stderr=_coerce_output(stderr),
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


def render_command_template(command: str, task_id: str) -> str:
    task_id_lower = task_id.lower()
    task_id_slug = task_id_lower.replace("-", "_")
    task_id_compact = task_id_lower.replace("-", "")
    return command.format(
        task_id=task_id,
        task_id_lower=task_id_lower,
        task_id_slug=task_id_slug,
        task_id_compact=task_id_compact,
    )


def extract_test_file_paths(command: str) -> tuple[str, ...]:
    paths: list[str] = []
    for match in re.finditer(r"(?<![\w./\\-])(tests[\\/][^\s`'\"<>|&;]+\.py)", command):
        path = match.group(1).replace("\\", "/")
        if path not in paths:
            paths.append(path)
    return tuple(paths)


def _coerce_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _command_env(allowed_env: tuple[str, ...], project_root: Path | None = None) -> dict[str, str]:
    env = dict(os.environ) if not allowed_env else {
        name: os.environ[name] for name in allowed_env if name in os.environ
    }
    venv_dir = _project_venv_dir(project_root) if project_root is not None else None
    python_dir = str(_venv_scripts_dir(venv_dir) if venv_dir is not None else Path(sys.executable).resolve().parent)
    current_path = env.get("PATH") or os.environ.get("PATH", "")
    path_parts = [part for part in current_path.split(os.pathsep) if part]
    env["PATH"] = os.pathsep.join([python_dir, *[part for part in path_parts if part != python_dir]])
    if venv_dir is not None:
        env["VIRTUAL_ENV"] = str(venv_dir)
    else:
        env.setdefault("VIRTUAL_ENV", os.environ.get("VIRTUAL_ENV", ""))
    return env


def _project_venv_dir(project_root: Path | None) -> Path | None:
    if project_root is None:
        return None
    candidates = (project_root / ".venv", project_root.parent / ".venv")
    for candidate in candidates:
        if _venv_python(candidate).exists():
            return candidate.resolve()
    return None


def _venv_scripts_dir(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts" if os.name == "nt" else "bin")


def _venv_python(venv_dir: Path) -> Path:
    executable = "python.exe" if os.name == "nt" else "python"
    return _venv_scripts_dir(venv_dir) / executable


def _kill_process_tree(process: subprocess.Popen[str]) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return
    process.kill()
