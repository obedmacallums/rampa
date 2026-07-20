# Research: Delete Projects and Surveys

**Date**: 2026-07-20 | **Plan**: [plan.md](./plan.md)

No `[NEEDS CLARIFICATION]` markers remained after `/speckit-clarify` (5
questions resolved across the specify + clarify sessions). Research below
settles implementation-level unknowns the spec deliberately left open.

## R1 — Soft-delete field shape

**Decision**: Add `deleted_at: DateTimeField(null=True, blank=True)` and
`deleted_by: ForeignKey(User, null=True, blank=True, on_delete=SET_NULL,
related_name="+")` directly on `Project` and `Survey`. `Survey` additionally
gets `deleted_via_project_cascade: BooleanField(default=False)`.

**Rationale**: `deleted_at IS NULL` is the existing row's normal state — a
single nullable timestamp is the simplest possible "is this deleted, and
since when" signal, directly answers FR-006/FR-008 (recoverable + traceable),
and needs no new table. `deleted_by` uses `SET_NULL` (not `PROTECT`) so a
deleted user account never blocks anything — audit value degrades to "deleted
by a since-removed account" rather than blocking, consistent with how
`ProjectMembership.granted_by` already handles the same situation (002). The
cascade flag is the only way to implement FR-011's "only surveys that were
still active at the moment the project was deleted are cascade-restored with
it" (an independently-deleted survey must never be touched by a later
project-level delete/restore).

**Alternatives considered**: A separate `Deletion` audit table (one row per
deletion event) — rejected: FR-008's traceability need is fully satisfied by
two columns on the row itself, and a separate table would need to survive
independently of the row's own lifecycle for no clarified requirement (the
spec's Assumptions explicitly scope the audit trail to "while the row is
still soft-deleted," not permanent history past physical purge, R6).

## R2 — Cascade + independent-restore semantics

**Decision**: Deleting a project sets `deleted_at`/`deleted_by` on the
project itself, then sets the same on every currently-active
(`deleted_at IS NULL`) survey inside it, marking each
`deleted_via_project_cascade=True`. Restoring a project clears its own
`deleted_at`/`deleted_by`, then does the same for every survey where
`deleted_via_project_cascade=True`, resetting the flag to `False`. A survey
deleted on its own (`deleted_via_project_cascade=False`) is never touched by
a project-level delete or restore.

**Rationale**: Directly implements FR-011 and its edge case. Using a boolean
flag (rather than, say, comparing timestamps) is unambiguous even if a
project delete and an independent survey delete happen to land in the same
second.

**Alternatives considered**: Deriving "was this survey cascade-deleted" from
"does `survey.deleted_at == project.deleted_at`" — rejected: fragile
(timestamp equality across two separate writes), and breaks the moment a
project is deleted, restored, and deleted again with a different set of
active surveys.

## R3 — Where the "Recently Deleted" view lives

**Decision**: One global page (`GET /deleted`, `frontend` route `/deleted`)
listing every deleted project and every *independently* deleted survey (i.e.
`deleted_via_project_cascade=False`) the requesting user owns — not a
per-project sub-view.

**Rationale**: A deleted project has no live detail page to nest a view
inside (`ProjectDetailPage` needs a non-deleted project to render its survey
list, members, etc.), so a project-scoped "Recently Deleted" tab cannot host
the project's own deletion entry. A single global page is simpler, matches
FR-010's literal requirement ("browse... every project or survey they
deleted"), and needs no new per-project routing. Cascade-deleted surveys are
intentionally omitted from this listing (R2/FR-011: they come back as part of
restoring their project, not as separate rows) to avoid a project deletion
cluttering the view with dozens of survey rows.

**Alternatives considered**: A tab inside `ProjectDetailPage` — rejected for
the reason above; would also need a second, different UI for restoring a
whole deleted project.

## R4 — Blocking deletion on in-flight work (FR-003)

**Decision**: Survey deletion is rejected (`409 not_deletable`) while
`survey.status` is `queued` or `processing` (reusing the exact same states
`SurveyProcessView` already gates on, 004). Project deletion is rejected the
same way if **any** of its surveys is in that state, **or** if the project
has any `UploadSession` with `state=active`.

**Rationale**: Mirrors the existing `not_processable` 409 pattern (004)
instead of inventing a new state machine. Blocking project deletion on an
in-flight upload prevents the tusd `post-finish` hook from ever trying to
create a survey under an already-deleted project — the alternative (letting
it happen and handling the orphaned-survey case) was explicitly rejected in
clarification.

**Alternatives considered**: Also blocking on a survey's own `UploadSession`
— unnecessary: by the time a survey row exists, its upload session is already
`completed` (the tusd hook creates the survey exactly at that transition);
there is no state where an existing survey still has an `active` upload
session of its own.

## R5 — Storage cleanup: synchronous vs. deferred, and prefix delete

**Decision**: Deletion/restore endpoints never touch object storage — they
only flip DB columns, keeping the request path fast (Technical Context). A
new Celery beat task, `purge_expired_deletions` (alongside the existing
`purge_expired_upload_sessions` in `apps/surveys/tasks_maintenance.py`), runs
hourly and, for every `Project`/independently-deleted `Survey` past
`settings.DELETE_RECOVERY_DAYS`: recursively deletes every object under its
storage prefix via a new `pipeline.storage.delete_prefix(prefix)` helper
(paginated `list_objects_v2` + batched `delete_objects`, mirroring how
`storage.run_key`/`storage.source_key` already define the prefix layout),
then deletes the Django row (whose `on_delete=CASCADE` chain already removes
every `ProcessingRun`/`RunOption`/`DerivedArtifact`/`UploadSession` under it).
Purging a project this way already removes every one of its surveys' files
too (same S3 prefix, same DB cascade) — no separate per-survey purge pass is
needed for cascade-deleted surveys.

**Rationale**: Keeps the user-facing operation instant (SC-001) and matches
the existing expired-upload purge job exactly in shape and schedule.
`delete_prefix` is a genuinely new capability (today's `storage.py` only
deletes one object at a time) but is a small, self-contained addition.

**Alternatives considered**: Deleting files synchronously inside the DELETE
request — rejected: makes a "click delete" request as slow as however long
S3 takes to remove potentially tens of GB across many objects, and provides
no benefit since the recovery window already defers the point of no return.

## R6 — Audit trail lifetime

**Decision**: `deleted_by`/`deleted_at` (R1) live only as long as the row
does. Once the purge job deletes the row, the "who/when" is gone with it —
there is no separate, permanently-retained deletion log.

**Rationale**: FR-008 only requires traceability "after the fact" while the
action is still relevant/actionable (visible in "Recently Deleted", still
restorable) — not indefinite audit retention, which the spec's Assumptions
never asked for and would need its own table/retention policy to build
responsibly. Revisit if a future feature needs a durable audit log across
the whole platform (a cross-cutting concern, not specific to deletion).

**Alternatives considered**: A permanent audit log table — rejected as
scope creep beyond what FR-008 and the clarified assumptions require.

## R7 — Reusing vs. introducing error codes

**Decision**: Reuse the existing `not_owner` (403) code for both project- and
survey-level deletion/restore permission checks (`access.is_owner`, already
used by `_require_owner` in 002); broaden its Spanish/English message text
from "administrar los miembros del proyecto" to something action-neutral
("realizar esta acción sobre el proyecto"), since it now guards more than
membership management. Introduce two new codes: `not_deletable` (409, R4) and
`not_restorable` (404 — covers "never existed," "not yours," "not deleted,"
and "past the recovery window" uniformly, so the response never leaks which
case applies, consistent with how `get_project_or_404`/`get_survey_or_404`
already collapse "doesn't exist" and "not a member" into one 404).

**Rationale**: Minimizes new surface area; the `not_owner` wording tweak is
backward compatible (same code, same 403, just clearer prose) and the two new
codes follow the exact `snake_case` gerund-negative style already established
(`not_retriable`, `not_processable`).

**Alternatives considered**: A distinct `not_owner_delete` code — rejected:
the existing code already means exactly "you are not an owner of this
project," no new semantic is needed.
