# Troubleshooting

## `command is not allowlisted`

Add the exact command to `safety.allowed_commands`. NightShift normalizes whitespace but otherwise expects exact matches.

## Command works in PowerShell but fails in NightShift

Command stages use Python subprocess execution. By default `shell: true` uses the platform shell, which is usually `cmd.exe` on Windows. Prefer Python module commands or set explicit shell commands.

## No runnable tasks

Check `nightshift status`. A task may be blocked by dependencies listed under `Dependencies:`.

## Git clean worktree failure

If `require_clean_worktree: true`, NightShift blocks dirty repositories before creating artifacts. Commit/stash changes or set it to false.

## Ollama backend fails

The `ollama` backend uses Ollama's local HTTP API, normally at `http://localhost:11434/api/generate`. Confirm Ollama is running and the configured model is available with `ollama list` or `ollama pull <model>`. Tests do not require Ollama.

## Flask dashboard fails

Install Flask:

```bash
pip install flask
```
