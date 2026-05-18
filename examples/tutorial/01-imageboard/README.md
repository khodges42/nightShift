# Tutorial 01: Building A Small Imageboard With Real Local Models

This tutorial starts after the quickstart. The quickstart uses fake command agents so you can verify the pipeline deterministically. Here, you will use a named NightShift template and let a local model build the target application.

The target is a compact 4chan-style imageboard: boards, threads, replies, images, tripcodes, sessions, reports, and moderation. That is larger than a toy parser, but it is a better first real-model target because failures are ordinary web-app failures: routes, schema, file handling, tests, and model helpers.

## What The Template Creates

Run this from a disposable parent directory:

```bash
nightshift init --template imageboard --root nightshift-imageboard
cd nightshift-imageboard
```

The template creates:

```text
nightshift.yaml
.nightshift/
  agents/
    planner.md
    implementer.md
    reviewer.md
  tasks.md
src/
  imageboard/
tests/
templates/
static/
  uploads/
  thumbs/
```

NightShift control files live in `.nightshift/`. Application source lives under `src/`, tests under `tests/`, HTML templates under `templates/`, and image/static files under `static/`.

The template does not create the Flask app, schema, models, or tests. That is intentional: `TASK-001` asks the agent to create the initial application slice. This is a better exercise of NightShift than pre-building the app and asking for a small patch.

## Prerequisites

Install NightShift from this repository:

```bash
python -m pip install -e .
```

Install target project dependencies:

```bash
python -m pip install flask pillow pytest
```

Install and start Ollama, then make sure the model is available:

```bash
ollama pull qwen2.5-coder:14b
ollama list
```

NightShift uses Ollama's local HTTP API, normally at `http://localhost:11434`.

## Task Plan

The template writes this task sequence to `.nightshift/tasks.md`.

1. Board and thread foundation
   Implement the initial data model, SQLite schema, model helpers, `/board/<name>` and `/thread/<id>` routes, and tests.

2. Image upload and thumbnails
   Add image attachments, metadata, upload storage under `static/uploads`, and thumbnails under `static/thumbs`.

3. Bump ordering and reply counts
   Sort board threads by most recent reply and maintain reply counters.

4. Tripcodes and session cookies
   Add anonymous names, optional tripcodes, and lightweight poster identity.

5. Moderation and report queue
   Add reporting, report queue, dismiss actions, and post hiding.

Run only `TASK-001` first. Do not ask the model to implement uploads, tripcodes, or moderation until the previous tasks pass.

## Validate And Run

Validate the project:

```bash
nightshift validate
```

Run the first task:

```bash
nightshift run --task TASK-001
```

Start the dashboard:

```bash
nightshift web --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/`.

## What To Inspect

Useful artifacts:

```text
.nightshift/runs/<run-id>/devlog.md
.nightshift/runs/<run-id>/run.log
.nightshift/runs/<run-id>/tasks/TASK-001/plan.md
.nightshift/runs/<run-id>/tasks/TASK-001/context-pack.md
.nightshift/runs/<run-id>/tasks/TASK-001/proposed.patch
.nightshift/runs/<run-id>/tasks/TASK-001/test-output.txt
.nightshift/runs/<run-id>/tasks/TASK-001/final-notes.md
```

The dashboard surfaces `devlog.md`, run status, logs, and links to finer-grained artifacts.

## Scope Note

This project is still not tiny. The advantage over a language interpreter is that the model works in familiar web-app territory and failures are easier to inspect. If `TASK-001` fails, read `devlog.md`, `test-output.txt`, and the implementer output before increasing retries or changing prompts.
