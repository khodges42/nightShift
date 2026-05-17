"""Artifact storage for NightShift runs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import shutil
import re

from .config import NightShiftConfig
from .errors import ArtifactError, SafetyError
from .safety import resolve_inside_root, resolve_project_root, safe_artifact_path
from .tasks import Task


@dataclass(frozen=True)
class TaskArtifactPaths:
    task_id: str
    directory: Path
    task_snapshot: Path


class ArtifactStore:
    """Create and write the durable artifact tree for one run."""

    def __init__(self, project_root: str | Path, artifact_dir: str | Path, run_id: str | None = None) -> None:
        try:
            self.project_root = resolve_project_root(project_root)
            self.artifact_root = resolve_inside_root(
                self.project_root, artifact_dir, "artifact directory"
            )
        except SafetyError as exc:
            raise ArtifactError(str(exc)) from exc

        self.run_id = _safe_artifact_segment(run_id or default_run_id(), "run id")
        self.run_dir = self._artifact_path("runs", self.run_id)
        self.tasks_dir = self.run_dir / "tasks"
        self.project_context_path = self.artifact_root / "project-context.md"
        self.run_summary_path = self.run_dir / "run-summary.md"
        self.config_snapshot_path = self.run_dir / "config.snapshot.yaml"
        self.run_log_path = self.run_dir / "run.log"
        self.aggregate_log_path = self.artifact_root / "nightshift.log"

    @classmethod
    def from_config(cls, config: NightShiftConfig, run_id: str | None = None) -> "ArtifactStore":
        return cls(config.project.root, config.project.artifact_dir, run_id=run_id)

    def initialize_run(self) -> None:
        """Create the base artifact tree for this run."""

        self.artifact_root.mkdir(parents=True, exist_ok=True)
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        if not self.project_context_path.exists():
            self.project_context_path.write_text("# Project Context\n\n", encoding="utf-8")
        if not self.run_summary_path.exists():
            self.run_summary_path.write_text("# Run Summary\n\n", encoding="utf-8")

    def write_config_snapshot(self, config_path: str | Path) -> Path:
        """Copy the input config into the run artifact directory."""

        self.initialize_run()
        source = Path(config_path).resolve()
        try:
            source.relative_to(self.project_root)
        except ValueError as exc:
            raise ArtifactError(f"Artifact error: config path is outside project root: {source}") from exc
        if not source.exists():
            raise ArtifactError(f"Artifact error: config path does not exist: {source}")
        shutil.copyfile(source, self.config_snapshot_path)
        return self.config_snapshot_path

    def write_prompt_snapshots(self, prompt_paths: dict[str, Path]) -> list[Path]:
        """Copy agent prompt files into the run artifact directory."""

        self.initialize_run()
        prompts_dir = self.run_dir / "prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        for agent_id, prompt_path in sorted(prompt_paths.items()):
            source = prompt_path.resolve()
            try:
                source.relative_to(self.project_root)
            except ValueError as exc:
                raise ArtifactError(
                    f"Artifact error: prompt path is outside project root: {source}"
                ) from exc
            if not source.exists():
                raise ArtifactError(f"Artifact error: prompt path does not exist: {source}")
            target = prompts_dir / f"{_safe_artifact_segment(agent_id, 'agent id')}.md"
            shutil.copyfile(source, target)
            written.append(target)
        return written

    def write_run_metadata(self, content: str, filename: str = "run-metadata.md") -> Path:
        self.initialize_run()
        path = self.run_dir / filename
        path.write_text(content, encoding="utf-8")
        return path

    def create_task_dir(self, task_id: str) -> TaskArtifactPaths:
        """Create the artifact directory for one task."""

        self.initialize_run()
        safe_task_id = _safe_artifact_segment(task_id, "task id")
        task_dir = self._artifact_path("runs", self.run_id, "tasks", safe_task_id)
        task_dir.mkdir(parents=True, exist_ok=True)
        return TaskArtifactPaths(
            task_id=safe_task_id,
            directory=task_dir,
            task_snapshot=task_dir / "task.md",
        )

    def write_task_snapshot(self, task: Task) -> Path:
        paths = self.create_task_dir(task.id)
        paths.task_snapshot.write_text(task.raw_markdown, encoding="utf-8")
        return paths.task_snapshot

    def write_stage_output(self, task_id: str, filename: str, content: str) -> Path:
        """Write a stage artifact under a task directory."""

        task_dir = self.create_task_dir(task_id).directory
        output_path = self._task_artifact_path(task_dir, filename)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        return output_path

    def write_command_output(self, task_id: str, filename: str, content: str) -> Path:
        return self.write_stage_output(task_id, filename, content)

    def write_final_task_notes(self, task_id: str, content: str, filename: str = "final-notes.md") -> Path:
        return self.write_stage_output(task_id, filename, content)

    def _artifact_path(self, *parts: str | Path) -> Path:
        try:
            return safe_artifact_path(self.project_root, self.artifact_root, *parts)
        except SafetyError as exc:
            raise ArtifactError(str(exc)) from exc

    def _task_artifact_path(self, task_dir: Path, filename: str) -> Path:
        candidate = Path(filename)
        if candidate.is_absolute():
            raise ArtifactError(f"Artifact error: stage output filename must be relative: {filename}")
        resolved = (task_dir / candidate).resolve()
        try:
            resolved.relative_to(task_dir.resolve())
        except ValueError as exc:
            raise ArtifactError(f"Artifact error: stage output escapes task directory: {filename}") from exc
        return resolved


def default_run_id(now: datetime | None = None) -> str:
    """Return a filesystem-friendly UTC run id."""

    value = now or datetime.now(timezone.utc)
    return value.strftime("%Y%m%dT%H%M%SZ")


def _safe_artifact_segment(value: str, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise ArtifactError(f"Artifact error: {context} must be a non-empty string.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", value):
        raise ArtifactError(
            f"Artifact error: {context} contains unsafe characters: {value}"
        )
    if value in {".", ".."}:
        raise ArtifactError(f"Artifact error: {context} cannot be '{value}'.")
    return value
