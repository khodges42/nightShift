# Pastebin Tutorial Tasks

- [ ] TASK-001: Snippet creation and viewing

Description:
Complete the pastebin service foundation. Support creating snippets with title and body. Support viewing a single snippet by id.

Acceptance Criteria:
- POST `/snippets` creates a snippet with title and body
- GET `/snippets/<id>` returns the snippet
- Tests cover creation and viewing

- [ ] TASK-002: Snippet metadata fields

Dependencies:
- TASK-001

Description:
Persist optional language, tags, and expiration fields on snippets.

Acceptance Criteria:
- POST `/snippets` accepts optional language, tags, and expires_at fields
- GET `/snippets/<id>` returns persisted metadata fields
- Tags are serialized deterministically
- Tests cover metadata persistence

- [ ] TASK-003: Snippet listing and filtering

Dependencies:
- TASK-002

Description:
Add snippet listing with newest-first ordering and deterministic search/filter behavior.

Acceptance Criteria:
- GET `/snippets` lists snippets newest first
- `q` filters by title or body text
- `language` filters by language
- `tag` filters by tag
- Tests cover listing, search, and filters

- [ ] TASK-004: Expiration handling

Dependencies:
- TASK-003

Description:
Hide expired snippets from list/search results while keeping direct lookup behavior explicit.

Acceptance Criteria:
- Expired snippets are excluded from GET `/snippets`
- Direct lookup of an expired snippet returns 410
- Non-expiring snippets remain visible
- Tests cover expired and active snippets

- [ ] TASK-005: HTML forms and templates

Dependencies:
- TASK-004

Description:
Add simple HTML pages for creating, listing, filtering, and viewing snippets.

Acceptance Criteria:
- GET `/` shows the snippet list
- GET `/new` shows a creation form
- Creating a snippet redirects to the snippet view
- Templates expose language, tags, and expiration fields
- Tests cover HTML response status and redirects
