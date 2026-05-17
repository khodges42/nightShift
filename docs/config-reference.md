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
- `forbidden_paths`: paths the patch must not touch.
- Unified diff hunk line prefixes and hunk line counts are validated before patch apply.

Writer stages:

- `code_writer`: agent returns a unified diff directly.
- `file_writer`: agent returns complete file content blocks; NightShift generates the unified diff deterministically.

`file_writer` blocks use this form:

````markdown
```file:relative/path.py
<complete file content>
```
````
