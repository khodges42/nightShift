"""Operational run logging for NightShift."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .artifacts import ArtifactStore
from .terminal import format_console_event_line, format_plain_event_line


ConsoleWriter = Callable[[str], None]
StatusWriter = Callable[[str], None]


@dataclass(frozen=True)
class LogEvent:
    event: str
    message: str
    fields: dict[str, object]


class RunLogger:
    """Write concise operational events to CLI and run log artifacts."""

    def __init__(self, console: ConsoleWriter | None = None, status: StatusWriter | None = None) -> None:
        self.console = console
        self.status = status
        self._run_log_path: Path | None = None
        self._aggregate_log_path: Path | None = None
        self._initialized_run_logs: set[Path] = set()

    def bind(self, artifacts: ArtifactStore) -> None:
        artifacts.initialize_run()
        self._run_log_path = artifacts.run_log_path
        self._aggregate_log_path = artifacts.aggregate_log_path
        if self._run_log_path not in self._initialized_run_logs:
            self._run_log_path.parent.mkdir(parents=True, exist_ok=True)
            self._run_log_path.write_text("", encoding="utf-8")
            self._initialized_run_logs.add(self._run_log_path)

    def event(self, event: str, message: str, **fields: object) -> None:
        safe_fields = _redact_fields(fields)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        line = format_plain_event_line(timestamp, event, message, safe_fields)
        if self.console is not None:
            self.console(format_console_event_line(timestamp, event, message, safe_fields))
        if self.status is not None:
            status_message = format_status_event_message(event, message, safe_fields)
            if status_message:
                self.status(status_message)
        for path in (self._run_log_path,):
            if path is None:
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")


class NullRunLogger(RunLogger):
    def __init__(self) -> None:
        super().__init__(console=None)

    def bind(self, artifacts: ArtifactStore) -> None:
        return None

    def event(self, event: str, message: str, **fields: object) -> None:
        return None


def format_log_line(log_event: LogEvent) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return format_plain_event_line(timestamp, log_event.event, log_event.message, log_event.fields)


def format_status_event_message(event: str, message: str, fields: dict[str, object]) -> str | None:
    task_id = str(fields.get("task_id", "") or "")
    retry = fields.get("retry_count")
    retry_text = f" retry {retry}" if retry not in (None, "") else ""
    stage_id = str(fields.get("stage_id", "") or "")
    stage_type = str(fields.get("stage_type", "") or "")
    agent_id = str(fields.get("agent_id", "") or "")
    model = str(fields.get("model", "") or "")
    command = str(fields.get("command", "") or "")
    status = str(fields.get("status", "") or "")
    next_stage = str(fields.get("next_stage", "") or "")

    prefix = f"Task: {task_id} | " if task_id else ""
    if event == "task.start":
        return f"Task: {task_id} | Starting" if task_id else "Starting task"
    if event == "stage.start" and stage_id:
        label = f"{stage_id} ({stage_type})" if stage_type else stage_id
        return f"{prefix}>> Stage: {label}{retry_text}"
    if event == "agent.start":
        model_text = f" | Model: {model}" if model else ""
        return f"{prefix}Agent: {agent_id or stage_id}{model_text}"
    if event == "command.start":
        return f"{prefix}Command: {command or stage_id}"
    if event == "stage.retry":
        return f"{prefix}Retry: {stage_id} -> {next_stage}{retry_text}"
    if event in {"stage.finish", "task.finish"} and status:
        target = f"Stage: {stage_id}" if event == "stage.finish" and stage_id else "Task"
        reason = str(fields.get("reason", "") or "")
        reason_text = f" | {reason}" if reason and status not in {"pass", "complete"} else ""
        return f"{prefix}{target}: {status}{reason_text}"
    if event.endswith(".start"):
        return f"{prefix}{message}"
    return None


def tail_lines(path: Path, limit: int = 100) -> list[str]:
    if limit <= 0:
        return []
    if not path.exists() or not path.is_file():
        return []
    return path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]


def _redact_fields(fields: dict[str, object]) -> dict[str, object]:
    redacted: dict[str, object] = {}
    for key, value in fields.items():
        lowered = key.lower()
        if any(marker in lowered for marker in ("secret", "token", "password", "key")):
            redacted[key] = "<redacted>"
        else:
            redacted[key] = value
    return redacted
