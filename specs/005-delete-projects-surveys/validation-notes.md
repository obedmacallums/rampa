# Quickstart Validation Notes (T036)

**Date**: 2026-07-20 | **Stack**: `docker compose` (`db`, `redis`, `minio`, `tusd`,
`titiler`, `backend`, `worker`, `frontend`), rebuilt from this feature's code
(`docker compose up -d --build`).

All 7 scenarios from [`quickstart.md`](quickstart.md) were run as genuine
`curl` requests (with real session cookies + CSRF tokens) against the live
stack, backed by real Postgres/PostGIS and MinIO — not simulated. Setup data
(users, projects, surveys, backdated deletions) was seeded via
`manage.py shell` so each scenario exercises the real view/serializer/access
code paths end to end. The full automated suite (below) additionally covers
every branch (permissions, edge cases, purge) that a manual pass can't
exhaustively re-run.

## Scenario 1 — Delete a survey independently (US1)

**Status**: PASS

`DELETE /surveys/{id}` on `survey-a.laz` → `204`; `GET
/projects/{id}/surveys` afterward lists only `survey-b.laz` and
`survey-processing.laz` — the deleted survey is gone, the rest of the
project untouched.

## Scenario 2 — Blocked while processing, blocked for non-owners (US1)

**Status**: PASS

- Member (non-owner) `DELETE /surveys/{id}` on `survey-b.laz` → `403
  not_owner`.
- Owner `DELETE /surveys/{id}` on a survey with `status=processing` → `409
  not_deletable`.

## Scenario 3 — Delete an entire project cascades (US2)

**Status**: PASS

`DELETE /projects/{id}` on "QS005 Project B" (2 surveys, one `completed` one
`failed`) → `204`. `GET /projects` afterward excludes it; `GET
/projects/{id}/surveys` on the deleted project → `404` (no longer
resolvable, same collapsed 404 as any other non-member/nonexistent
project).

## Scenario 4 — Recently Deleted listing + restore a survey (US3)

**Status**: PASS

`GET /deleted` returned "QS005 Project B" (with `purge_at` ~7 days out) and
the independently-deleted `survey-a.laz` (cascade-deleted surveys from
Project B were correctly *not* listed under `surveys`). `POST
/surveys/{id}/restore` on `survey-a.laz` → `200`; it reappeared in `GET
/projects/{id}/surveys` immediately after.

## Scenario 5 — Restore a whole project cascade-restores its surveys (US2/US3)

**Status**: PASS

`POST /projects/{id}/restore` on "QS005 Project B" → `200` with
`survey_count: 2`; `GET /projects/{id}/surveys` afterward listed both
`b-survey-1.laz` and `b-survey-2.laz` — the cascade-restore brought both
surveys back as a unit.

## Scenario 6 — Past the recovery window: not_restorable

**Status**: PASS

A survey with `deleted_at` backdated 8 days (past `DELETE_RECOVERY_DAYS=7`)
→ `POST /surveys/{id}/restore` returned `404 not_restorable`.

## Scenario 7 — Purge job physically removes expired deletions

**Status**: PASS

Ran `purge_expired_deletions()` directly against the live stack: the
backdated survey from Scenario 6 was physically deleted from the database
(`Survey.objects.filter(id=...).exists() == False`) — confirmed separately
by the automated `test_purge_expired_deletions.py`, which also asserts the
object-storage prefix is emptied via a real MinIO client.

## Full suites (run inside the container against real Postgres/MinIO)

```
$ docker compose exec backend pytest -q
126 passed, 1 skipped in ~31s   (the 1 skip is test_real_laz_full_pipeline,
                                  which needs --laz-sample)

$ docker compose exec backend pytest tests/integration/test_real_laz_ingest.py \
    -m real_laz --laz-sample /tmp/fixture/ramp.laz -v
1 passed   (real PDAL/untwine/gdal binaries, not the local-dev fallback path)
```

Frontend (local, not containerized — no frontend test runner in the image):
```
$ npx vitest run
40 passed (7 files)
```

## Success criteria (SC-001…SC-007)

- **SC-001** (delete a survey in <30s, no one else involved): PASS — a
  single synchronous `DELETE` call (metadata-only, no file I/O on the
  request path) plus one confirm click in the UI.
- **SC-002** (100% of a deleted project's surveys/uploads/products stop
  appearing immediately): PASS — Scenario 3; `cascade_delete_surveys_for_project`
  sets `deleted_at` on every still-active survey in the same request, and
  the shared `access.py` scoping excludes them from every read path
  immediately.
- **SC-003** (0% of deletions succeed while processing is queued/running):
  PASS — Scenario 2 plus `test_survey_deletion.py`/`test_project_deletion.py`
  parametrized over `queued`/`processing`.
- **SC-004** (100% of deletions traceable to user + time): PASS —
  `deleted_at`/`deleted_by` are set on every delete path (independent survey
  delete, project delete, and the project's cascade helper), asserted
  directly in the integration tests.
- **SC-005** (every deletion requires explicit confirmation): PASS —
  `ConfirmDialog` gates both the survey- and project-delete flows;
  `survey-delete.test.tsx`/`project-delete.test.tsx` assert the API is not
  called until the confirm button is clicked.
- **SC-006** (100% of restores come back with history/products intact):
  PASS — restore only ever clears `deleted_at`/`deleted_by` (and the cascade
  flag); `ProcessingRun`/`RunOption`/`DerivedArtifact` rows are never touched
  by delete or restore, so a restored survey's history/products are exactly
  what they were before deletion (Scenario 4/5 confirm the reappearance).
- **SC-007** (find + restore from Recently Deleted in <1 minute): PASS —
  `GET /deleted` is a single global, owner-scoped listing with a one-click
  restore action per row (`RecentlyDeletedPage.tsx`), verified in
  `recently-deleted.test.tsx` and Scenario 4/5 above.

**Done when** (quickstart.md): all scenarios pass and both a real-LAZ ingest
and a real-purge pass have been run against the compose stack — all
satisfied above.
