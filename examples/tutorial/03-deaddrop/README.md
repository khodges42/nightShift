# Tutorial 03: DeadDrop With Fixed Tests And Telemetry

This tutorial uses the `tutorial-deaddrop` template: a small Flask snippet sharing utility designed for deterministic NightShift orchestration tests.

It is intentionally simpler than the imageboard tutorial. There are no uploads, thumbnails, sessions, or moderation queues. The work is ordinary web-app behavior: snippet creation, viewing, listing, filtering, expiration handling, and simple HTML forms.

## What The Template Creates

Run this from a disposable parent directory:

```bash
nightshift init --template tutorial-deaddrop --root nightshift-deaddrop
cd nightshift-deaddrop
```

For an isolated local integration run, use the integration sandbox command from the NightShift repository root:

```bash
python -m nightshift.cli integ-run --template tutorial-deaddrop
```

To create, set up, validate, and run one task in a single command:

```bash
python -m nightshift.cli integ-test --template tutorial-deaddrop --task TASK-001
```

To create the sandbox and set up the Python project immediately:

```bash
python -m nightshift.cli integ-run --template tutorial-deaddrop --setup
```

Then set up the generated Python project:

```bash
python -m nightshift.cli integ-setup --project integ_runs/<timestamp>/project
```

`integ-setup` cannot activate the venv for your current shell. In PowerShell, activate it manually if you want plain `python` and `nightshift` to use the integration venv:

```powershell
integ_runs\<timestamp>\.venv\Scripts\Activate.ps1
```

The template creates:

```text
nightshift.yaml
.nightshift/
  agents/
    planner.md
    test-writer.md
    implementer.md
    debugger.md
    reviewer.md
  tasks.md
src/
  deaddrop_app/
templates/
tests/
pyproject.toml
README.md
```

The template includes a tiny Flask `create_app(database_path=None)` scaffold and fixed tests for each tutorial task. The default tutorial pipeline asks the implementation agent to make only the current task's deterministic tests pass before review.

## Prerequisites

Install NightShift from this repository:

```bash
python -m pip install -e .
```

Install target dependencies:

```bash
python -m pip install -e . pytest flask
```

Install and start Ollama, then pull the default DeadDrop model:

```bash
ollama pull qwen3-coder:30b
ollama list
```

NightShift uses Ollama's local HTTP API, normally at `http://localhost:11434`.

## Model

The default DeadDrop pipeline uses one strong local coder model:

- `qwen3-coder:30b`

NightShift records which agent/model handled each stage in `telemetry-summary.md`. Multi-candidate fallback belongs in a separate experiment template, not the default DeadDrop reliability harness.

## TDD Pipeline

The task pipeline runs in this shape:

```text
plan -> semantic_context -> context -> implement -> pytest -> review
```

The default template uses fixed task tests instead of model-generated tests. This keeps the tutorial focused on implementation and NightShift orchestration instead of letting a test-writing model invent an incompatible architecture.

## Task Plan

The template writes the full task list to `.nightshift/tasks.md`. A copy is included here as [tasks.md](tasks.md).

1. Snippet creation and viewing
2. Snippet metadata fields
3. Snippet listing and filtering
4. Expiration handling
5. HTML forms and templates

Run one task first:

```bash
python -m nightshift.cli validate
python -m nightshift.cli run --task TASK-001
python -m nightshift.cli what-happened
```

Then inspect:

```text
.nightshift/runs/<run-id>/devlog.md
.nightshift/runs/<run-id>/telemetry-summary.md
.nightshift/runs/<run-id>/tasks/TASK-001/semantic-context.md
.nightshift/runs/<run-id>/tasks/TASK-001/telemetry-summary.md
.nightshift/runs/<run-id>/tasks/TASK-001/artifact-index.md
.nightshift/runs/<run-id>/tasks/TASK-001/test-output.txt
```

## Pipeline Reference

A copy of the template pipeline is included here as [nightshift.yaml](nightshift.yaml). The canonical runnable template lives under `nightshift/project_templates/tutorial-deaddrop/`.
