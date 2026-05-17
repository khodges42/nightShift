"""Operational run logging for NightShift."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .artifacts import ArtifactStore


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

    def bind(self, artifacts: ArtifactStore) -> None:
        artifacts.initialize_run()
        self._run_log_path = artifacts.run_log_path
        self._aggregate_log_path = artifacts.aggregate_log_path

    def event(self, event: str, message: str, **fields: object) -> None:
        safe_fields = _redact_fields(fields)
        line = format_log_line(LogEvent(event=event, message=message, fields=safe_fields))
        if self.console is not None:
            self.console(line)
        for path in (self._run_log_path, self._aggregate_log_path):
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
    parts = [timestamp, log_event.event, log_event.message]
    for key, value in sorted(log_event.fields.items()):
        if value is None or value == "":
            continue
        parts.append(f"{key}={_format_value(value)}")
    return " | ".join(parts)


def tail_lines(path: Path, limit: int = 100) -> list[str]:
    if limit <= 0:
        return []
    if not path.exists() or not path.is_file():
        return []
    return path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]


def _format_value(value: object) -> str:
    text = str(value).replace("\n", " ").replace("\r", " ")
    return text if text else ""


def _redact_fields(fields: dict[str, object]) -> dict[str, object]:
    redacted: dict[str, object] = {}
    for key, value in fields.items():
        lowered = key.lower()
        if any(marker in lowered for marker in ("secret", "token", "password", "key")):
            redacted[key] = "<redacted>"
        else:
            redacted[key] = value
    return redacted
