# Phase 19 Devlog: Stronger Command Execution

## Implemented

- Added command stage `shell` option, defaulting to true for backward compatibility.
- Added command stage `timeout_seconds` override.
- Added command stage `working_dir` restricted to the project root.
- Added `safety.allowed_env` for optional environment variable pass-through.
- Added argv-style execution path when `shell: false`.
- Added tests for shell-free execution and working-directory restrictions.

## Decisions Made

- Existing string command config remains valid.
- `shell: false` still uses the same exact allowlist check before splitting into argv.
- `PATH` is preserved when an environment allowlist is configured so common executables remain discoverable.

## Notes

- Future hardening can move toward structured command definitions, but this phase avoids breaking current configs.
