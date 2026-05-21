"""Built-in starter file templates for `nightshift init`."""

NIGHTSHIFT_YAML = """project:
  name: example-project
  root: .
  task_file: tasks.md
  artifact_dir: .nightshift

safety:
  require_clean_worktree: false
  scoped_paths:
    - .
  allowed_commands:
    - python -m unittest
  forbidden_commands:
    - rm -rf
    - git push
    - curl | bash

agents:
  planner:
    backend: command
    command: echo
    system_prompt: agents/planner.md

  implementer:
    backend: command
    command: echo
    system_prompt: agents/implementer.md

  reviewer:
    backend: command
    command: echo
    system_prompt: agents/reviewer.md

  debugger:
    backend: command
    command: echo
    role: debugger
    system_prompt: agents/debugger.md

pipeline:
  max_task_retries: 6
  stages:
    - id: plan
      type: agent
      agent: planner
      output: plan.md

    - id: review_plan
      type: agent_review
      agent: reviewer
      on_fail: plan
      output: plan-review.md

    - id: implement
      type: agent
      agent_pool:
        - implementer
      output: implementation-log.md

    - id: test
      type: command
      commands:
        - python -m unittest
      output: test-output.txt

    - id: review
      type: agent_review
      agent: reviewer
      on_fail: implement
      output: review.md

    - id: summarize
      type: summarize
      output: final-notes.md
"""

TASKS_MD = """# Tasks

- [ ] TASK-001: Add your first NightShift task

Description:
Describe the coding task NightShift should work on.

Acceptance Criteria:
- The expected behavior is clear
- The task can be reviewed from generated artifacts
"""

PLANNER_PROMPT = """# Planner

You are the planning agent for NightShift.

Create a conservative implementation plan for one coding task.

Rules:
- Do not write code.
- Identify relevant files.
- Preserve existing behavior.
- Prefer small changes.
- Include test strategy.
- Include risks.
"""

IMPLEMENTER_PROMPT = """# Implementer

You are the implementation agent for NightShift.

Implement the approved plan inside the scoped project directory.

Rules:
- Make the smallest correct change.
- Do not edit files outside scope.
- Preserve existing style.
- Write useful implementation notes.
"""

DEBUGGER_PROMPT = """# Debugger

You diagnose failed attempts for NightShift.

Output:
- concise diagnosis
- recommended next action
- do not modify guidance

Do not directly modify files.
"""

REVIEWER_PROMPT = """# Reviewer

You are the review agent for NightShift.

Decide whether the current task should pass, retry implementation, retry planning, or fail.

Output exactly:

status: pass | fail | retry | escalate
reason: <short explanation>
next_stage: <optional stage id>
context_update: <compact useful note>
"""

IMAGEBOARD_NIGHTSHIFT_YAML = """project:
  name: imageboard
  root: .
  task_file: .nightshift/tasks.md
  artifact_dir: .nightshift

safety:
  require_clean_worktree: false
  scoped_paths:
    - src
    - tests
    - templates
    - static
    - schema.sql
    - pyproject.toml
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
    system_prompt: .nightshift/agents/planner.md

  implementer:
    backend: ollama
    model: qwen2.5-coder:14b
    temperature: 0.1
    system_prompt: .nightshift/agents/implementer.md

  reviewer:
    backend: ollama
    model: qwen2.5-coder:14b
    temperature: 0.1
    system_prompt: .nightshift/agents/reviewer.md

  debugger:
    backend: ollama
    model: qwen2.5-coder:14b
    role: debugger
    temperature: 0.1
    system_prompt: .nightshift/agents/debugger.md

pipeline:
  max_task_retries: 6
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
      agent_pool:
        - implementer
      output: proposed.patch

    - id: normalize
      type: patch_normalizer
      output: normalized.patch

    - id: validate_patch
      type: patch_validator
      output: patch-validation.md
      max_files: 10
      max_lines: 900
      max_delete_ratio: 0.70
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
"""

IMAGEBOARD_TASKS_MD = """# Tasks

- [ ] TASK-001: Board and thread foundation

Description:
Create the initial Flask imageboard application. Implement the board and thread data model, SQLite schema, model helpers, `/board/<name>` and `/thread/<id>` routes, and tests. Keep source code under `src/`, tests under `tests/`, HTML templates under `templates/`, and static files under `static/`.

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
"""

REAL_MODEL_PLANNER_PROMPT = """You are the planning agent for NightShift.

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
"""

REAL_MODEL_IMPLEMENTER_PROMPT = """You are the implementation agent for NightShift.

Output only complete file content blocks.
Use one fenced block per file with this exact opening form:
```file:relative/path.py
<complete file content>
```
Do not include explanations before or after the file blocks.
Include tests when needed.
Keep the change as small as possible.
Only edit files needed for the task.
"""

REAL_MODEL_REVIEWER_PROMPT = """You are the review agent for NightShift.

Review the task, plan, patch artifacts, test output, and final state.

Output exactly:

status: pass | fail | retry | escalate
reason: <short explanation>
next_stage: <optional stage id>
context_update: <compact useful note>

Use retry when the implementation is close but needs another patch.
Use fail when the patch is unsafe, unrelated, or clearly broken.
Use pass only when the acceptance criteria are satisfied.
"""

REAL_MODEL_DEBUGGER_PROMPT = """You are the debugger agent for NightShift.

Diagnose failed attempts without editing files.

Use the task, current patch, failure output, and retry history to produce:
- concise diagnosis
- recommended next action
- do not modify guidance
"""

IMAGEBOARD_README = """# NightShift Imageboard Target

This project was created with:

```bash
nightshift init --template imageboard
```

NightShift control files live in `.nightshift/`. Target application code should live under `src/`, tests under `tests/`, templates under `templates/`, and uploaded/generated static files under `static/`.

Install target dependencies:

```bash
python -m pip install flask pillow pytest
```

Validate the project:

```bash
nightshift validate
```

Run the first task:

```bash
nightshift run --task TASK-001
```
"""
