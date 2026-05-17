"""Markdown task parsing and selection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .errors import SafetyError, TaskError
from .safety import resolve_inside_root


TASK_HEADER_RE = re.compile(r"^\s*-\s+\[(?P<mark>[ xX])\]\s+(?P<id>[A-Z]+-\d+):\s+(?P<title>.+?)\s*$")
CHECKBOX_RE = re.compile(r"^\s*-\s+\[[^\]]*\]")
SECTION_RE = re.compile(r"^(?P<name>[A-Za-z][A-Za-z ]+):\s*$")


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    completed: bool
    description: str
    acceptance_criteria: tuple[str, ...]
    dependencies: tuple[str, ...]
    raw_markdown: str
    line_number: int


def parse_task_file(project_root: str | Path, task_file: str | Path) -> list[Task]:
    """Load and parse a task markdown file inside the project root."""

    try:
        path = resolve_inside_root(project_root, task_file, "task file")
    except SafetyError as exc:
        raise TaskError(str(exc)) from exc

    if not path.exists():
        raise TaskError(f"Task error: task file does not exist: {path}")

    return parse_tasks(path.read_text(encoding="utf-8"))


def parse_tasks(markdown: str) -> list[Task]:
    """Parse NightShift's documented markdown checklist task format."""

    lines = markdown.splitlines()
    tasks: list[Task] = []
    seen_ids: set[str] = set()
    index = 0

    while index < len(lines):
        line = lines[index]
        header = TASK_HEADER_RE.match(line)
        if not header:
            if CHECKBOX_RE.match(line):
                raise TaskError(
                    f"Task error: malformed task header on line {index + 1}. "
                    "Expected '- [ ] TASK-001: Task title'."
                )
            index += 1
            continue

        task_id = header.group("id")
        if task_id in seen_ids:
            raise TaskError(f"Task error: duplicate task id '{task_id}' on line {index + 1}.")
        seen_ids.add(task_id)

        start = index
        index += 1
        while index < len(lines) and not TASK_HEADER_RE.match(lines[index]):
            if CHECKBOX_RE.match(lines[index]):
                raise TaskError(
                    f"Task error: malformed task header on line {index + 1}. "
                    "Expected '- [ ] TASK-001: Task title'."
                )
            index += 1

        block = lines[start:index]
        description = _extract_section(block, "Description")
        acceptance_criteria = tuple(_extract_bullets(block, "Acceptance Criteria"))
        dependencies = tuple(_extract_bullets(block, "Dependencies"))

        if not acceptance_criteria:
            raise TaskError(
                f"Task error: task '{task_id}' is missing Acceptance Criteria bullets."
            )

        tasks.append(
            Task(
                id=task_id,
                title=header.group("title"),
                completed=header.group("mark").lower() == "x",
                description=description,
                acceptance_criteria=acceptance_criteria,
                dependencies=dependencies,
                raw_markdown="\n".join(block).strip() + "\n",
                line_number=start + 1,
            )
        )

    if not tasks:
        raise TaskError("Task error: no tasks found. Expected '- [ ] TASK-001: Task title'.")

    return tasks


def select_next_incomplete_task(tasks: list[Task] | tuple[Task, ...]) -> Task:
    """Return the first incomplete task in file order."""

    for task in tasks:
        if not task.completed:
            return task
    raise TaskError("Task error: no incomplete tasks found.")


def select_task_by_id(tasks: list[Task] | tuple[Task, ...], task_id: str) -> Task:
    """Return a task by id."""

    for task in tasks:
        if task.id == task_id:
            return task
    available = ", ".join(task.id for task in tasks) or "<none>"
    raise TaskError(f"Task error: unknown task id '{task_id}'. Available tasks: {available}.")


def _extract_section(block: list[str], section_name: str) -> str:
    start = _find_section_index(block, section_name)
    if start is None:
        return ""

    collected: list[str] = []
    for line in block[start + 1 :]:
        if SECTION_RE.match(line.strip()):
            break
        collected.append(line)

    return "\n".join(collected).strip()


def _extract_bullets(block: list[str], section_name: str) -> list[str]:
    start = _find_section_index(block, section_name)
    if start is None:
        return []

    bullets: list[str] = []
    for line in block[start + 1 :]:
        stripped = line.strip()
        if SECTION_RE.match(stripped):
            break
        if stripped.startswith("- "):
            value = stripped[2:].strip()
            if value:
                bullets.append(value)
    return bullets


def _find_section_index(block: list[str], section_name: str) -> int | None:
    expected = f"{section_name}:".lower()
    for index, line in enumerate(block):
        if line.strip().lower() == expected:
            return index
    return None
