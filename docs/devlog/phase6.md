# Phase 6 Devlog: Command Executor

## Implemented

- Added `nightshift/commands.py`.
- Added command-stage execution for configured `command` stages.
- Captured stdout, stderr, exit code, duration, and timeout state.
- Persisted command transcripts through the artifact store.
- Returned structured `StageResult` objects.
- Added tests for passing commands, failing commands, output persistence, and allowlist rejection.

## Decisions Made

- Commands are validated through the Phase 3 safety layer immediately before execution, even though config validation also checks them. This keeps command execution safe if called directly in later code.
- Command stages stop at the first failing or timed-out command and persist the commands that ran.
- Commands run with `shell=True` because v1 config stores commands as shell-style strings. This is constrained by exact allowlist matching and forbidden fragment checks.
- The default timeout is 300 seconds. Tests can override it later if timeout-specific behavior needs coverage.

## Notes

- This phase does not wire command execution into a full pipeline runner. That belongs to Phase 8.
