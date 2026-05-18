"""Operational run logging for NightShift."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .artifacts import ArtifactStore
from .terminal import format_console_event_line, format_plain_event_line


ConsoleWriter = Callable[[str], None]


@dataclass(frozen=True)
class LogEvent:
    event: str
    message: str
    fields: dict[str, object]


class RunLogger:
    """Write concise operational events to CLI and run log artifacts."""

    def __init__(self, console: ConsoleWriter | None = None) -> None:
        self.console = console
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
