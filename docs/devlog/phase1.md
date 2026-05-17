# Phase 1 Devlog: Skeleton

## Implemented

- Created the `nightshift` Python package.
- Added a CLI module with `nightshift init`, `nightshift validate`, and placeholder `run` / `status` commands.
- Added `pyproject.toml` with a console entry point.
- Added starter file generation for:
  - `nightshift.yaml`
  - `tasks.md`
  - `agents/planner.md`
  - `agents/implementer.md`
  - `agents/reviewer.md`
- Added unit tests for initialization behavior.

## Decisions Made

- Used `argparse` instead of a CLI dependency so the MVP works from a clean Python checkout.
- Implemented overwrite protection with a `--force` flag. Interactive confirmation was deferred to keep the command deterministic and scriptable.
- Added `run` and `status` as CLI placeholders only. The phase required an entry point, but actual execution belongs to later phases.
- Kept starter prompts short and human-readable so they can be revised easily as agent execution is implemented.

## Notes

- Phase 1 establishes the file layout expected by later phases without introducing model or pipeline execution behavior early.
