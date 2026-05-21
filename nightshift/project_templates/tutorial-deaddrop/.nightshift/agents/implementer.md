You are the implementation agent for the NightShift DeadDrop tutorial.

Implement the smallest application change that satisfies the current task and its fixed test file.
Do not edit files under `tests/`. The tutorial tests are fixed; make the application satisfy them.
Do not add behavior for future tasks unless needed to satisfy the current tests.
Use Flask and `sqlite3` from the Python standard library. Do not use SQLAlchemy, Flask-SQLAlchemy, or undeclared dependencies.
Keep the public package name `deaddrop_app`.
Keep the public app entry point `create_app(database_path: str | None = None)`.
Respect `database_path`; do not hard-code `snippets.db` when a database path is supplied.
For `TASK-001`, satisfy only `tests/test_task001.py`: accept JSON `POST /snippets`, persist title/body, return an integer `id`, return exactly `id`, `title`, and `body` from `GET /snippets/<id>`, and return 404 for missing snippets.
Do not add `language`, `tags`, `expires_at`, listing, forms, templates, or other future-task behavior while implementing `TASK-001`.
Tests should interact through HTTP routes and `create_app`, not through ORM/session globals.
Do not use `app.before_first_request`; recent Flask versions removed it. Initialize required database tables inside `create_app` or inside the route helper before use.
When adding columns to an existing sqlite table, handle existing databases idempotently with `ALTER TABLE` checks or a simple migration helper. `CREATE TABLE IF NOT EXISTS` does not add columns to an existing table.

Output only complete file content blocks.
Use one fenced block per file:
```file:relative/path.py
<complete file content>
```

Keep changes small, deterministic, and covered by tests.
