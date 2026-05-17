# Phase 21 Devlog: Read-Only Web Dashboard

## Implemented

- Added `nightshift/web.py`.
- Added `nightshift web` CLI command.
- Implemented read-only artifact dashboard rendering.
- Listed runs from `.nightshift/runs/`.
- Rendered run summaries with simple auto-refresh.
- Added safe artifact reading that rejects path traversal.
- Added tests for missing runs, run listing, and artifact path handling.

## Decisions Made

- Flask is an optional dependency. The CLI gives a clear error if Flask is missing.
- The dashboard is artifact-driven and does not control pipeline execution.
- No websockets, authentication, mutation, or live process control were added.

## Notes

- This is intentionally a monitoring entry point, not an operations console.
