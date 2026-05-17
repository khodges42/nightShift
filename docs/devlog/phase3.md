# Phase 3 Devlog: Safety Layer

## Implemented

- Added `nightshift/safety.py`.
- Implemented project root resolution.
- Implemented path resolution that rejects traversal outside the configured project root.
- Implemented scoped path validation.
- Implemented safe artifact path construction that rejects escapes from the artifact directory.
- Implemented command allowlist checks.
- Implemented forbidden command fragment checks.
- Wired command and path safety checks into `validate_config()`.
- Added tests for path traversal, artifact escapes, allowlist behavior, and forbidden command fragments.

## Decisions Made

- Command matching uses normalized whitespace and exact allowlist entries. This keeps v1 predictable while still handling harmless spacing differences.
- Forbidden fragments are checked before allowlist acceptance, so a dangerous command cannot be made valid by adding it to `allowed_commands`.
- Scoped paths are validated for containment inside the project root, but they are not required to exist yet. This preserves the Phase 2 decision that configs can be scaffolded before all source directories exist.
- The safety layer raises `SafetyError`; config validation wraps those failures as config errors when they come from `nightshift validate`.

## Notes

- This phase does not execute commands. It only validates whether a command would be permitted. Process execution belongs to Phase 6.
