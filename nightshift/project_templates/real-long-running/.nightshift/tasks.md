# Tasks

- [ ] TASK-001: Incident intake service foundation

Description:
Create a Flask service for incident intake and triage. Implement SQLite schema, app factory, incident model helpers, routes for creating/listing/detailing incidents, and tests. This is intentionally larger than the simple template and should exercise planning, architecture notes, implementation, tests, and review.

Acceptance Criteria:
- Provides app factory and package layout under `src/`
- Defines SQLite schema for incidents, status, severity, and audit events
- Implements create, list, and detail routes
- Records audit events when incidents are created or status changes
- Includes pytest tests with temporary database setup

- [ ] TASK-002: Assignment and status workflow

Dependencies:
- TASK-001

Description:
Add assignee tracking, status transitions, validation rules, and audit history views.

Acceptance Criteria:
- Supports assigning incidents to owners
- Validates allowed status transitions
- Stores audit events for assignment and status changes
- Includes route and model tests

- [ ] TASK-003: Search and reporting

Dependencies:
- TASK-002

Description:
Add filtering by severity/status/assignee and a lightweight CSV export for open incidents.

Acceptance Criteria:
- Supports filtered incident list queries
- Exports open incidents as CSV
- Includes tests for filter combinations and export content
