# Phase 4 Devlog: Task Parser

## Implemented

- Added `nightshift/tasks.py`.
- Implemented parsing for documented markdown checklist tasks.
- Extracted task id, title, completion state, description, acceptance criteria, dependency bullets, raw task markdown, and source line number.
- Added selection of the next incomplete task.
- Added selection of a specific task id.
- Added useful errors for malformed task headers, duplicate ids, missing acceptance criteria, missing files, traversal attempts, and unknown task ids.
- Added parser and selection tests.

## Decisions Made

- The parser intentionally supports the documented v1 format rather than broad Markdown. This keeps failure behavior explicit and testable.
- Acceptance criteria are required for each task because downstream pipeline stages need concrete review targets.
- Dependencies are parsed as simple bullets under a `Dependencies:` section, but no dependency solver is implemented in this phase.
- Completed tasks use `[x]` or `[X]`; incomplete tasks use `[ ]`.

## Notes

- Task mutation, completion updates, and dependency enforcement are deferred until later pipeline phases.
