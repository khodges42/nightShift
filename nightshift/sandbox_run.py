"""General-purpose setup-and-run sandbox command."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
import venv

from .errors import NightShiftError
from .integ import _initialize_project_git_repo
from .integ_setup import IntegrationSetupResult, setup_python_project


@dataclass(frozen=True)
class SandboxRunResult:
    source_project: Path
    directory: Path
    project_dir: Path
    venv_dir: Path
    setup: IntegrationSetupResult
    command: tuple[str, ...]
    exit_code: int
    dry_run: bool


def run_sandbox_project(
    project: str | Path,
    *,
    output: str | Path | None = None,
    timestamped: bool = False,
    root: str | Path = ".",
    task: str | None = None,
    all_tasks: bool = False,
    setup_extras: tuple[str, ...] = ("pytest",),
    skip_setup_validate: bool = False,
    dry_run: bool = False,
    animation: str = "status_dots",
    no_animation: bool = False,
    force: bool = False,
) -> SandboxRunResult:
    """Copy a NightShift project into a sandbox, set it up, and run it."""

    if task and all_tasks:
        raise NightShiftError("Sandbox run error: use either --task or --all, not both.")
    if not task and not all_tasks:
        raise NightShiftError("Sandbox run error: provide --task or --all.")
    if output and timestamped:
        raise NightShiftError("Sandbox run error: use either --output or --timestamped, not both.")
    if not output and not timestamped:
        raise NightShiftError("Sandbox run error: provide --output or --timestamped.")

    source = Path(project).resolve()
    if not source.exists() or not source.is_dir():
        raise NightShiftError(f"Sandbox run error: project directory does not exist: {source}")
    if not (source / "nightshift.yaml").exists():
        raise NightShiftError(f"Sandbox run error: project does not contain nightshift.yaml: {source}")

    sandbox_dir = _sandbox_directory(output, root=root, timestamped=timestamped)
    project_dir = sandbox_dir / "project"
    venv_dir = sandbox_dir / ".venv"
    if project_dir.exists() and any(project_dir.iterdir()) and not force:
        raise NightShiftError(f"Sandbox run error: output project already exists: {project_dir}")

    sandbox_dir.mkdir(parents=True, exist_ok=True)
    if project_dir.exists():
        shutil.rmtree(project_dir)
    shutil.copytree(source, project_dir, ignore=_copy_ignore)
    if not dry_run:
        if not venv_dir.exists():
            venv.EnvBuilder(with_pip=True).create(venv_dir)
        _initialize_project_git_repo(project_dir)

    setup = setup_python_project(
        project_dir,
        extras=setup_extras,
        validate=not skip_setup_validate,
        dry_run=dry_run,
    )
    command = [str(setup.python), "-m", "nightshift.cli", "run"]
    if no_animation:
        command.append("--no-animation")
    elif animation:
        command.extend(["--animation", animation])
    if all_tasks:
        command.append("--all")
    else:
        command.extend(["--task", task or ""])

    exit_code = 0
    if not dry_run:
        completed = subprocess.run(command, cwd=project_dir, text=True, encoding="utf-8", errors="replace")
        exit_code = completed.returncode

    return SandboxRunResult(
        source_project=source,
        directory=sandbox_dir,
        project_dir=project_dir,
        venv_dir=venv_dir,
        setup=setup,
        command=tuple(command),
        exit_code=exit_code,
        dry_run=dry_run,
    )


def format_sandbox_run_result(result: SandboxRunResult) -> str:
    lines = [
        f"Source project: {result.source_project}",
        f"Sandbox: {result.directory}",
        f"Project: {result.project_dir}",
        f"Venv: {result.venv_dir}",
        f"Run command: {' '.join(result.command)}",
        f"Exit code: {result.exit_code}",
        f"Artifacts: {result.project_dir / '.nightshift'}",
    ]
    if result.dry_run:
        lines.insert(0, "Dry run: true")
    return "\n".join(lines)


def _sandbox_directory(output: str | Path | None, *, root: str | Path, timestamped: bool) -> Path:
    if output:
        return Path(output).resolve()
    base = Path(root).resolve() / "integ_runs"
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    return base / run_id


def _copy_ignore(directory: str, names: list[str]) -> set[str]:
    ignored = {
        ".git",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        ".venv",
        "venv",
    }
    if Path(directory).name == ".nightshift":
        ignored.update({"runs", "run-summary.md", "run.log", "project-context.md", "project-context-chart.md"})
    return {name for name in names if name in ignored or name.endswith(".egg-info")}
