# Tasks

- [ ] TASK-001: Board and thread foundation

Description:
Create the initial Flask imageboard application. Implement the board and thread data model, SQLite schema, model helpers, `/board/<name>` and `/thread/<id>` routes, and tests. Keep source code under `src/`, tests under `tests/`, HTML templates under `templates/`, and static files under `static/`.

Acceptance Criteria:
- Defines SQLite tables for boards, threads, and replies
- Provides database initialization and model helper functions
- Implements `/board/<name>` route showing threads for that board
- Implements `/thread/<id>` route showing the thread and replies
- Includes route and model tests using a temporary database

- [ ] TASK-002: Image upload and thumbnails

Dependencies:
- TASK-001

Description:
Add image attachment support for new threads and replies. Store uploaded image metadata in SQLite, save uploaded files under `static/uploads`, and generate thumbnails under `static/thumbs`.

Acceptance Criteria:
- Accepts image uploads for threads and replies
- Stores image filename, thumbnail filename, MIME type, and size
- Generates thumbnails with Pillow
- Rejects unsupported or oversized files
- Includes upload and thumbnail tests

- [ ] TASK-003: Bump ordering and reply counts

Dependencies:
- TASK-002

Description:
Sort board threads by most recent bump. Creating a reply updates the thread bump timestamp and increments reply counters.

Acceptance Criteria:
- Board pages sort threads by latest bump time
- Replies increment thread reply count
- Reply creation updates bump timestamp
- Tests cover ordering and counters

- [ ] TASK-004: Tripcodes and session cookies

Dependencies:
- TASK-003

Description:
Add anonymous names, optional tripcodes, and a session cookie for lightweight poster identity.

Acceptance Criteria:
- Supports optional name and tripcode input
- Stores tripcode hashes without storing raw tripcode secrets
- Sets and reuses a poster session cookie
- Displays stable poster identity on posts
- Includes tripcode and session tests

- [ ] TASK-005: Moderation and report queue

Dependencies:
- TASK-004

Description:
Add post reporting and a simple moderation queue. Moderators can view reports, dismiss reports, and hide reported posts.

Acceptance Criteria:
- Users can report threads and replies
- Reports are stored with reason and timestamp
- Moderation queue lists open reports
- Moderation actions can dismiss reports or hide posts
- Includes moderation and report queue tests
