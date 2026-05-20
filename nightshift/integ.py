"""Integration sandbox runner."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import shutil
import venv

from .init import init_project


@dataclass(frozen=True)
class IntegrationRun:
    directory: Path
    venv_dir: Path
    log_path: Path


def create_integration_run(root: Path, *, template: str = "basic", keep: int | None = None) -> IntegrationRun:
    base = root.resolve() / "integ_runs"
    base.mkdir(parents=True, exist_ok=True)
    if keep is not None:
        cleanup_integration_runs(base, keep=keep)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    run_dir = base / run_id
    run_dir.mkdir()
    log_dir = run_dir / "logs"
    transcript_dir = run_dir / "transcripts"
    patch_dir = run_dir / "patches"
    artifact_dir = run_dir / "artifacts"
    for directory in (log_dir, transcript_dir, patch_dir, artifact_dir):
        directory.mkdir()
    venv_dir = run_dir / ".venv"
    venv.EnvBuilder(with_pip=True).create(venv_dir)
    project_dir = run_dir / "project"
    project_dir.mkdir()
    init_project(project_dir, template=template)
    log_path = log_dir / "integ-run.log"
    log_path.write_text(
        "\n".join(
            [
                "# Integration Run",
                "",
                f"Template: {template}",
                f"Project: {project_dir}",
                f"Venv: {venv_dir}",
                "Dependencies: project installation is left to the operator or command stages.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return IntegrationRun(run_dir, venv_dir, log_path)


def cleanup_integration_runs(base: Path, *, keep: int) -> tuple[Path, ...]:
    if keep < 0:
        raise ValueError("keep must be zero or greater")
    runs = sorted((path for path in base.iterdir() if path.is_dir()), key=lambda path: path.name, reverse=True)
    removed: list[Path] = []
    for path in runs[keep:]:
        shutil.rmtree(path)
        removed.append(path)
    return tuple(removed)
