# NightShift Config Reference

NightShift config is YAML.

## `project`

- `name`: project display name.
- `root`: project root, resolved relative to the config file.
- `task_file`: markdown task file inside the project root.
- `artifact_dir`: artifact directory inside the project root.

## `safety`

- `require_clean_worktree`: when true, block runs if `git status --short` is dirty or unavailable.
- `scoped_paths`: paths that must resolve inside the project root.
- `allowed_commands`: exact command-stage allowlist entries after whitespace normalization.
- `forbidden_commands`: dangerous fragments blocked before allowlist acceptance.
- `allowed_env`: optional environment variable names to pass to command stages.

## `experiment`

- `label`: optional run experiment label.
- `prompt_variant`: optional prompt variant label.

## `agents`

Supported backends:

- `command`: runs a local command with the prompt on stdin.
- `ollama`: calls the local Ollama HTTP API at `http://localhost:11434/api/generate` by default.
- `openai_compatible`: calls a Chat Completions-compatible HTTP API.

Command agent:

```yaml
planner:
  backend: command
  command: echo
  system_prompt: agents/planner.md
```

Agent roles:

- `role: debugger` marks an agent as diagnosis-only. When a stage fails and a debugger is configured, NightShift sends the task, failed stage output, and retry history to that agent before the next retry.

Stage model routing:

```yaml
agent_pool:
  - small-implementer
  - larger-implementer
```

When `agent_pool` is set, NightShift uses the first agent initially and advances through the list as retry count increases. Each agent still owns its own backend, model, and temperature.

Telemetry:

NightShift writes `telemetry-summary.md` at both run and task scope. The summary estimates prompt/output tokens from captured prompts and responses, records stage runtime, retry count, status, agent id, and model, and groups success/failure statistics per model.

Ollama agent:

```yaml
planner:
  backend: ollama
  model: qwen3-coder:30b
  base_url: http://localhost:11434
  system_prompt: agents/planner.md
  temperature: 0.2
  num_ctx: 8192
  num_predict: 4096
  seed: 1
  stop:
    - STOP
```

Optional Ollama generation options currently supported by NightShift are `temperature`, `num_ctx`, `num_predict`, `seed`, and `stop`.

## `pipeline`

- `max_task_retries`: task retry limit.
- `continue_on_task_failure`: for `run --all`, continue after failed/blocked tasks.
- `stages`: ordered state-machine stages.

Command stage options:

- `commands`: command strings.
- Command strings may use task placeholders: `{task_id}`, `{task_id_lower}`, `{task_id_slug}`, and `{task_id_compact}`.
- `shell`: defaults to true. Set false for argv-style execution.
- `timeout_seconds`: per-stage timeout override.
- `working_dir`: command working directory inside project root.

Patch validator stage options:

- `max_files`: max files changed.
- `max_lines`: max changed lines.
- `max_delete_ratio`: reject deletion-heavy patches above this deleted-line share, from `0.0` to `1.0`.
- `allowed_paths`: optional stage-specific allowlist. If set, every changed path must be inside one of these paths.
- `forbidden_paths`: paths the patch must not touch.
- Unified diff hunk line prefixes and hunk line counts are validated before patch apply.
- The patch normalizer recomputes hunk line counts from hunk bodies for direct unified diff output.

Writer stages:

- `code_writer`: agent returns a unified diff directly.
- `file_writer`: agent returns complete file content blocks; NightShift generates the unified diff deterministically. Prefer this for local models that wrap or miscount long patch hunks.

`file_writer` blocks use this form:

````markdown
```file:relative/path.py
<complete file content>
```
````

Semantic context stage:

```yaml
- id: semantic_context
  type: semantic_context
  output: semantic-context.md
```

This stage builds a lightweight repository index of files, Python symbols, imports, and tests, then writes compact relevant snippets for the current task. It is keyword based with symbol-aware scoring, so it works without a vector database or network dependency.

## Failure, Retry, and Resource Artifacts

Failed command and validation stages write deterministic diagnostics under the task artifact directory:

- `diagnostics/<stage>-failure.md`: failure category, probable root cause, confidence, recommended next action, retry recommendation, modified files, and failing tests.
- `diagnostics/dependency-diagnostic.md`: Python missing-import and manifest guidance when the classifier detects dependency failures.
- `retry-memory.md`: compact summaries of previous attempts.
- `escalation-policy.md`: churn detection result and recommended escalation action.
- `resource-requests.md` plus `resources/`: generated run-local fixtures for supported blocked requests.

Agents can request generated run-local fixtures with a line like:

```text
blocked_request: json fixtures/input.json missing fixture for test
```

Supported fixture types are `png`, `jpg`, `json`, `sqlite`, `text`, and `blob`.

## Integration Runs

`nightshift integ-run` creates a timestamped directory under `integ_runs/` with an isolated virtual environment, initialized template project, logs, transcript, patch, and artifact directories. `integ_runs/` is ignored by git.

Create a local integration sandbox from the NightShift repository root:

```bash
python -m nightshift.cli integ-run --template tutorial-deaddrop
```

Create, set up, validate, and run one task from the generated project directory:

```bash
python -m nightshift.cli integ-test --template tutorial-deaddrop --task TASK-001
```

Set up the generated Python project:

```bash
python -m nightshift.cli integ-setup --project integ_runs/<timestamp>/project
```

The setup helper:

- finds or creates the integration virtual environment
- installs this NightShift checkout into that venv
- installs the target project with `pip install -e`
- installs extra packages, defaulting to `pytest`
- runs `nightshift validate` unless `--skip-validate` is set

Preview commands without running them:

```bash
python -m nightshift.cli integ-setup --project integ_runs/<timestamp>/project --dry-run
```

Summarize the latest integration artifact run:

```bash
python -m nightshift.cli integ-report --latest
```

To clean up old sandboxes before creating a new one, keep only the newest three existing runs:

```bash
python -m nightshift.cli integ-run --template tutorial-deaddrop --keep 3
```

## DeadDrop Tutorial

`nightshift init --template tutorial-deaddrop` creates a small Flask snippet sharing utility with deterministic tests and incremental NightShift tasks. Its pipeline includes semantic context retrieval, telemetry, debugger support, fixed task-specific tests, and a single default `qwen3-coder:30b` model path.
