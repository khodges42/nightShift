from __future__ import annotations

from datetime import datetime, timezone
import sqlite3
from pathlib import Path

from flask import Flask, abort, g, jsonify, redirect, render_template, request, url_for


SCHEMA = """
create table if not exists snippets (
  id integer primary key autoincrement,
  title text not null,
  body text not null,
  language text default '',
  tags text default '',
  expires_at text default '',
  created_at text not null
);
"""


def create_app(database_path: str | Path | None = None) -> Flask:
    app = Flask(__name__, template_folder=str(Path(__file__).resolve().parents[2] / "templates"))
    app.config["DATABASE"] = str(database_path or Path(app.instance_path) / "pastebin.sqlite3")

    @app.before_request
    def _open_db() -> None:
        Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute(SCHEMA)

    @app.teardown_request
    def _close_db(exc) -> None:
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.get("/")
    def index():
        snippets = list_snippets(g.db, request.args)
        return render_template("index.html", snippets=snippets)

    @app.get("/new")
    def new_snippet():
        return render_template("new.html")

    @app.post("/snippets")
    def create_snippet_route():
        snippet_id = create_snippet(g.db, request.form or request.json or {})
        wants_json = request.is_json or "application/json" in request.headers.get("Accept", "")
        if wants_json:
            return jsonify(get_snippet(g.db, snippet_id)), 201
        return redirect(url_for("view_snippet", snippet_id=snippet_id))

    @app.get("/snippets")
    def list_snippets_route():
        snippets = list_snippets(g.db, request.args)
        if "application/json" in request.headers.get("Accept", ""):
            return jsonify(snippets)
        return render_template("index.html", snippets=snippets)

    @app.get("/snippets/<int:snippet_id>")
    def view_snippet(snippet_id: int):
        snippet = get_snippet(g.db, snippet_id)
        if snippet is None:
            abort(404)
        if is_expired(snippet):
            abort(410)
        if "application/json" in request.headers.get("Accept", ""):
            return jsonify(snippet)
        return render_template("view.html", snippet=snippet)

    return app


def create_snippet(db: sqlite3.Connection, data) -> int:
    title = str(data.get("title", "")).strip()
    body = str(data.get("body", "")).strip()
    if not title or not body:
        raise ValueError("title and body are required")
    cursor = db.execute(
        "insert into snippets(title, body, language, tags, expires_at, created_at) values (?, ?, ?, ?, ?, ?)",
        (
            title,
            body,
            str(data.get("language", "")).strip(),
            str(data.get("tags", "")).strip(),
            str(data.get("expires_at", "")).strip(),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    db.commit()
    return int(cursor.lastrowid)


def get_snippet(db: sqlite3.Connection, snippet_id: int) -> dict | None:
    row = db.execute("select * from snippets where id = ?", (snippet_id,)).fetchone()
    return dict(row) if row else None


def list_snippets(db: sqlite3.Connection, args) -> list[dict]:
    rows = db.execute("select * from snippets order by id desc").fetchall()
    snippets = [dict(row) for row in rows if not is_expired(dict(row))]
    query = str(args.get("q", "")).lower()
    language = str(args.get("language", "")).lower()
    tag = str(args.get("tag", "")).lower()
    if query:
        snippets = [item for item in snippets if query in item["title"].lower() or query in item["body"].lower()]
    if language:
        snippets = [item for item in snippets if item["language"].lower() == language]
    if tag:
        snippets = [item for item in snippets if tag in [part.strip().lower() for part in item["tags"].split(",")]]
    return snippets


def is_expired(snippet: dict) -> bool:
    value = snippet.get("expires_at") or ""
    if not value:
        return False
    try:
        expires = datetime.fromisoformat(value)
    except ValueError:
        return False
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return expires <= datetime.now(timezone.utc)
