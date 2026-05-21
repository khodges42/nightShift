"""Summarize integration run artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .errors import NightShiftError


@dataclass(frozen=True)
class IntegrationReport:
    integration_run: Path
    nightshift_run: Path | None
    lines: tuple[str, ...]


def build_integration_report(root: str | Path = ".", *, latest: bool = True) -> IntegrationReport:
    base = Path(root).resolve() / "integ_runs"
    if not base.exists():
        raise NightShiftError(f"Integration report error: no integ_runs directory found: {base}")
    runs = sorted((path for path in base.iterdir() if path.is_dir()), key=lambda path: path.name, reverse=True)
    if not runs:
        raise NightShiftError(f"Integration report error: no integration runs found under: {base}")
    integration_run = runs[0] if latest else runs[0]
    artifacts_root = integration_run / "project" / ".nightshift" / "runs"
    if not artifacts_root.exists():
        return IntegrationReport(
            integration_run,
            None,
            ("No NightShift run artifacts found. Setup may have failed before task execution.",),
        )
    nightshift_runs = sorted((path for path in artifacts_root.iterdir() if path.is_dir()), key=lambda path: path.name, reverse=True)
    if not nightshift_runs:
        return IntegrationReport(integration_run, None, ("No NightShift run directories found.",))
    nightshift_run = nightshift_runs[0]
    summaries = sorted(nightshift_run.glob("tasks/*/run-summary.md"))
    if not summaries and (nightshift_run / "run-summary.md").exists():
        summaries = [nightshift_run / "run-summary.md"]
    lines = [_summarize_run_summary(path, integration_run) for path in summaries]
    return IntegrationReport(integration_run, nightshift_run, tuple(lines or ("No task summaries found.",)))


def format_integration_report(report: IntegrationReport) -> str:
    lines = [f"Integration run: {report.integration_run}"]
    if report.nightshift_run is not None:
        lines.append(f"NightShift run: {report.nightshift_run}")
    lines.append("")
    lines.extend(f"- {line}" for line in report.lines)
    return "\n".join(lines)


def _summarize_run_summary(path: Path, integration_run: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    task = _field(text, "Task") or path.parent.name
    status = _field(text, "Status") or "unknown"
    retries = _field(text, "Retry count") or "unknown"
    reason = _field(text, "Reason") or "no reason recorded"
    try:
        relative = path.relative_to(integration_run)
    except ValueError:
        relative = path
    return f"{task} {status} after {retries} retries. Reason: {reason}. Artifacts: {relative.parent}"


def _field(text: str, name: str) -> str | None:
    match = re.search(rf"^- {re.escape(name)}:\s*(.+)$", text, flags=re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip()
