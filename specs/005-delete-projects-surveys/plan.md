# Implementation Plan: Delete Projects and Surveys

**Branch**: `main` (no feature branch; git extension not installed) | **Date**: 2026-07-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-delete-projects-surveys/spec.md`

## Summary

Add owner-only soft deletion for both `Project` and `Survey`, with a shared
recovery window before a background job permanently purges database rows and
their object-storage files. Deleting a project cascades to every survey that
was still active at that moment (tagged so an independent, earlier survey
deletion is never affected); restoring a project brings those cascaded
surveys back as one unit. A global "Recently Deleted" page lists everything
an owner can still restore. Deletion is blocked while a survey has processing
queued/running, or while a project has any of that or an upload actively in
progress. Technical approach: `deleted_at`/`deleted_by` fields on both models
(plus a `deleted_via_project_cascade` flag on `Survey`), new DELETE/restore
endpoints reusing the existing owner-only permission helper (`access.is_owner`,
002), a new recursive object-storage prefix-delete helper, and a Celery beat
task mirroring the existing expired-upload purge job.

## Technical Context

**Language/Version**: Python 3.12 (backend/workers), TypeScript 5.x + Node 22 (frontend) — unchanged from 001/004

**Primary Dependencies**: Django 5 + DRF, Celery 5 + Redis, boto3; React 18 + Vite + Zustand + react-i18next — unchanged; no new dependencies

**Storage**: PostGIS (metadata: `deleted_at`/`deleted_by` on Project/Survey, a cascade-tag on Survey) + S3-compatible object storage (recursive prefix delete, new capability in `pipeline/storage.py`)

**Testing**: pytest + pytest-django (soft-delete/restore/cascade semantics, permission checks, purge job, storage prefix-delete against MinIO); Vitest + RTL (delete/restore UI flows, confirmation dialogs)

**Target Platform**: Linux server containers (linux/arm64 + linux/amd64); modern browsers — unchanged

**Project Type**: Web application (existing backend + frontend + worker + compose infra) — unchanged

**Performance Goals**: Deletion and restore are synchronous, sub-second operations (metadata-only; no file I/O on the request path — matches SC-001/SC-007's "under 30/60 seconds" including UI navigation, not backend latency). Purge is a periodic background job, not user-facing.

**Constraints**: Deletion/restore never touch object storage synchronously (only DB rows flip `deleted_at`); only the periodic purge job performs S3 deletes, keeping the request path fast and matching the existing expired-upload-purge pattern. Files must never be removed from S3 before their recovery window elapses. No pipeline stage assumes cloud fits in RAM (unaffected — no pipeline changes here).

**Scale/Scope**: 2 entities gain soft-delete (`Project`, `Survey`); 5 new endpoints (project delete/restore, survey delete/restore, recently-deleted listing); 1 new background job; 1 new storage helper (recursive prefix delete); 1 new frontend page (Recently Deleted) plus delete actions on 2 existing pages.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Analysis on rasters, viz on tiles | Not touched — no analysis code involved. | N/A |
| II. Thin backend, interactive frontend | Delete/restore/listing endpoints serve/mutate metadata only; no new interactive client-side analysis introduced. | PASS |
| III. Async ingest, always | Deletion is an explicit, confirmed, synchronous metadata operation distinct from the ingest pipeline — it does not mutate or reprocess any derived artifact, it removes it (after an explicit confirmation and a recovery window), which is a different guarantee than "never mutate a published artifact in place." Physical purge (real file removal) is itself an async background job, consistent with "artifacts are immutable outputs of a versioned run" until the user explicitly, deliberately removes the whole run's owner (survey/project). | PASS |
| IV. Station-based evaluation | Not touched. | N/A |
| V. Assisted detection, human authority | Not touched — no detection output involved. | N/A |
| VI. Evaluation profiles as data | Not touched. | N/A |
| VII. Reproducible reports | Not touched — no reports exist yet in the codebase. | N/A |
| VIII. Test-first analysis core | Not touched — no analysis engine code. | N/A |
| IX. Bilingual by design | All new user-visible text (confirmation dialogs, Recently Deleted page, new error codes) ships through the existing es/en i18n catalogs, no exceptions. | PASS |
| X. Mining focus, neutral core | `Project`/`Survey` stay the existing generic entities; deletion adds only generic `deleted_at`/`deleted_by`/cascade-tag fields, no domain-specific concepts. | PASS |
| XI. AI as isolated service | Not touched. | N/A |
| Tech constraints | Same stack; files only in object storage (purge job is the only code path that ever deletes them, and only after the recovery window); multi-arch images untouched; CRS/memory-budget rules unaffected (no pipeline changes). | PASS |

**Initial gate result: PASS (no violations, Complexity Tracking empty).**

**Post-Phase-1 re-check**: design artifacts (data model, contracts) introduce no
deviation — soft-delete fields are generic, the purge job mirrors an existing
pattern (expired-upload purge), and no analysis/reporting/AI code paths are
touched. **PASS.**

## Project Structure

### Documentation (this feature)

```text
specs/005-delete-projects-surveys/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── rest-api.md      # Phase 1 output (delta over 001/002/004 contracts)
└── tasks.md              # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── apps/projects/
│   ├── models.py            # Project gains deleted_at, deleted_by
│   ├── migrations/          # schema migration
│   ├── access.py            # projects_for/get_project_or_404 exclude deleted_at;
│   │                        #   unchanged is_owner reused as the permission check
│   ├── serializers.py       # ProjectSummarySerializer gains is_owner
│   ├── views.py             # NEW: ProjectDetailView.delete, ProjectRestoreView,
│   │                        #   RecentlyDeletedView (global listing)
│   └── urls.py              # + DELETE/restore/deleted routes
├── apps/surveys/
│   ├── models.py            # Survey gains deleted_at, deleted_by,
│   │                        #   deleted_via_project_cascade
│   ├── migrations/          # schema migration
│   ├── deletion.py          # NEW: cascade_delete_surveys_for_project /
│   │                        #   cascade_restore_surveys_for_project — the one
│   │                        #   place apps/projects lazily imports into
│   │                        #   (mirrors the existing access.get_survey_or_404
│   │                        #   lazy cross-app import style)
│   ├── views_surveys.py     # SurveyDetailView gains delete(); NEW SurveyRestoreView
│   ├── urls.py               # + DELETE/restore routes
│   └── tasks_maintenance.py # NEW purge_expired_deletions task alongside the
│                             #   existing purge_expired_upload_sessions
├── pipeline/
│   └── storage.py           # NEW: delete_prefix(prefix) — recursive S3 delete
└── tests/
    ├── unit/                # storage.delete_prefix, cascade helpers
    └── integration/         # delete/restore API contract, permission checks,
                              #   purge job, recently-deleted listing

frontend/
├── src/
│   ├── api/client.ts        # deleteProject/restoreProject/deleteSurvey/
│   │                        #   restoreSurvey/listDeleted + types
│   ├── pages/
│   │   ├── ProjectsPage.tsx      # delete action per project (owner-only) +
│   │   │                         #   link to Recently Deleted
│   │   ├── ProjectDetailPage.tsx # delete action per survey + delete-project
│   │   │                         #   action (owner-only)
│   │   └── RecentlyDeletedPage.tsx   # NEW: global restore view
│   ├── i18n/                 # new keys (es/en): delete/restore copy, new
│   │                          #   error codes
│   └── App.tsx                # + /deleted route
└── tests/
```

**Structure Decision**: Extend the existing web-application layout in place,
following the established cross-app boundary (`surveys` depends on
`projects`, never the reverse): the project-deletion view lazily imports a
small `apps/surveys/deletion.py` helper for the survey-cascade step — the
same lazy-import style `apps/projects/access.get_survey_or_404` already uses
to reach into `apps.surveys.models`. No new services, packages, or
dependencies.

## Complexity Tracking

No constitution violations — table intentionally empty.
