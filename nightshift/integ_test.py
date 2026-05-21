"""End-to-end integration test wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from .errors import NightShiftError
from .integ import IntegrationRun, create_integration_run
from .integ_setup import IntegrationSetupResult, setup_python_project


@dataclass(frozen=True)
class IntegrationTestResult:
    run: IntegrationRun
    setup: IntegrationSetupResult
    command: tuple[str, ...]
    exit_code: int
    dry_run: bool


def run_integration_test(
    root: str | Path = ".",
    *,
    template: str = "tutorial-deaddrop",
    task: str | None = None,
    all_tasks: bool = False,
    keep: int | None = None,
    setup_extras: tuple[str, ...] = ("pytest",),
    skip_setup_validate: bool = False,
    dry_run: bool = False,
) -> IntegrationTestResult:
    if task and all_tasks:
        raise NightShiftError("Integration test error: use either --task or --all, not both.")
    if not task and not all_tasks:
        raise NightShiftError("Integration test error: provide --task or --all.")

    run = create_integration_run(Path(root), template=template, keep=keep)
    project = run.directory / "project"
    setup = setup_python_project(
        project,
        extras=setup_extras,
        validate=not skip_setup_validate,
        dry_run=dry_run,
    )
    command = [str(setup.python), "-m", "nightshift.cli", "run", "--no-animation"]
    if all_tasks:
        command.append("--all")
    else:
        command.extend(["--task", task or ""])

    exit_code = 0
    if not dry_run:
        completed = subprocess.run(command, cwd=project, text=True, encoding="utf-8", errors="replace")
        exit_code = completed.returncode
    return IntegrationTestResult(run, setup, tuple(command), exit_code, dry_run)


def format_integration_test_result(result: IntegrationTestResult) -> str:
    lines = [
        f"Integration run: {result.run.directory}",
        f"Project: {result.run.directory / 'project'}",
        f"Venv: {result.run.venv_dir}",
        f"Run command: {' '.join(result.command)}",
        f"Exit code: {result.exit_code}",
        f"Artifacts: {result.run.directory / 'project' / '.nightshift'}",
    ]
    if result.dry_run:
        lines.insert(3, "Dry run: true")
    return "\n".join(lines)
