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
    devlog: str
    status: str
    log_tail: tuple[str, ...] = ()
    artifacts: tuple[str, ...] = ()


def list_runs(artifact_dir: str | Path) -> list[RunInfo]:
    runs_dir = Path(artifact_dir) / "runs"
    if not runs_dir.exists():
        return []
    runs: list[RunInfo] = []
    for path in sorted((item for item in runs_dir.iterdir() if item.is_dir()), reverse=True):
        summary_path = path / "run-summary.md"
        devlog_path = path / "devlog.md"
        summary = summary_path.read_text(encoding="utf-8") if summary_path.exists() else "No run summary yet."
        devlog = devlog_path.read_text(encoding="utf-8") if devlog_path.exists() else "No devlog yet."
        runs.append(
            RunInfo(
                name=path.name,
                path=path,
                summary=summary,
                devlog=devlog,
                status=_status_from_summary(summary),
                log_tail=tuple(tail_lines(path / "run.log", limit=100)),
                artifacts=tuple(_artifact_paths(path)),
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
        '<meta http-equiv="refresh" content="5">',
        _style_block(),
        '<main class="shell">',
        '<header class="hero">',
        '<div class="brand"><img src="/assets/logo.png" alt="NightShift logo"><div><p class="eyebrow">Local artifact dashboard</p><h1>NightShift</h1></div></div>',
        '<div class="hero-copy">Read-only run review. Auto-refreshes every 5 seconds.</div>',
        "</header>",
    ]
    if not runs:
        body.append('<section class="empty">No runs found.</section>')
    for index, run in enumerate(runs):
        title = "Latest Run" if index == 0 else "Older Run"
        status_class = _status_class(run.status)
        artifact_links = "\n".join(
            f'<a class="artifact-link" href="/runs/{escape(run.name)}/{escape(path)}">{escape(path)}</a>'
            for path in run.artifacts[:18]
        )
        artifact_body = artifact_links or '<span class="muted">No artifacts yet.</span>'
        body.extend(
            [
                '<section class="run-card">',
                '<div class="run-head">',
                f'<div><p class="run-kicker">{title}</p><h2>{escape(run.name)}</h2></div>',
                f'<span class="status {status_class}">{escape(run.status.upper())}</span>',
                "</div>",
                '<div class="grid">',
                '<article class="panel span-2">',
                "<h3>Devlog</h3>",
                '<pre class="prose">',
                escape(run.devlog),
                "</pre>",
                "</article>",
                '<article class="panel">',
                "<h3>Run Summary</h3>",
                '<pre class="prose">',
                escape(run.summary),
                "</pre>",
                "</article>",
                '<article class="panel">',
                "<h3>Log Tail</h3>",
                '<pre class="log">',
                escape("\n".join(run.log_tail) if run.log_tail else "No run log yet."),
                "</pre>",
                "</article>",
                '<article class="panel span-2">',
                "<h3>Artifacts</h3>",
                f'<div class="artifact-grid">{artifact_body}</div>',
                "</article>",
                "</div>",
                "</section>",
            ]
        )
    body.append("</main>")
    return "\n".join(["<!doctype html>", '<html lang="en"><body>', *body, "</body></html>"])


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
        response = Response(
            "\n".join(
                [
                    "<!doctype html>",
                    '<html lang="en"><body>',
                    _style_block(),
                    '<main class="shell">',
                    f'<a class="back-link" href="/">Back to dashboard</a>',
                    f'<section class="panel"><h1>{escape(artifact_path)}</h1><pre class="prose">{escape(content)}</pre></section>',
                    "</main>",
                    "</body></html>",
                ]
            ),
            mimetype="text/html",
        )
        response.headers["Cache-Control"] = "no-store, max-age=0"
        return response

    @app.get("/assets/logo.png")
    def logo():
        logo_path = root / "docs" / "images" / "logo.png"
        if not logo_path.exists():
            return Response(status=404)
        response = Response(logo_path.read_bytes(), mimetype="image/png")
        response.headers["Cache-Control"] = "no-store, max-age=0"
        return response

    return app


def _artifact_paths(run_path: Path) -> list[str]:
    if not run_path.exists():
        return []
    paths = [
        path.relative_to(run_path).as_posix()
        for path in run_path.rglob("*")
        if path.is_file()
    ]
    priority = {
        "devlog.md": 0,
        "run-summary.md": 1,
        "run.log": 2,
    }
    return sorted(paths, key=lambda item: (priority.get(item, 10), item))


def _status_from_summary(summary: str) -> str:
    for line in summary.splitlines():
        normalized = line.strip().lower()
        if normalized.startswith("- status:"):
            return normalized.split(":", 1)[1].strip() or "running"
        if normalized.startswith("status:"):
            return normalized.split(":", 1)[1].strip() or "running"
    return "running"


def _status_class(status: str) -> str:
    normalized = status.lower()
    if normalized in {"complete", "completed", "pass", "passed"}:
        return "complete"
    if normalized in {"failed", "fail", "error"}:
        return "failed"
    return "running"


def _style_block() -> str:
    return """
<style>
:root {
  color-scheme: dark;
  --bg: #070a12;
  --panel: #101622;
  --panel-2: #141c2a;
  --line: #263246;
  --text: #e7edf7;
  --muted: #93a4ba;
  --blue: #7dd3fc;
  --green: #86efac;
  --red: #fca5a5;
  --amber: #fcd34d;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background:
    radial-gradient(circle at 20% 0%, rgba(56, 189, 248, .16), transparent 32rem),
    linear-gradient(180deg, #070a12 0%, #0b1020 100%);
  color: var(--text);
  font: 14px/1.5 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.shell { width: min(1320px, calc(100vw - 32px)); margin: 0 auto; padding: 28px 0 48px; }
.hero, .run-head { display: flex; align-items: center; justify-content: space-between; gap: 20px; }
.hero { margin-bottom: 26px; }
.brand { display: flex; align-items: center; gap: 14px; min-width: 0; }
.brand img { width: 58px; height: 58px; object-fit: contain; filter: drop-shadow(0 10px 24px rgba(125, 211, 252, .18)); }
.eyebrow, .run-kicker { margin: 0 0 4px; color: var(--blue); font-size: 12px; text-transform: uppercase; letter-spacing: .12em; }
h1, h2, h3 { margin: 0; letter-spacing: 0; }
h1 { font-size: 40px; line-height: 1; }
h2 { font-size: 18px; }
h3 { font-size: 13px; color: var(--muted); text-transform: uppercase; letter-spacing: .10em; margin-bottom: 12px; }
.hero-copy { color: var(--muted); max-width: 420px; text-align: right; }
.run-card, .empty {
  border: 1px solid var(--line);
  background: rgba(16, 22, 34, .84);
  border-radius: 8px;
  padding: 18px;
  box-shadow: 0 18px 60px rgba(0, 0, 0, .32);
  margin-bottom: 18px;
}
.status {
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 700;
}
.status.complete { color: var(--green); border-color: rgba(134, 239, 172, .45); background: rgba(22, 101, 52, .22); }
.status.failed { color: var(--red); border-color: rgba(252, 165, 165, .45); background: rgba(127, 29, 29, .22); }
.status.running { color: var(--amber); border-color: rgba(252, 211, 77, .45); background: rgba(113, 63, 18, .22); }
.grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; margin-top: 16px; }
.panel {
  min-width: 0;
  border: 1px solid var(--line);
  background: linear-gradient(180deg, var(--panel-2), var(--panel));
  border-radius: 8px;
  padding: 14px;
}
.span-2 { grid-column: span 2; }
pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font: 12px/1.55 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
.prose { max-height: 460px; overflow: auto; color: #dbe6f6; }
.log { max-height: 360px; overflow: auto; color: #bdd0e7; }
.artifact-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.artifact-link, .back-link {
  color: var(--blue);
  text-decoration: none;
  border: 1px solid rgba(125, 211, 252, .22);
  background: rgba(14, 116, 144, .12);
  border-radius: 6px;
  padding: 8px 10px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.artifact-link:hover, .back-link:hover { border-color: rgba(125, 211, 252, .55); background: rgba(14, 116, 144, .2); }
.back-link { display: inline-block; margin-bottom: 14px; }
.muted { color: var(--muted); }
@media (max-width: 900px) {
  .hero, .run-head { align-items: flex-start; flex-direction: column; }
  .brand img { width: 48px; height: 48px; }
  .hero-copy { text-align: left; }
  .grid { grid-template-columns: 1fr; }
  .span-2 { grid-column: span 1; }
  .artifact-grid { grid-template-columns: 1fr; }
}
</style>
"""
