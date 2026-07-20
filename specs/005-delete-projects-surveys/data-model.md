# Data Model: Delete Projects and Surveys

**Date**: 2026-07-20 | **Plan**: [plan.md](./plan.md) | Extends [001](../001-survey-ingest/data-model.md)/[002](../002-project-authorization/data-model.md) models

## Database changes

### Project *(modified, `apps/projects`)*

| Field | Change | Notes |
|---|---|---|
| `deleted_at` | NEW `DateTimeField(null=True, blank=True)` | `NULL` = active (the overwhelming majority of rows); set = soft-deleted (R1) |
| `deleted_by` | NEW `ForeignKey(User, null=True, blank=True, on_delete=SET_NULL, related_name="+")` | Who deleted it (FR-008); `SET_NULL` so a removed user account never blocks anything (R1) |

No new constraints. `ProjectMembership` rows are untouched by deletion — a
soft-deleted project keeps its memberships, so `access.is_owner` keeps
working for the restore/recently-deleted flows.

### Survey *(modified, `apps/surveys`)*

| Field | Change | Notes |
|---|---|---|
| `deleted_at` | NEW `DateTimeField(null=True, blank=True)` | Same semantics as `Project.deleted_at` |
| `deleted_by` | NEW `ForeignKey(User, null=True, blank=True, on_delete=SET_NULL, related_name="+")` | Who deleted it — the acting user for an independent survey delete, or the project's deleter for a cascade (FR-008) |
| `deleted_via_project_cascade` | NEW `BooleanField(default=False)` | `True` only while cascade-deleted alongside its project (R2); always `False` for an independent survey deletion |

No changes to `ProcessingRun`, `RunOption`, `DerivedArtifact`, or
`UploadSession` — they are removed by the existing `on_delete=CASCADE` chain
when the `Survey`/`Project` row is physically purged (R5); they are simply
unreachable (via the normal, deleted-excluding lookups) while their parent is
soft-deleted.

## Settings

| Setting | Default | Notes |
|---|---|---|
| `DELETE_RECOVERY_DAYS` | `7` | Shared recovery window for both projects and surveys (Assumptions); mirrors the existing `UPLOAD_EXPIRY_DAYS=7` convention |

## State model

```text
Project/Survey lifecycle (deletion overlay, orthogonal to existing status):
  active (deleted_at IS NULL)
    --delete (owner, not blocked by FR-003)--> deleted (deleted_at=now, deleted_by=user)
  deleted, within recovery window
    --restore (owner)--> active (deleted_at=NULL, deleted_by=NULL)
    --recovery window elapses--> purge job deletes storage prefix, then the row
                                   (DB CASCADE removes every dependent row)
```

For `Survey` specifically, `deleted_via_project_cascade` governs whether a
project-level delete/restore touches it (R2):

```text
Survey.deleted_via_project_cascade lifecycle:
  independent delete   -> deleted_via_project_cascade=False (untouched by project ops)
  project cascade delete -> deleted_via_project_cascade=True (restored/purged with the project)
  restore (either path)  -> deleted_via_project_cascade reset to False
```

## Validation & access rules

- **Listing/detail scoping**: every existing read path that resolves a
  `Project` or `Survey` for a normal user (`access.projects_for`,
  `access.get_project_or_404`, `access.get_survey_or_404`, and the survey
  list under a project) MUST additionally filter `deleted_at__isnull=True`
  (and, for surveys, `project__deleted_at__isnull=True`) — FR-005.
- **Delete authorization**: both delete and restore actions call
  `access.is_owner(request.user, project)` (002, unchanged) — FR-007.
- **Delete blocking**: a delete request MUST be rejected (`not_deletable`,
  409) if the target survey has `status` in `{queued, processing}`, or — for
  a project — if any of its surveys does, or if any of its `UploadSession`s
  has `state=active` (R4/FR-003).
- **Cascade on project delete**: every survey with `deleted_at IS NULL`
  under the project gets `deleted_at`/`deleted_by` set and
  `deleted_via_project_cascade=True` in the same transaction as the
  project's own soft delete (R2/FR-002/FR-011).
- **Cascade on project restore**: every survey with
  `deleted_via_project_cascade=True` under the project gets `deleted_at`/
  `deleted_by` cleared and the flag reset to `False`, in the same
  transaction as the project's own restore (R2/FR-011).
- **Restore authorization & window**: restoring requires the same
  owner check, plus `deleted_at` must be set and not older than
  `DELETE_RECOVERY_DAYS`; any other case (never deleted, already restored,
  past the window, never existed, not yours) responds identically with
  `not_restorable` (404) — no case is distinguishable from another (R7).
- **Purge job scope**: `purge_expired_deletions` selects `Project`s with
  `deleted_at <= now() - DELETE_RECOVERY_DAYS` and independently-deleted
  (`deleted_via_project_cascade=False`) `Survey`s with the same age
  threshold whose project is still active (`project__deleted_at__isnull=True`)
  — a cascade-deleted survey's storage/DB cleanup is already subsumed by its
  project's own purge pass (R5).
