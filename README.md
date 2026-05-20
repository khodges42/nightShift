# NightShift

<p align="center">
  <img src="docs/images/logo.png" width="220">
</p>

Auditable local-first AI coding pipelines.

NightShift is a deterministic pipeline runner for AI-assisted coding work. It reads markdown tasks, builds bounded context, asks configured agents for plans or patches, validates and applies those patches through explicit stages, runs checks, and leaves a human-reviewable artifact trail.

NightShift is not an autonomous software engineer. It is an orchestration layer that treats AI agents as unreliable workers inside bounded, testable, auditable workflows.

## Current Status

NightShift now supports the full local patch workflow:

- `nightshift init`, `validate`, `status`, `run`, `run --task`, `run --all`, and `web`.
- Markdown task parsing with dependencies.
- Command, Ollama, and OpenAI-compatible agent backends.
- Per-agent model settings such as `temperature`.
- Repo lookup tools: scoped `list_files`, `read_file`, and `grep`.
- Planner lookup requests with `files-inspected.md` artifacts.
- `repo_context` stage for `context-pack.md`.
- Project context chart generation at `.nightshift/project-context-chart.md`.
- `code_writer` stage for direct unified diff output.
- `file_writer` stage for model-written complete file blocks with deterministic diff generation.
- `patch_normalizer`, `patch_validator`, and `patch_apply` stages.
- Patch dry-run and apply modes.
- Test/static failure repair loops through existing retry routing.
- Run logs, dashboard log tails, git status artifacts, diffs, stage summaries, and final reports.

The default posture remains local-first and review-first: agents propose; NightShift validates, applies, tests, and records.

## What NightShift Is

NightShift is built for reviewable automation:

- local-first execution
- declarative pipeline stages
- markdown task files
- command-backed and model-backed agent wrappers
- explicit retry limits
- scoped repository lookup
- patch validation before mutation
- command allowlists
- durable markdown/text artifacts
- compact context handoff
- final reports for human review

The goal is to wake up to useful artifacts and a repository state you can inspect.

## What NightShift Is Not

NightShift does not push branches, deploy software, run unbounded task swarms, or grant agents unlimited repository access. Human review remains the final authority.

## Install

Repo setup scripts can install NightShift in editable mode, check for Ollama, and offer to add the Python scripts directory to PATH.

Windows PowerShell:

```powershell
.\setup.ps1
```

macOS/Linux:

```bash
sh ./setup.sh
```

Development install:

```bash
pip install -e .
```

You can also run the CLI module directly from a checkout:

```bash
python -m nightshift.cli --help
```

NightShift uses the Python standard library for runtime behavior where practical. PyYAML is used automatically if installed, but starter configs work with the built-in YAML subset parser.

## Getting Started

Start with the [Quickstart](QUICKSTART.md). It uses deterministic fake agents so you can verify lookup, context generation, patch validation, patch apply, tests, and artifacts without installing a model.

After that works, continue with [Tutorial 01: Building A Small Imageboard With Real Local Models](examples/tutorial/01-imageboard/README.md). It swaps the fake agents for Ollama-backed agents such as `qwen2.5-coder:14b` and walks through a small Flask/SQLite project with ordinary web-app tasks.

### Quickstart Commands

Validate the included end-to-end patch example:

```bash
python -m nightshift.cli validate --config examples/quickstart-lisp/nightshift.yaml
```

Run the first task against a copy of the example project. The pipeline uses `patch_apply mode: apply`, so running it directly against `examples/quickstart-lisp/` will modify those files.

```bash
cp -r examples/quickstart-lisp /tmp/nightshift-quickstart
python -m nightshift.cli run --config /tmp/nightshift-quickstart/nightshift.yaml --task TASK-001
```

For a new project:

```bash
nightshift init
nightshift validate
nightshift status
nightshift run --task TASK-001
```

For the first real-model tutorial target:

```bash
nightshift init --template tutorial-imageboard --root nightshift-imageboard
```

Other built-in real-model templates:

```bash
nightshift init --template real-simple --root bookmarks-demo
nightshift init --template real-long-running --root incident-service
nightshift init --template tutorial-pastebin --root nightshift-pastebin
```

Create an isolated integration sandbox for a template:

```bash
python -m nightshift.cli integ-run --template tutorial-pastebin
cd integ_runs/<timestamp>/project
```

Activate the generated virtual environment, then install and run the project.

PowerShell:

```powershell
..\.venv\Scripts\Activate.ps1
python -m pip install -e ..\..\..
python -m pip install -e . pytest flask
python -m nightshift.cli validate
python -m nightshift.cli run --task TASK-001
```

Bash:

```bash
source ../.venv/bin/activate
python -m pip install -e ../../..
python -m pip install -e . pytest flask
python -m nightshift.cli validate
python -m nightshift.cli run --task TASK-001
```

Open the read-only artifact dashboard:

```bash
pip install flask
nightshift web
```

## Task File Example

Tasks live in markdown checklist format:

```markdown
# Tasks

- [ ] TASK-001: Add parser support

Description:
Implement parsing for the target language.

Acceptance Criteria:
- Parses numbers
- Parses symbols
- Parses nested lists
- Includes unit tests
```

NightShift parses task id, title, completion state, description, acceptance criteria, dependency bullets, and raw task markdown.

## Pipeline Example

```yaml
pipeline:
  max_task_retries: 2
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
      max_lines: 800
      on_fail: implement

    - id: apply_patch
      type: patch_apply
      mode: apply
      output: patch-apply-output.txt
      on_fail: implement

    - id: test
      type: command
      commands:
        - python -m unittest discover -v
      output: test-output.txt
      on_fail: implement

    - id: review
      type: agent_review
      agent: reviewer
      on_fail: implement
      output: review.md
```

Use `mode: dry_run` for patch applicability checks without modifying files. Use `mode: apply` to write the validated patch to the target project.

## Agent Backends

NightShift supports:

- `backend: command`
- `backend: ollama`
- `backend: openai_compatible`

Example Ollama agent:

```yaml
agents:
  implementer:
    backend: ollama
    model: qwen2.5-coder:14b
    base_url: http://localhost:11434
    temperature: 0.2
    system_prompt: agents/implementer.md
```

The Ollama backend uses the local HTTP API instead of `ollama run`, which keeps exact patch output away from terminal rendering and line wrapping.

Example OpenAI-compatible agent:

```yaml
agents:
  implementer:
    backend: openai_compatible
    model: local-model
    base_url: http://localhost:11434/v1
    api_key_env: OPENAI_API_KEY
    temperature: 0.2
    system_prompt: agents/implementer.md
```

NightShift passes prompt bundles to agents and persists stdout, stderr, exit code, duration, and prompt artifacts. `code_writer` agents return unified diffs directly. `file_writer` agents return complete file blocks, and NightShift generates the unified diff deterministically. On retries, patch artifacts are versioned by attempt, for example `repair-1.patch`, `normalized-1.patch`, and `patch-validation-1.md`.

Review agents should emit:

```yaml
status: pass | fail | retry | escalate
reason: <short explanation>
next_stage: <optional stage id>
context_update: <compact useful note>
```

## Safety Model

NightShift validates paths, commands, and patches before mutation.

Path safety:

- project roots are resolved with `pathlib`
- task and prompt files must stay inside the project root
- artifact paths cannot escape `.nightshift/`
- repo lookup tools are constrained by `safety.scoped_paths`

Command safety:

- command stages must match `allowed_commands`
- forbidden fragments are blocked before allowlist acceptance
- command output and exit codes are recorded
- command stages stop at the first failing or timed-out command

Patch safety:

- code changes are represented as unified diffs, either supplied directly or generated from complete file blocks
- patches are normalized and validated before apply
- path traversal and forbidden paths are rejected
- scoped paths, max files, and max changed lines are enforced
- `patch_apply` records apply output and git status artifacts

## Artifact Layout

A run creates human-readable artifacts:

```text
.nightshift/
  project-context.md
  project-context-chart.md
  nightshift.log
  runs/
    <run-id>/
      run.log
      run-summary.md
      config.snapshot.yaml
      run-metadata.md
      prompts/
        <agent-id>.md
      tasks/
        TASK-001/
          task.md
          context.md
          files-inspected.md
          context-pack.md
          plan.md
          proposed.patch
          repair-1.patch
          normalized.patch
          normalized-1.patch
          patch-validation.md
          patch-validation-1.md
          applied.patch
          applied-1.patch
          patch-apply-output.txt
          patch-apply-output-1.txt
          test-output.txt
          review.md
          stage-results.md
          context-out.md
          task-completion.md
          diff.patch
          final-notes.md
```

Exact artifact names depend on configured stage `output` values.

## Development

Run tests:

```bash
python -m unittest discover -v
```

Compile-check modules:

```bash
python -m compileall nightshift tests
```

Additional docs:

- [Quickstart](QUICKSTART.md)
- [Tutorial 01: imageboard with real local models](examples/tutorial/01-imageboard/README.md)
- [Tutorial 02: Lisp with real local models](examples/tutorial/02-lisp/README.md)
- [Tutorial 03: Pastebin with model fallback and telemetry](examples/tutorial/03-pastebin/README.md)
- [Config reference](docs/config-reference.md)
- [Artifact review workflow](docs/artifact-review.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Quickstart Lisp example](examples/quickstart-lisp/)

## Roadmap

The active roadmap now lives in [docs/design.md](docs/design.md). Completed phase checklists are cleared from that document so it stays focused on the current platform shape and the next important work.
