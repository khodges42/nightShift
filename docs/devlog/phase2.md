# Phase 2 Devlog: Config Loading

## Implemented

- Added typed configuration objects for project, safety, agents, pipeline, and stages.
- Added `load_config()` for parsing `nightshift.yaml`.
- Added `validate_config()` for checking referenced task and prompt files.
- Added validation for:
  - required top-level sections
  - required project fields
  - non-empty agents
  - supported stage types
  - agent stage references
  - command stage command lists
  - duplicate stage IDs
  - `on_fail` references
- Added unit tests for valid config loading and key invalid config cases.

## Decisions Made

- Used PyYAML automatically when available, but added a small standard-library fallback parser for the YAML subset emitted by `nightshift init`.
- Deferred full YAML edge-case support to a future dependency/install pass. The fallback is intentionally documented as a starter-config parser, not a general YAML implementation.
- Validation currently confirms that scoped paths resolve inside the project root, but it does not require every scoped path to already exist. That allows users to scaffold configs before creating all source/test directories.
- Kept config validation focused on structural correctness and references. Command safety enforcement is left for Phase 3.

## Notes

- The config layer now catches missing agent references with explicit messages such as `pipeline stage 'plan' references unknown agent 'critic'`.
- Tests use `unittest` from the standard library so they can run before development dependencies are introduced.
