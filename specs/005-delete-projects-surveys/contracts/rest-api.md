# REST API Contract — Delete Projects and Surveys (delta over 001/002/004 contracts)

**Base**: `/api/v1` — session auth, JSON, error shape `{"error": {"code", "message_key", "detail"}}` as in 001.

## DELETE /projects/{projectId} *(new)*

Owner-only. Soft-deletes the project and cascades to every survey still
active at that moment (FR-002/FR-011).

- `204` — deleted. No body.
- `403` `not_owner` — requester is a member but not an owner.
- `404` `not_found` — not a member, already deleted, or doesn't exist (same
  collapsed 404 as every other project lookup, 002).
- `409` `not_deletable` — the project (or one of its surveys) has processing
  queued/running, or the project has an upload actively in progress (R4).

## POST /projects/{projectId}/restore *(new)*

Owner-only. Restores a soft-deleted project within its recovery window,
cascade-restoring every survey that was cascade-deleted with it (FR-010/FR-011).

```json
// 200 — ProjectSummarySerializer shape (unchanged from 001/002), now visible again
{ "id": "…", "name": "…", "crs": { "...": "..." }, "survey_count": 3, "created_at": "…", "is_owner": true }
```

- `403` `not_owner`.
- `404` `not_restorable` — never deleted, already restored, past the
  recovery window, not yours, or never existed (all collapsed into one
  response, R7).

## DELETE /surveys/{surveyId} *(new)*

Owner-only. Soft-deletes the survey; unaffected by anything else in the
project (FR-001).

- `204` — deleted. No body.
- `403` `not_owner`.
- `404` `not_found`.
- `409` `not_deletable` — the survey has processing queued/running (R4).

## POST /surveys/{surveyId}/restore *(new)*

Owner-only. Restores an independently-deleted survey within its recovery
window. Has no effect on (and cannot be used for) a survey currently
cascade-deleted with its still-deleted project — restore the project
instead (FR-011).

```json
// 200 — SurveySummarySerializer shape (004), now visible again
{ "id": "…", "name": "…", "capture_date": "…", "status": "completed", "...": "..." }
```

- `403` `not_owner`.
- `404` `not_restorable`.

## GET /deleted *(new)*

Global listing (not project-scoped) of everything the requesting user can
still restore: projects they own that are soft-deleted, and surveys they
independently deleted (cascade-deleted surveys are omitted — they come back
as part of restoring their project, R3).

```json
{
  "projects": [
    {
      "id": "…", "name": "…",
      "crs": { "code": "…", "label_key": "…" },
      "survey_count": 3,
      "deleted_at": "2026-07-20T10:00:00Z",
      "purge_at": "2026-07-27T10:00:00Z"
    }
  ],
  "surveys": [
    {
      "id": "…", "name": "…", "capture_date": "…",
      "project": { "id": "…", "name": "…" },
      "deleted_at": "2026-07-19T08:30:00Z",
      "purge_at": "2026-07-26T08:30:00Z"
    }
  ]
}
```

`purge_at` is `deleted_at + DELETE_RECOVERY_DAYS`, provided so the UI can show
a countdown without hardcoding the recovery window.

## GET /projects *(modified)*

Excludes soft-deleted projects (FR-005). Each entry gains `is_owner`, needed
by the frontend to show delete actions only where authorized:

```json
// 200 — unchanged fields plus:
{ "...": "...", "is_owner": true }
```

## GET /projects/{projectId}/surveys *(modified)*

Excludes soft-deleted surveys (FR-005). No shape change otherwise.

## GET /surveys/{surveyId}, /retry, /process, /artifacts *(unchanged contract)*

Resolution now additionally excludes soft-deleted surveys and surveys whose
project is soft-deleted (via the shared `access.get_survey_or_404` scoping) —
same 404 as any other non-member/nonexistent case, no new error code.

## Compatibility notes

- All new/changed responses expose i18n **keys** only (Principle IX).
- `not_owner` (403, existing since 002) is now also raised by the four new
  delete/restore endpoints; its message text is broadened from
  membership-specific wording to a generic "you must be an owner" phrasing
  (R7) — same code, same status, no contract break.
- No endpoint returns a permanently-purged project/survey's data; once the
  background purge job removes a row, it behaves exactly like it never
  existed (plain 404, not `not_restorable` — that code is reserved for rows
  still present in the database but outside an owner's restore rights or
  window).
