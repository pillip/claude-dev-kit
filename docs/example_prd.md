# PRD: Bookmark Management API

## Background

Our team frequently saves and shares useful links (articles, docs, tools) across Slack and email. Links get lost, duplicated, and lack context. We need a simple, self-hosted API to collect, organize, and retrieve bookmarks with tagging and full-text search.

## Goals

1. Provide a RESTful API to create, read, update, and delete bookmarks.
2. Support tagging and tag-based filtering.
3. Enable full-text search across bookmark titles, descriptions, and tags.
4. Allow bulk import/export via JSON.

## Target User

- **Primary**: Backend developers on the team who want to save/retrieve links programmatically or via CLI.
- **Secondary**: Any team member using a lightweight web UI (out of scope for v0, API only).

## User Stories

1. **As a developer**, I want to save a URL with a title, description, and tags so I can find it later.
2. **As a developer**, I want to list all my bookmarks filtered by tag so I can browse a topic.
3. **As a developer**, I want to search bookmarks by keyword so I can find a half-remembered link.
4. **As a developer**, I want to edit a bookmark's tags or description to keep it accurate.
5. **As a developer**, I want to delete bookmarks I no longer need.
6. **As a developer**, I want to export all bookmarks as JSON for backup.
7. **As a developer**, I want to import bookmarks from a JSON file to migrate data.

## Functional Requirements

### FR-1: Bookmark CRUD
- `POST /bookmarks` — Create a bookmark (url, title, description?, tags?[]).
- `GET /bookmarks` — List bookmarks with optional query params: `tag`, `q` (search), `page`, `per_page`.
- `GET /bookmarks/{id}` — Get a single bookmark.
- `PUT /bookmarks/{id}` — Update a bookmark.
- `DELETE /bookmarks/{id}` — Delete a bookmark.

### FR-2: Tagging
- Tags are lowercase, alphanumeric + hyphens, max 30 chars each.
- A bookmark can have 0–10 tags.
- `GET /tags` — List all tags with bookmark counts.

### FR-3: Search
- `GET /bookmarks?q=<keyword>` — Full-text search across title, description, tags.
- Results sorted by relevance, then by creation date descending.

### FR-4: Bulk Import/Export
- `POST /bookmarks/import` — Accept a JSON array of bookmark objects.
- `GET /bookmarks/export` — Return all bookmarks as a JSON array.

## Non-functional Requirements

- **NFR-1**: Response time < 200ms for list/search queries (up to 10k bookmarks).
- **NFR-2**: SQLite for storage (single-file, no external DB dependency).
- **NFR-3**: Input validation on all endpoints; return 422 with field-level errors.
- **NFR-4**: Pagination defaults: page=1, per_page=20, max per_page=100.
- **NFR-5**: API returns JSON with consistent envelope: `{"data": ..., "meta": {...}}`.

## Out of Scope (v0)

- Authentication / multi-user support.
- Web UI / frontend.
- Bookmark deduplication by URL.
- Link health checking (dead link detection).
- Browser extension.

## Success Metrics

- All CRUD endpoints pass integration tests.
- Search returns relevant results within 200ms for 1k+ bookmarks.
- Import/export round-trip preserves all data without loss.
- Zero critical/high severity bugs in first review cycle.

## Technical Notes

- Framework: Django or FastAPI (architect decides).
- Database: SQLite with FTS5 extension for full-text search.
- Deployment: Docker container, single `docker compose up`.
