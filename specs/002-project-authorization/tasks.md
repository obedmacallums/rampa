# Tasks: Project Authorization

**Input**: Design documents from `/specs/002-project-authorization/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/rest-api.md, quickstart.md

**Tests**: Included — plan.md retains 001's convention (integration tests written first, must fail before implementation). Test files: `test_access_boundaries.py` (US1/US2), `test_membership_api.py` (US3), `test_membership_migration.py` (US4), plus the existing frontend i18n parity test.

**Organization**: Tasks are grouped by user story so each story is independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

Existing web-app layout: `backend/apps/`, `backend/tests/`, `frontend/src/` (see plan.md Project Structure).

---

## Phase 1: Setup

**Purpose**: Package scaffolding — no new dependencies, no new services (plan.md Technical Context).

- [X] T001 Create management-command package scaffolding: `backend/apps/projects/management/__init__.py` and `backend/apps/projects/management/commands/__init__.py` (empty files)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The membership table and the single enforcement point (`access.py`, research R1) that every user story routes through.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 Add `ProjectMembership` model to `backend/apps/projects/models.py` per data-model.md: UUID pk; FKs `project` (CASCADE) and `user` (CASCADE); `role` enum `owner|member`; `granted_by` FK SET_NULL nullable; `granted_at` auto; `unique(project, user)` constraint; secondary index `(user, project)` to serve `projects_for(user)` lookups
- [X] T003 Generate schema migration `backend/apps/projects/migrations/0002_projectmembership.py` (`makemigrations projects`) creating the table, unique constraint, and indexes — schema only, no data backfill here (backfill is US4)
- [X] T004 Create `backend/apps/projects/access.py` with the scoped-queryset helpers (research R1): `projects_for(user)` returning the membership-scoped `Project` queryset, `get_project_or_404(user, project_id)`, and `get_survey_or_404(user, survey_id)` resolving through that scope so denial raises the same 404 as nonexistence (FR-002); include `is_owner(user, project)` helper for US3 mutations

**Checkpoint**: Table + enforcement helpers exist — user story implementation can begin.

---

## Phase 3: User Story 1 - Access limited to my projects (Priority: P1) 🎯 MVP

**Goal**: Every project-scoped read/write is gated by membership; non-members get responses byte-identical to nonexistence (FR-001, FR-002). Server-to-server paths stay unscoped (FR-012).

**Independent Test**: Two users, two projects with disjoint membership (memberships created via ORM in test fixtures). Each user's list shows only their project; every project/survey surface of the other project returns the same `404 not_found` envelope as a random UUID; no presigned URLs leak.

### Tests for User Story 1 (write FIRST — must fail before implementation)

- [X] T005 [US1] Write integration test `backend/tests/integration/test_access_boundaries.py` covering the isolation matrix from spec US1 acceptance scenarios: (a) `GET /api/v1/projects` returns only the caller's memberships with correct survey counts; (b) non-member `GET /projects/{id}/surveys`, `GET/POST /projects/{id}/uploads`, `GET /surveys/{id}`, `GET /surveys/{id}/artifacts`, `POST /surveys/{id}/retry` all return a `404 not_found` envelope byte-identical to a random-UUID request; (c) a member retains full existing behavior on their own project (list, upload init, status, retry, artifacts); (d) `POST /api/v1/hooks/tusd` still works with shared secret and no session (FR-012 regression guard)

### Implementation for User Story 1

- [X] T006 [US1] Scope the project list in `backend/apps/projects/views.py`: `ProjectListCreateView.get` queries via `access.projects_for(request.user)` instead of `Project.objects` (keep `select_related("crs")` and survey counts)
- [X] T007 [P] [US1] Scope survey views in `backend/apps/surveys/views_surveys.py`: replace `get_object_or_404(Project, ...)` and `get_object_or_404(Survey..., ...)` (project surveys list, survey detail, artifacts, retry) with `access.get_project_or_404` / `access.get_survey_or_404`; `views_hooks.py` stays untouched
- [X] T008 [P] [US1] Scope upload views in `backend/apps/surveys/views_uploads.py`: both `get_object_or_404(Project, ...)` call sites (upload create, pending uploads list) go through `access.get_project_or_404`

**Checkpoint**: `pytest backend/tests/integration/test_access_boundaries.py` green (except US2 cases if written together); the platform is membership-gated. MVP boundary exists.

---

## Phase 4: User Story 2 - Create my own projects (Priority: P1)

**Goal**: Any authenticated user creates projects; the creator automatically becomes owner at creation time (FR-003); the new project is invisible to everyone else.

**Independent Test**: User creates a project → they are recorded as `owner` (membership row exists, `granted_by` = themselves), it appears in their list; a second user's list omits it and its direct URL returns 404.

### Tests for User Story 2 (write FIRST — must fail before implementation)

- [X] T009 [US2] Extend `backend/tests/integration/test_access_boundaries.py` with creation scenarios: `POST /api/v1/projects` creates exactly one membership row `(creator, role=owner, granted_by=creator)`; the project appears in the creator's list and is invisible (list + 404 on direct access) to another user; name-collision with an invisible project still returns the "name taken" error (spec edge case)

### Implementation for User Story 2

- [X] T010 [US2] In `backend/apps/projects/views.py` `ProjectListCreateView.post`: wrap project creation in a transaction that also creates `ProjectMembership(project, request.user, role=owner, granted_by=request.user)` (FR-003); keep the global unique-name check unchanged (spec assumption)

**Checkpoint**: Both P1 stories done — full isolation plus self-service creation. Independently deployable increment.

---

## Phase 5: User Story 3 - Invite collaborators and revoke access (Priority: P2)

**Goal**: Owners manage the member list from the project page (add by exact username, remove, grant/revoke ownership); every member sees the list with audit columns; the ≥1-owner invariant is enforced transactionally (FR-004…FR-009); UI texts exist in es (primary) and en (FR-011).

**Independent Test**: Quickstart Scenario 2 — owner adds a second user by username (they gain access), removes them (access ends on next request); a non-owner member sees the list but gets `403 not_owner` on mutations; sole-owner removal/downgrade returns `409 last_owner`.

### Tests for User Story 3 (write FIRST — must fail before implementation)

- [X] T011 [US3] Write integration test `backend/tests/integration/test_membership_api.py` against contracts/rest-api.md: `GET /projects/{id}/members` visible to any member with `username/role/granted_by/granted_at` rows, 404 for non-members; `POST` owner-only (`403 not_owner` for members) with `201`, `404 user_not_found`, `409 already_member`, `400 invalid_role`; `PATCH /members/{username}` role changes incl. `409 last_owner` on sole-owner downgrade and the two-owners handover flow (US3 scenario 6); `DELETE` incl. `204` revocation (target loses list + access on next request, FR-008), `409 last_owner` for sole owner self-removal, `404` unknown membership

### Backend implementation for User Story 3

- [X] T012 [P] [US3] Add `ProjectMembershipSerializer` to `backend/apps/projects/serializers.py` exposing `username`, `role`, `granted_by` (username or null), `granted_at` per the contract JSON shape
- [X] T013 [US3] Implement members endpoints in `backend/apps/projects/views.py`: `ProjectMembersView` (GET list for any member; POST owner-only resolving exact username with `404 user_not_found` / `409 already_member` / `400 invalid_role`) and `ProjectMemberDetailView` (PATCH role, DELETE) — mutations `select_for_update` the project's memberships and reject any operation leaving zero owners with `409 last_owner` (FR-006, data-model transitions table); non-member access resolves through `access.get_project_or_404`
- [X] T014 [US3] Register routes in `backend/apps/projects/urls.py`: `projects/<uuid:project_id>/members` and `projects/<uuid:project_id>/members/<str:username>`
- [X] T015 [P] [US3] Create admin-channel management command `backend/apps/projects/management/commands/members.py`: `manage.py members list|add|remove <project-name-or-id> [username] [--role owner|member]`, bypassing ownership checks (research R5; rescues sole-owner-deleted projects); mirror `createuser.py` conventions

### Frontend implementation for User Story 3

- [X] T016 [P] [US3] Add members API calls to `frontend/src/api/client.ts`: `listMembers(projectId)`, `addMember(projectId, username, role)`, `updateMemberRole(projectId, username, role)`, `removeMember(projectId, username)` mapping the contract's error codes
- [X] T017 [US3] Create Zustand store `frontend/src/stores/members.ts`: members list state, load/add/updateRole/remove actions, error surface keyed by the contract's `message_key`s
- [X] T018 [US3] Create `frontend/src/components/ProjectMembers.tsx`: member table (username, role, granted_by — null rendered as "system" —, granted_at) visible to all members; add-by-username form, role toggle, and remove buttons rendered only for owners (FR-007); confirmation on remove; inline error messages (user_not_found, already_member, last_owner, not_owner)
- [X] T019 [US3] Mount the members panel in `frontend/src/pages/ProjectDetailPage.tsx` so adding a teammate never leaves the project page (SC-006)
- [X] T020 [P] [US3] Add the contract's message keys to all four catalogs `frontend/src/i18n/es/common.json`, `frontend/src/i18n/en/common.json`, `frontend/src/i18n/es/errors.json`, `frontend/src/i18n/en/errors.json`: `members.title`, `members.role_owner`, `members.role_member`, `members.granted_by_system`, `members.add_label`, `members.remove_confirm`, `errors.user_not_found`, `errors.already_member`, `errors.last_owner`, `errors.not_owner` — Spanish primary, English secondary (FR-011); existing parity test `frontend/tests/i18n.test.ts` must stay green

**Checkpoint**: Quickstart Scenario 2 passes end-to-end; membership is self-service.

---

## Phase 6: User Story 4 - Existing projects survive the change (Priority: P3)

**Goal**: Zero-manual-step upgrade — every pre-existing project ends with its creator as sole owner, `granted_by=NULL` (system) (FR-010, research R3).

**Independent Test**: Quickstart Scenario 4 — on a pre-feature database, run migrations; each project's creator retains full access as owner (member panel shows "system"), other users see nothing.

### Tests for User Story 4 (write FIRST — must fail before implementation)

- [X] T021 [US4] Write migration test `backend/tests/integration/test_membership_migration.py`: given projects with distinct `created_by` and no memberships, the backfill creates exactly one `owner` membership per project with `granted_by=NULL`; it is idempotent (`get_or_create` — re-running creates nothing); projects that already have an owner membership are untouched

### Implementation for User Story 4

- [X] T022 [US4] Create data migration `backend/apps/projects/migrations/0003_backfill_owner_memberships.py`: for every `Project`, `get_or_create` `ProjectMembership(project, project.created_by, role=owner, granted_by=NULL)` (data-model migration plan); reverse operation is a no-op

**Checkpoint**: All four stories complete; upgrade path is safe.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T023 [P] Run the R1 smell check: grep `backend/apps/` user-request views for direct `Project.objects` / `Survey.objects` / `get_object_or_404(Project|Survey` usage outside `access.py`, migrations, hooks (`views_hooks.py`), and Celery tasks — fix any stragglers to route through `backend/apps/projects/access.py`
- [X] T024 Run full regression: `docker compose -f infra/docker-compose.yml exec backend pytest` (001 suites must stay green) and `cd frontend && npm test` (i18n parity), per quickstart Automated checks
- [X] T025 Execute quickstart.md Scenarios 1–4 manually against the compose stack (isolation, invite/revoke ≤ 5 s, presigned-URL expiry bound ≤ 60 min, backfill) and record results in `specs/002-project-authorization/quickstart.md` validation notes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: T002 → T003 → (T004 needs T002). BLOCKS all user stories.
- **US1 (Phase 3)**: needs Phase 2. Independent of other stories (tests create memberships via ORM).
- **US2 (Phase 4)**: needs Phase 2. Independent of US1's implementation (touches `post`, US1 touches `get`), but both edit `backend/apps/projects/views.py` — coordinate or sequence T006/T010.
- **US3 (Phase 5)**: needs Phase 2; builds on US1 semantics (404 scoping) for its non-member cases. Backend (T011–T015) and frontend (T016–T020) sub-tracks are independent of each other.
- **US4 (Phase 6)**: needs Phase 2 only (table must exist). Can run any time after T003.
- **Polish (Phase 7)**: after all desired stories.

### Within Each User Story

- Tests first, confirmed failing, then implementation (001 convention, plan.md).
- Serializer (T012) before endpoints (T013); endpoints before routes (T014).
- API client (T016) before store (T017) before component (T018) before mounting (T019).

### Parallel Opportunities

- After T004: US1, US4, and US3's frontend i18n task (T020) can all start in parallel.
- Within US1: T007 and T008 in parallel (different files) after T005 fails.
- Within US3: T012 ∥ T015 ∥ T016 ∥ T020; backend track ∥ frontend track.
- T023 in parallel with T024/T025.

---

## Parallel Example: User Story 1

```bash
# After T005 is written and failing, launch together:
Task: "Scope survey views through access helpers in backend/apps/surveys/views_surveys.py"   # T007
Task: "Scope upload views through access helpers in backend/apps/surveys/views_uploads.py"   # T008
```

## Parallel Example: User Story 3

```bash
# After T011 is written and failing, launch together:
Task: "Membership serializer in backend/apps/projects/serializers.py"                        # T012
Task: "Admin members command in backend/apps/projects/management/commands/members.py"        # T015
Task: "Members API calls in frontend/src/api/client.ts"                                      # T016
Task: "i18n keys in frontend/src/i18n/{es,en}/{common,errors}.json"                          # T020
```

---

## Implementation Strategy

### MVP First (User Stories 1+2)

1. Phase 1 + Phase 2 (T001–T004).
2. Phase 3 (US1): the access boundary — the entire point of the feature.
3. Phase 4 (US2): creator-becomes-owner. US1+US2 together form the deployable MVP (both are P1; without US2, newly created projects would have no owner and be invisible even to their creator, so ship them together).
4. **STOP and VALIDATE**: quickstart Scenario 1.

### Incremental Delivery

1. MVP (US1+US2) → validate → deployable.
2. US3 (self-service membership) → quickstart Scenario 2 → deploy.
3. US4 (backfill migration) → quickstart Scenario 4 → required before upgrading any real installation.
4. Polish: regression suite + manual scenarios.

Note: on a database that predates the feature, deploy of the MVP without US4's backfill would hide existing projects from their creators — for any real installation, run Phases 3/4/6 within the same release.

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks.
- Verify each story's tests fail before implementing; commit after each task or logical group.
- `backend/apps/surveys/views_hooks.py` and Celery tasks are deliberately NOT scoped (FR-012, research R4) — do not "fix" them in T023.
- Presigned URL expiry stays at 3600 s (research R6); no task touches artifact issuing beyond membership-scoping the endpoints.
