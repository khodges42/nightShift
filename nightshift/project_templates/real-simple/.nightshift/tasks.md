# Tasks

- [ ] TASK-001: Bookmark API foundation

Description:
Create a small Flask bookmark API with SQLite persistence. Implement app factory, schema initialization, bookmark model helpers, and routes to create, list, update, and delete bookmarks. Keep code under `src/` and tests under `tests/`.

Acceptance Criteria:
- Provides an app factory under `src/`
- Initializes a SQLite schema for bookmarks
- Supports create, list, update, and delete routes
- Validates required URL/title fields
- Includes pytest tests using a temporary database

- [ ] TASK-002: Tags and filtering

Dependencies:
- TASK-001

Description:
Add tags to bookmarks and support filtering bookmarks by tag.

Acceptance Criteria:
- Stores tags in SQLite
- Supports assigning multiple tags to a bookmark
- Supports filtering list output by tag
- Includes model and route tests

- [ ] TASK-003: Import/export

Dependencies:
- TASK-002

Description:
Add JSON import and export endpoints for bookmark backups.

Acceptance Criteria:
- Exports all bookmarks and tags as JSON
- Imports valid JSON backup payloads
- Rejects malformed imports without corrupting existing data
- Includes tests for export and import behavior
