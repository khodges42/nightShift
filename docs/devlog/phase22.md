# Phase 22 Devlog: Quickstart Test Project

## Implemented

- Added a guided Lisp interpreter quickstart project to `QUICKSTART.md`.
- Added concrete quickstart project files under `examples/quickstart-lisp/`.
- Included multi-task `tasks.md` with dependencies.
- Included a matching `nightshift.yaml`.
- Included planner, implementer, and reviewer prompt files.
- Included an initial passing unittest smoke test.

## Decisions Made

- Kept the Lisp interpreter as the recommended test project because it is compact, incremental, and testable.
- Fake agents are used in the example so users can validate NightShift before connecting a real local model or coding agent.

## Notes

- Users can copy `examples/quickstart-lisp/` to a scratch directory and run `nightshift validate`, `nightshift status`, and `nightshift run --all`.
