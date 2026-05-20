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
  model: qwen2.5-coder:14b
  base_url: http://localhost:11434
  system_prompt: agents/planner.md
```

## `pipeline`

- `max_task_retries`: task retry limit.
- `continue_on_task_failure`: for `run --all`, continue after failed/blocked tasks.
- `stages`: ordered state-machine stages.

Command stage options:

- `commands`: command strings.
- `shell`: defaults to true. Set false for argv-style execution.
- `timeout_seconds`: per-stage timeout override.
- `working_dir`: command working directory inside project root.

Patch validator stage options:

- `max_files`: max files changed.
- `max_lines`: max changed lines.
- `max_delete_ratio`: reject deletion-heavy patches above this deleted-line share, from `0.0` to `1.0`.
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
python -m nightshift.cli integ-run --template tutorial-pastebin
```

Then enter the generated project:

```bash
cd integ_runs/<timestamp>/project
```

Activate the sandbox virtual environment and install target dependencies.

PowerShell:

```powershell
..\.venv\Scripts\Activate.ps1
python -m pip install -e ..\..\..
python -m pip install -e . pytest flask
```

Bash:

```bash
source ../.venv/bin/activate
python -m pip install -e ../../..
python -m pip install -e . pytest flask
```

Run NightShift inside the generated `project/` directory:

```bash
python -m nightshift.cli validate
python -m nightshift.cli run --task TASK-001
```

To clean up old sandboxes before creating a new one, keep only the newest three existing runs:

```bash
python -m nightshift.cli integ-run --template tutorial-pastebin --keep 3
```

## Pastebin Tutorial

`nightshift init --template tutorial-pastebin` creates a small Flask snippet-hosting target with deterministic tests and incremental NightShift tasks. Its pipeline includes semantic context retrieval, telemetry, debugger support, and implementation fallback order:

- `qwen2.5-coder:14b`
- `carstenuhlig/omnicoder-9b`
- `deepseek-coder-v2:16b`
