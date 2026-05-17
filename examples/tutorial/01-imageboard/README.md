# Tutorial 01: Building A Small Imageboard With Real Local Models

This tutorial starts after the quickstart. The quickstart uses fake command agents so you can verify the pipeline deterministically. Here, you will point NightShift at a small web application and let a local model implement one feature slice at a time.

The target is a compact 4chan-style imageboard: boards, threads, replies, images, tripcodes, sessions, reports, and moderation. That is larger than a toy parser, but it is a better first real-model target because each task maps to ordinary web-app files and tests.

Keep the first run scoped to `TASK-001`. Let later tasks build on the previous completed task.

## What You Will Build

You will create a disposable Flask project with SQLite and use NightShift to implement:

1. Board and thread data model, routes, SQLite schema, and tests.
2. Image upload and thumbnail generation.
3. Bump ordering and reply counters.
4. Tripcodes and session cookies.
5. Moderation and report queue.

NightShift still controls the workflow. The model proposes code; NightShift validates, applies, tests, records artifacts, and shows the result in the dashboard.

## Prerequisites

Install NightShift from this repository:

```bash
python -m pip install -e .
```

Install runtime dependencies for the target project:

```bash
python -m pip install flask pillow pytest
```

Install and start Ollama, then make sure the model is available:

```bash
ollama pull qwen2.5-coder:14b
ollama list
```

NightShift uses Ollama's local HTTP API, normally at `http://localhost:11434`.

## 1. Create A Scratch Target Project

Do not run apply-mode experiments directly inside the NightShift repo. Create a disposable project.

PowerShell:

```powershell
$TargetProject = "$HOME\Documents\nightshift-imageboard"
New-Item -ItemType Directory -Force $TargetProject
Set-Location $TargetProject
New-Item -ItemType Directory -Force agents, tests, static\uploads, static\thumbs, templates
```

Bash:

```bash
mkdir -p ~/nightshift-imageboard/{agents,tests,static/uploads,static/thumbs,templates}
cd ~/nightshift-imageboard
```

## 2. Add The Starter App

Create `app.py`:

```python
from __future__ import annotations

from pathlib import Path
import sqlite3

from flask import Flask, abort, g, redirect, render_template_string, request, url_for


DATABASE = "imageboard.db"


def create_app(database: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config["DATABASE"] = database or DATABASE
    app.config["UPLOAD_DIR"] = Path("static/uploads")
    app.config["THUMB_DIR"] = Path("static/thumbs")
    app.secret_key = "dev-secret"

    @app.before_request
    def open_db() -> None:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row

    @app.teardown_request
    def close_db(_exc: BaseException | None) -> None:
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.get("/")
    def index():
        return redirect(url_for("board", name="test"))

    @app.get("/board/<name>")
    def board(name: str):
        abort(501)

    @app.get("/thread/<int:thread_id>")
    def thread(thread_id: int):
        abort(501)

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
```

Create `schema.sql`:

```sql
-- NightShift will fill this in during TASK-001.
```

Create `models.py`:

```python
"""Database helpers for the imageboard tutorial."""
```

Create `tests/test_app.py`:

```python
from app import create_app


def test_index_redirects_to_test_board(tmp_path):
    app = create_app(str(tmp_path / "test.db"))
    client = app.test_client()

    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/board/test")
```

## 3. Add NightShift Config

Create `nightshift.yaml`:

```yaml
project:
  name: imageboard
  root: .
  task_file: tasks.md
  artifact_dir: .nightshift

safety:
  require_clean_worktree: false
  scoped_paths:
    - .
  allowed_commands:
    - python -m pytest -q
  forbidden_commands:
    - rm -rf
    - git push
    - curl | bash

experiment:
  label: imageboard-real-model
  prompt_variant: ollama-qwen25-coder-14b-v1

agents:
  planner:
    backend: ollama
    model: qwen2.5-coder:14b
    temperature: 0.2
    system_prompt: agents/planner.md

  implementer:
    backend: ollama
    model: qwen2.5-coder:14b
    temperature: 0.1
    system_prompt: agents/implementer.md

  reviewer:
    backend: ollama
    model: qwen2.5-coder:14b
    temperature: 0.1
    system_prompt: agents/reviewer.md

pipeline:
  max_task_retries: 3
  continue_on_task_failure: false
  stages:
    - id: plan
      type: agent
      agent: planner
      output: plan.md

    - id: context
      type: repo_context
      output: context-pack.md

    - id: implement
      type: file_writer
      agent: implementer
      output: proposed.patch

    - id: normalize
      type: patch_normalizer
      output: normalized.patch

    - id: validate_patch
      type: patch_validator
      output: patch-validation.md
      max_files: 8
      max_lines: 700
      on_fail: implement

    - id: apply_patch
      type: patch_apply
      mode: apply
      output: patch-apply-output.txt
      on_fail: implement

    - id: test
      type: command
      commands:
        - python -m pytest -q
      output: test-output.txt
      shell: true
      timeout_seconds: 20
      on_fail: implement

    - id: review
      type: agent_review
      agent: reviewer
      on_fail: implement
      output: review.md

    - id: summarize
      type: summarize
      output: final-notes.md
```

## 4. Add Agent Prompts

Create `agents/planner.md`:

```markdown
You are the planning agent for NightShift.

Create a concise implementation plan for the current task.

If you need repository context before planning, output lookup requests exactly like this:

lookup_requests:
- tool: read_file
  path: relative/path.py
- tool: grep
  path: .
  pattern: search_regex

After context is provided, write a short plan with:
- files to edit
- tests to add or update
- risks

Do not write code.
```

Create `agents/implementer.md`:

````markdown
You are the implementation agent for NightShift.

Output only complete file content blocks.
Use one fenced block per file with this exact opening form:
```file:relative/path.py
<complete file content>
```
Do not include explanations before or after the file blocks.
Include tests when needed.
Keep the change as small as possible.
Only edit files needed for the task.
````

Create `agents/reviewer.md`:

```markdown
You are the review agent for NightShift.

Review the task, plan, patch artifacts, test output, and final state.

Output exactly:

status: pass | fail | retry | escalate
reason: <short explanation>
next_stage: <optional stage id>
context_update: <compact useful note>

Use retry when the implementation is close but needs another patch.
Use fail when the patch is unsafe, unrelated, or clearly broken.
Use pass only when the acceptance criteria are satisfied.
```

## 5. Add The Task List

Create `tasks.md`:

```markdown
# Tasks

- [ ] TASK-001: Board and thread foundation

Description:
Implement the initial imageboard data model and read routes. Add a SQLite schema and model helpers for boards, threads, and replies. Implement `/board/<name>` and `/thread/<id>` routes with simple HTML responses. Include tests that initialize a temporary database, create board/thread/reply records, and verify both routes.

Acceptance Criteria:
- Defines SQLite tables for boards, threads, and replies
- Provides database initialization and model helper functions
- Implements `/board/<name>` route showing threads for that board
- Implements `/thread/<id>` route showing the thread and replies
- Includes route and model tests using a temporary database

- [ ] TASK-002: Image upload and thumbnails

Dependencies:
- TASK-001

Description:
Add image attachment support for new threads and replies. Store uploaded image metadata in SQLite, save uploaded files under `static/uploads`, and generate thumbnails under `static/thumbs`.

Acceptance Criteria:
- Accepts image uploads for threads and replies
- Stores image filename, thumbnail filename, MIME type, and size
- Generates thumbnails with Pillow
- Rejects unsupported or oversized files
- Includes upload and thumbnail tests

- [ ] TASK-003: Bump ordering and reply counts

Dependencies:
- TASK-002

Description:
Sort board threads by most recent bump. Creating a reply updates the thread bump timestamp and increments reply counters.

Acceptance Criteria:
- Board pages sort threads by latest bump time
- Replies increment thread reply count
- Reply creation updates bump timestamp
- Tests cover ordering and counters

- [ ] TASK-004: Tripcodes and session cookies

Dependencies:
- TASK-003

Description:
Add anonymous names, optional tripcodes, and a session cookie for lightweight poster identity.

Acceptance Criteria:
- Supports optional name and tripcode input
- Stores tripcode hashes without storing raw tripcode secrets
- Sets and reuses a poster session cookie
- Displays stable poster identity on posts
- Includes tripcode and session tests

- [ ] TASK-005: Moderation and report queue

Dependencies:
- TASK-004

Description:
Add post reporting and a simple moderation queue. Moderators can view reports, dismiss reports, and hide reported posts.

Acceptance Criteria:
- Users can report threads and replies
- Reports are stored with reason and timestamp
- Moderation queue lists open reports
- Moderation actions can dismiss reports or hide posts
- Includes moderation and report queue tests
```

## 6. Validate And Run

Validate the project:

```bash
python -m nightshift.cli validate --config nightshift.yaml
```

Run only the first task:

```bash
python -m nightshift.cli run --config nightshift.yaml --task TASK-001
```

Start the dashboard:

```bash
python -m nightshift.cli web --config nightshift.yaml --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/`.

## Notes On Scope

This is still a non-trivial first project. The advantage over a tiny interpreter is that failures are ordinary web-app failures: missing routes, schema mistakes, file handling, or tests. Those are easier to inspect in NightShift artifacts than parser recursion or tokenizer loops.

Keep the tasks sequential. Do not ask the model to implement uploads, tripcodes, or moderation before `TASK-001` is passing.
