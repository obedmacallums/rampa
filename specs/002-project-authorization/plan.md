# Implementation Plan: Project Authorization

**Branch**: `002-project-authorization` | **Date**: 2026-07-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-project-authorization/spec.md`

## Summary

Replace the current "every authenticated user sees every project" model with
project-scoped authorization: a `ProjectMembership` association (roles owner /
member) gates every project-scoped read and write. Creators become owners,
owners manage the member list from the project page, non-members receive
responses indistinguishable from nonexistence (404 semantics via scoped
querysets), and a data migration backfills each existing project's creator as
its owner. Server-to-server paths (tusd hook, pipeline tasks) are unaffected.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.7 / React 18 (frontend)

**Primary Dependencies**: Django 5 + DRF (session auth already in place),
PostGIS; React + Zustand + i18next. No new dependencies.

**Storage**: PostgreSQL/PostGIS — one new table (project membership). Object
storage untouched.

**Testing**: pytest + pytest-django (integration tests around access
boundaries and membership management), vitest (i18n completeness).

**Target Platform**: existing docker compose stack; no new services.

**Project Type**: web application (backend + frontend, existing layout).

**Performance Goals**: project list and project pages within current budgets
(SC-004); membership check adds one indexed join per request.

**Constraints**: denial must be indistinguishable from nonexistence (FR-002);
presigned artifact URLs keep their existing ≤ 3600 s expiry, which satisfies
the ≤ 60 min revocation bound (FR-008/SC-005); Spanish-primary i18n
(Principle IX).

**Scale/Scope**: single-digit teams per installation today; the design must
simply not regress list latency (indexed FK lookups suffice).

## Constitution Check

*GATE: evaluated against constitution v1.3.0 before Phase 0; re-evaluated after Phase 1.*

- **I. Rasters/tiles split** — untouched; no analysis surface changes. PASS
- **II. Thin backend, interactive frontend** — users/projects persistence is
  explicitly a backend responsibility; membership checks are per-request
  authorization, not interactive analysis. PASS
- **III. Async ingest** — upload/processing flow unchanged; the tusd hook and
  Celery chain act as platform (FR-012), no membership checks added inside
  the pipeline. PASS
- **IV. Station-based evaluation** — not applicable to this feature. PASS
- **V. Assisted detection** — not applicable. PASS
- **VIII. Test-first for analysis core** — feature is not analysis-core, but
  001's convention (contract/integration tests written first) is retained.
  PASS
- **IX. Bilingual by design** — all new UI texts go through the i18n layer,
  es primary + en. PASS
- **Demo-first infra** — no new services, single `docker compose up`
  preserved. PASS

No violations → Complexity Tracking not required.

*Post-design re-check (after Phase 1)*: design introduces one table, one
scoping helper, membership endpoints and a members panel — no principle
touched. PASS.

## Project Structure

### Documentation (this feature)

```text
specs/002-project-authorization/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── rest-api.md      # Phase 1 output
└── checklists/
    └── requirements.md  # Spec quality checklist (done)
```

### Source Code (repository root)

```text
backend/
├── apps/
│   ├── projects/
│   │   ├── models.py        # + ProjectMembership
│   │   ├── access.py        # NEW: projects_for(user), scoped get-or-404 helpers
│   │   ├── serializers.py   # + membership serializer
│   │   ├── views.py         # scope list; + members endpoints
│   │   ├── urls.py          # + members routes
│   │   ├── migrations/      # + membership table, + owner backfill (data migration)
│   │   └── management/commands/members.py  # NEW: admin channel (add/remove/list)
│   └── surveys/
│       ├── views_surveys.py # querysets scoped through access helpers
│       ├── views_uploads.py # idem
│       └── views_hooks.py   # untouched (shared-secret, acts as platform)
└── tests/
    └── integration/
        ├── test_access_boundaries.py   # NEW: US1/US2 isolation matrix
        ├── test_membership_api.py      # NEW: US3 manage members
        └── test_membership_migration.py# NEW: US4 backfill
frontend/
└── src/
    ├── api/client.ts            # + members API calls
    ├── components/ProjectMembers.tsx  # NEW: member list + owner controls
    ├── stores/members.ts        # NEW
    ├── pages/ProjectDetailPage.tsx    # mount members panel
    └── i18n/{es,en}/*.json      # + membership texts
```

**Structure Decision**: existing web-app layout; the only new backend module
is `apps/projects/access.py`, the single enforcement point every
project-scoped view routes through (see research R1).
