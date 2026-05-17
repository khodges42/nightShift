# Phase 5 Devlog: Artifact Store

## Implemented

- Added `nightshift/artifacts.py`.
- Created `.nightshift/`, per-run directories, and per-task directories.
- Created `project-context.md` and `run-summary.md` placeholders when a run is initialized.
- Added config snapshot copying to `config.snapshot.yaml`.
- Added task snapshot writing to `task.md`.
- Added generic stage output writing.
- Added command output writing.
- Added final task notes writing.
- Added tests for artifact tree creation, snapshot writing, and task-directory escape rejection.

## Decisions Made

- `ArtifactStore` accepts an optional `run_id` so tests and future pipeline code can produce deterministic artifact paths.
- Default run ids use UTC timestamps in `YYYYMMDDTHHMMSSZ` format.
- Stage output filenames are relative to the task artifact directory and may include subdirectories, but they cannot escape that task directory.
- Project context and run summary files are initialized with simple markdown headers. Later phases can append richer content.

## Notes

- The artifact store is intentionally independent from pipeline execution so command, agent, context, and report phases can reuse it.
