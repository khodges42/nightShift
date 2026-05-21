"""Pastebin tutorial application scaffold."""

from __future__ import annotations

from flask import Flask


def create_app(database_path: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config["DATABASE_PATH"] = database_path
    return app
