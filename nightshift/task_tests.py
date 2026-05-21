"""Task-specific test file validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .commands import extract_test_file_paths, render_command_template
from .config import COMMAND_STAGE_TYPES, NightShiftConfig
from .tasks import Task


@dataclass(frozen=True)
class TaskTestCheck:
    task_id: str
    path: str
    exists: bool


def check_task_test_files(config: NightShiftConfig, tasks: tuple[Task, ...] | list[Task]) -> tuple[TaskTestCheck, ...]:
    checks: list[TaskTestCheck] = []
    for task in tasks:
        seen: set[str] = set()
        for stage in config.pipeline.stages:
            if stage.type not in COMMAND_STAGE_TYPES:
                continue
            for command in stage.commands:
                rendered = render_command_template(command, task.id)
                for path_text in extract_test_file_paths(rendered):
                    if path_text in seen:
                        continue
                    seen.add(path_text)
                    checks.append(TaskTestCheck(task.id, path_text, (config.project.root / path_text).exists()))
    return tuple(checks)


def format_task_test_checks(checks: tuple[TaskTestCheck, ...]) -> str:
    if not checks:
        return "Task test files: no task-specific test paths detected."
    lines = ["Task test files:"]
    for check in checks:
        status = "ok" if check.exists else "missing"
        lines.append(f"- {check.task_id}: {check.path} ({status})")
    return "\n".join(lines)


def missing_task_test_paths(checks: tuple[TaskTestCheck, ...]) -> tuple[Path, ...]:
    return tuple(Path(check.path) for check in checks if not check.exists)
