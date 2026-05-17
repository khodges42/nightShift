"""Read-only web dashboard for NightShift artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path

from .errors import NightShiftError
from .runlog import tail_lines


@dataclass(frozen=True)
class RunInfo:
    name: str
    path: Path
    summary: str
    log_tail: tuple[str, ...] = ()


def list_runs(artifact_dir: str | Path) -> list[RunInfo]:
    runs_dir = Path(artifact_dir) / "runs"
    if not runs_dir.exists():
        return []
    runs: list[RunInfo] = []
    for path in sorted((item for item in runs_dir.iterdir() if item.is_dir()), reverse=True):
        summary_path = path / "run-summary.md"
        summary = summary_path.read_text(encoding="utf-8") if summary_path.exists() else "No run summary yet."
        runs.append(
            RunInfo(
                name=path.name,
                path=path,
                summary=summary,
                log_tail=tuple(tail_lines(path / "run.log", limit=100)),
            )
        )
    return runs


def read_artifact(run_path: Path, relative_path: str) -> str:
    candidate = (run_path / relative_path).resolve()
    try:
        candidate.relative_to(run_path.resolve())
    except ValueError:
        return "Artifact path escapes run directory."
    if not candidate.exists() or not candidate.is_file():
        return "Artifact not found."
    return candidate.read_text(encoding="utf-8", errors="replace")


def render_dashboard(artifact_dir: str | Path) -> str:
    runs = list_runs(artifact_dir)
    body = [
        "<h1>NightShift Dashboard</h1>",
        '<meta http-equiv="refresh" content="5">',
        "<p>Showing artifact files from the newest run first. This page is read-only and refreshes every 5 seconds.</p>",
    ]
    if not runs:
        body.append("<p>No runs found.</p>")
    for index, run in enumerate(runs):
        title = "Latest Run" if index == 0 else "Older Run"
        body.extend(
            [
                f"<section><h2>{title}: {escape(run.name)}</h2>",
                "<pre>",
                escape(run.summary),
                "</pre>",
                "<h3>Log Tail</h3>",
                "<pre>",
                escape("\n".join(run.log_tail) if run.log_tail else "No run log yet."),
                "</pre>",
                "</section>",
            ]
        )
    return "\n".join(["<!doctype html>", "<html><body>", *body, "</body></html>"])


def create_app(project_root: str | Path = ".", artifact_dir: str | Path = ".nightshift"):
    try:
        from flask import Flask, Response
    except ModuleNotFoundError as exc:
        raise NightShiftError(
            "Web dashboard requires Flask. Install it with `pip install flask`."
        ) from exc

    root = Path(project_root).resolve()
    artifacts = root / artifact_dir
    app = Flask(__name__)

    @app.get("/")
    def index():
        response = Response(render_dashboard(artifacts), mimetype="text/html")
        response.headers["Cache-Control"] = "no-store, max-age=0"
        return response

    @app.get("/runs/<run_id>/<path:artifact_path>")
    def artifact(run_id: str, artifact_path: str):
        content = read_artifact(artifacts / "runs" / run_id, artifact_path)
        response = Response(f"<pre>{escape(content)}</pre>", mimetype="text/html")
        response.headers["Cache-Control"] = "no-store, max-age=0"
        return response

    return app
