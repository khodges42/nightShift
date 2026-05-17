"""Read-only web dashboard for NightShift artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path

from .errors import NightShiftError


@dataclass(frozen=True)
class RunInfo:
    name: str
    path: Path
    summary: str


def list_runs(artifact_dir: str | Path) -> list[RunInfo]:
    runs_dir = Path(artifact_dir) / "runs"
    if not runs_dir.exists():
        return []
    runs: list[RunInfo] = []
    for path in sorted((item for item in runs_dir.iterdir() if item.is_dir()), reverse=True):
        summary_path = path / "run-summary.md"
        summary = summary_path.read_text(encoding="utf-8") if summary_path.exists() else "No run summary yet."
        runs.append(RunInfo(name=path.name, path=path, summary=summary))
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
    body = ["<h1>NightShift Dashboard</h1>", '<meta http-equiv="refresh" content="5">']
    if not runs:
        body.append("<p>No runs found.</p>")
    for run in runs:
        body.extend(
            [
                f"<section><h2>{escape(run.name)}</h2>",
                "<pre>",
                escape(run.summary),
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
        return Response(render_dashboard(artifacts), mimetype="text/html")

    @app.get("/runs/<run_id>/<path:artifact_path>")
    def artifact(run_id: str, artifact_path: str):
        content = read_artifact(artifacts / "runs" / run_id, artifact_path)
        return Response(f"<pre>{escape(content)}</pre>", mimetype="text/html")

    return app
