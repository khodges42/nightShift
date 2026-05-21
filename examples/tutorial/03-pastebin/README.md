# Tutorial 03: Pastebin With Model Fallback And Telemetry

This tutorial uses the `tutorial-pastebin` template: a small Flask snippet-hosting service designed for deterministic NightShift orchestration tests.

It is intentionally simpler than the imageboard tutorial. There are no uploads, thumbnails, sessions, or moderation queues. The work is ordinary web-app behavior: snippet creation, viewing, listing, filtering, expiration handling, and simple HTML forms.

## What The Template Creates

Run this from a disposable parent directory:

```bash
nightshift init --template tutorial-pastebin --root nightshift-pastebin
cd nightshift-pastebin
```

For an isolated local integration run, use the integration sandbox command from the NightShift repository root:

```bash
python -m nightshift.cli integ-run --template tutorial-pastebin
```

To create the sandbox and set up the Python project immediately:

```bash
python -m nightshift.cli integ-run --template tutorial-pastebin --setup
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
  pastebin_app/
templates/
tests/
pyproject.toml
README.md
```

The template intentionally does not include a working Flask app or pre-generated task tests. For each task, NightShift first generates acceptance tests from the current task's acceptance criteria, reviews those tests for scope, and then asks the implementation agent to make them pass.

## Prerequisites

Install NightShift from this repository:

```bash
python -m pip install -e .
```

Install target dependencies:

```bash
python -m pip install -e . pytest flask
```

Install and start Ollama, then pull the fallback models you want available:

```bash
ollama pull qwen2.5-coder:14b
ollama pull carstenuhlig/omnicoder-9b
ollama pull deepseek-coder-v2:16b
ollama list
```

NightShift uses Ollama's local HTTP API, normally at `http://localhost:11434`.

## Model Fallback

The template writes tests with `qwen2.5-coder:14b`. The implementation stage uses this fallback order:

1. `qwen2.5-coder:14b`
2. `carstenuhlig/omnicoder-9b`
3. `deepseek-coder-v2:16b`

NightShift records which agent/model handled each stage in `telemetry-summary.md`.

## TDD Pipeline

The task pipeline runs in this shape:

```text
plan -> semantic_context -> context -> write_tests -> review_tests -> implement -> pytest -> review
```

Generated tests should cover only the current task. They are expected to fail before implementation, so the pipeline reviews the test patch but does not run pytest until after the implementation patch is applied.

## Task Plan

The template writes the full task list to `.nightshift/tasks.md`. A copy is included here as [tasks.md](tasks.md).

1. Snippet creation and viewing
2. Snippet listing and filtering
3. Expiration handling
4. HTML forms and templates

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

A copy of the template pipeline is included here as [nightshift.yaml](nightshift.yaml). The canonical runnable template lives under `nightshift/project_templates/tutorial-pastebin/`.
