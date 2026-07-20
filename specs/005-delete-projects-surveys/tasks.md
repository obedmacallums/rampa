# Tasks: Delete Projects and Surveys

**Input**: Design documents from `/specs/005-delete-projects-surveys/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/rest-api.md, quickstart.md

**Tests**: Included where the spec/constitution demands them: permission checks
(`not_owner`/`not_deletable`/`not_restorable`), the deleted-row scoping
guarantee (FR-005), cascade delete/restore semantics (FR-011), and the purge
job are all regression-critical and get integration coverage. No blanket TDD
elsewhere (matches 004's convention).

**Organization**: Tasks are grouped by user story (US1 delete a survey, US2
delete a project, US3 recently-deleted + restore) after a foundational phase
that reworks the schema and access-scoping shared by all stories.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 (user-story phases only)

## Phase 1: Setup

**Purpose**: The recovery-window setting and the storage primitive every delete/restore path needs

- [X] T001 Add `DELETE_RECOVERY_DAYS = 7` setting in `backend/config/settings.py` (mirrors the existing `UPLOAD_EXPIRY_DAYS` convention)
- [X] T002 [P] `delete_prefix(prefix: str) -> None` in `backend/pipeline/storage.py`: paginated `list_objects_v2` + batched `delete_objects` against the internal S3 client, so a project's or survey's entire object-storage prefix can be removed recursively (no such capability exists today — `delete_object` only removes one key at a time)
- [X] T003 [P] Unit test for `delete_prefix` in `backend/tests/unit/test_storage_delete_prefix.py` against MinIO: seed several objects under a prefix (and one outside it), delete the prefix, assert only the in-prefix objects are gone

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema, access-scoping, permissions, and error vocabulary shared by every story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Schema migration in `backend/apps/projects/models.py` + `backend/apps/projects/migrations/`: add `Project.deleted_at` (`DateTimeField(null=True, blank=True)`) and `Project.deleted_by` (`FK(User, null=True, blank=True, on_delete=SET_NULL, related_name="+")`)
- [X] T005 Schema migration in `backend/apps/surveys/models.py` + `backend/apps/surveys/migrations/`: add `Survey.deleted_at`, `Survey.deleted_by` (same shape as T004) and `Survey.deleted_via_project_cascade` (`BooleanField(default=False)`)
- [X] T006 Update `backend/apps/projects/access.py`: `projects_for` and `get_project_or_404` exclude `deleted_at__isnull=False` rows; `get_survey_or_404` additionally excludes surveys whose own `deleted_at` is set or whose `project.deleted_at` is set (FR-005) — the single enforcement point every read path already goes through (002 R1)
- [X] T007 [P] Add `is_owner` (SerializerMethodField using `access.is_owner`) to `ProjectSummarySerializer` in `backend/apps/projects/serializers.py`, so the frontend can gate delete actions per project
- [X] T008 Add `not_deletable` and `not_restorable` error codes (both default to their own i18n key via `ApiError`); broaden the existing `not_owner` message text in `frontend/src/i18n/es/errors.json` and `.../en/errors.json` from membership-specific wording to a generic "must be an owner" phrasing (R7); add `not_deletable`/`not_restorable` keys to both files
- [X] T009 [P] Integration test in `backend/tests/integration/test_access_deletion_scope.py`: a soft-deleted project disappears from `projects_for`/`GET /projects`; a soft-deleted survey (or one whose project is soft-deleted) disappears from `get_survey_or_404`/the project's survey list; `ProjectSummarySerializer` output includes correct `is_owner` for an owner and a plain member

**Checkpoint**: Foundation ready — soft-delete fields exist, are enforced everywhere reads happen, and the permission/error vocabulary is in place

---

## Phase 3: User Story 1 - Remove a survey that is no longer needed (Priority: P1) 🎯 MVP

**Goal**: A project owner can delete one survey independently; it and everything derived from it disappear, the rest of the project is untouched

**Independent Test**: Create a project with two surveys, delete one via `DELETE /surveys/{id}`, verify only that survey disappears from listings while the project and the other survey remain fully intact (quickstart Scenarios 1–2)

- [X] T010 [US1] `delete()` method on the existing `SurveyDetailView` in `backend/apps/surveys/views_surveys.py` (same URL, `surveys/<uuid:survey_id>`, no urls.py change needed): `access.is_owner` check (403 `not_owner`), reject with 409 `not_deletable` while `survey.status` is `queued`/`processing`, otherwise set `deleted_at`/`deleted_by` and return 204
- [X] T011 [P] [US1] Integration test in `backend/tests/integration/test_survey_deletion.py`: owner deletes successfully (excluded from listing afterward, other surveys unaffected), non-owner rejected 403, processing survey rejected 409, deleting an already-deleted/nonexistent survey 404
- [X] T012 [US1] Frontend API client: `deleteSurvey(surveyId)` in `frontend/src/api/client.ts`
- [X] T013 [US1] Delete action (owner-only, via the project's `is_owner`) + `ConfirmDialog` per survey row in `frontend/src/pages/ProjectDetailPage.tsx`, mirroring `ProjectMembers.tsx`'s remove-member confirm flow
- [X] T014 [P] [US1] i18n keys in `frontend/src/i18n/es/common.json` and `.../en/common.json`: `surveys.delete`, `surveys.delete_confirm`
- [X] T015 [P] [US1] Frontend test in `frontend/tests/survey-delete.test.tsx`: delete button hidden for non-owners, confirm dialog gates the actual API call

**Checkpoint**: US1 fully functional — a survey can be deleted independently, unattached to project-level deletion

---

## Phase 4: User Story 2 - Remove an entire project (Priority: P2)

**Goal**: A project owner can delete an entire project; every survey still active at that moment is cascade-deleted with it

**Independent Test**: Create a project with two surveys (one completed, one failed), delete the project via `DELETE /projects/{id}`, verify the project and both surveys disappear while other, unrelated projects are unaffected (quickstart Scenario 3)

- [X] T016 [US2] `cascade_delete_surveys_for_project(project, user)` in new `backend/apps/surveys/deletion.py`: sets `deleted_at`/`deleted_by`/`deleted_via_project_cascade=True` on every survey of `project` with `deleted_at IS NULL` — the one place `apps/projects` lazily imports `apps.surveys` from (mirrors `access.get_survey_or_404`'s existing lazy cross-app import style, R2)
- [X] T017 [US2] `ProjectDetailView.delete()` (new view) in `backend/apps/projects/views.py`: `access.is_owner` check (403 `not_owner`); reject with 409 `not_deletable` if any survey has `status` in `queued`/`processing` or any `UploadSession` has `state=active`; otherwise set the project's `deleted_at`/`deleted_by`, call T016's cascade helper, return 204
- [X] T018 [US2] Route `DELETE /projects/{project_id}` → `ProjectDetailView` in `backend/apps/projects/urls.py`
- [X] T019 [P] [US2] Integration test in `backend/tests/integration/test_project_deletion.py`: owner deletes a project with several surveys in different states → project and all its (then-active) surveys disappear (`deleted_via_project_cascade=True` on each); blocked 409 while a survey is processing or an upload is active; non-owner rejected 403; a survey deleted independently *before* the project stays `deleted_via_project_cascade=False`
- [X] T020 [US2] Frontend API client: `deleteProject(projectId)` in `frontend/src/api/client.ts`
- [X] T021 [US2] Delete-project action (owner-only) + `ConfirmDialog` in `frontend/src/pages/ProjectDetailPage.tsx` (or `ProjectsPage.tsx` row — whichever keeps the confirm copy clearest about cascading to every survey)
- [X] T022 [P] [US2] i18n keys es/en: `projects.delete`, `projects.delete_confirm` (mentioning the cascade)
- [X] T023 [P] [US2] Frontend test for the project-delete flow (owner-only visibility, confirm gate) in `frontend/tests/project-delete.test.tsx`

**Checkpoint**: US2 fully functional — deleting a project cascades correctly and independently-deleted surveys are unaffected

---

## Phase 5: User Story 3 - Undo an accidental deletion (Priority: P3)

**Goal**: An owner can browse everything they deleted and still can restore, and restoring a project brings its cascaded surveys back as one unit; past the recovery window, a background job purges permanently

**Independent Test**: Delete a survey and a project, restore both from `GET /deleted` within the recovery window, verify both come back with history/products intact and the project's cascaded surveys return together; verify a backdated deletion is rejected with `not_restorable` and gets purged by the background job (quickstart Scenarios 4–7)

- [X] T024 [US3] `cascade_restore_surveys_for_project(project, user)` in `backend/apps/surveys/deletion.py` (same file as T016): clears `deleted_at`/`deleted_by` and resets `deleted_via_project_cascade=False` on every survey of `project` with `deleted_via_project_cascade=True`
- [X] T025 [US3] `ProjectRestoreView` (new, `POST`) in `backend/apps/projects/views.py` + route `projects/{project_id}/restore`: owner-only lookup that *includes* soft-deleted rows scoped to the requester's ownership; 404 `not_restorable` if not found, not deleted, or past `DELETE_RECOVERY_DAYS`; otherwise clear the project's `deleted_at`/`deleted_by`, call T024's cascade helper, return the refreshed `ProjectSummarySerializer` (200)
- [X] T026 [US3] `SurveyRestoreView` (new, `POST`) in `backend/apps/surveys/views_surveys.py` + route `surveys/{survey_id}/restore`: same owner-only + window rules as T025 but for an independently-deleted survey (`deleted_via_project_cascade=False`); 200 with `SurveySummarySerializer`
- [X] T027 [US3] `RecentlyDeletedView` (new, `GET`, global — not project-scoped) in `backend/apps/projects/views.py` + route `deleted`: lists soft-deleted projects the requester owns, and independently-deleted (`deleted_via_project_cascade=False`) surveys in projects they own, each with `deleted_at` and a computed `purge_at = deleted_at + DELETE_RECOVERY_DAYS` (contracts/rest-api.md shape)
- [X] T028 [P] [US3] Integration test in `backend/tests/integration/test_recently_deleted_and_restore.py`: listing shape and ownership scoping; restoring an independent survey brings it back; restoring a project cascade-restores its (then-cascaded) surveys as a unit while a survey deleted independently beforehand stays deleted; restoring past the recovery window (or a nonexistent/foreign id) → 404 `not_restorable`; non-owner rejected 403
- [X] T029 [US3] `purge_expired_deletions` Celery task in `backend/apps/surveys/tasks_maintenance.py` (alongside the existing `purge_expired_upload_sessions`): for every `Project` and independently-deleted `Survey` past `DELETE_RECOVERY_DAYS`, call T002's `delete_prefix` on its storage prefix then delete the row (DB `CASCADE` removes every dependent `ProcessingRun`/`RunOption`/`DerivedArtifact`/`UploadSession`); register it in `CELERY_BEAT_SCHEDULE` in `backend/config/settings.py`
- [X] T030 [P] [US3] Integration test in `backend/tests/integration/test_purge_expired_deletions.py`: a backdated-past-window project/survey is physically removed from the database and its object-storage prefix is empty afterward; a project/survey still within the window is untouched
- [X] T031 [US3] Frontend API client: `restoreProject(projectId)`, `restoreSurvey(surveyId)`, `listDeleted()` + `DeletedProject`/`DeletedSurvey` types in `frontend/src/api/client.ts`
- [X] T032 [US3] New `frontend/src/pages/RecentlyDeletedPage.tsx`: lists deleted projects and independently-deleted surveys with a restore action per row and a "purges in N days" countdown; route `/deleted` in `frontend/src/App.tsx`; a nav link from `frontend/src/pages/ProjectsPage.tsx`
- [X] T033 [P] [US3] i18n keys es/en: `deleted.title`, `deleted.empty`, `deleted.restore`, `deleted.expires_in`, `nav.deleted`
- [X] T034 [P] [US3] Frontend test in `frontend/tests/recently-deleted.test.tsx`: renders listed projects/surveys, restore action calls the right endpoint and removes the row

**Checkpoint**: All user stories independently functional

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T035 [P] Verify SC-001…SC-007 against the implementation; update `specs/005-delete-projects-surveys/checklists/requirements.md` notes with the result
- [X] T036 Run full quickstart validation (`specs/005-delete-projects-surveys/quickstart.md` Scenarios 1–7) against the compose stack; record results in `specs/005-delete-projects-surveys/validation-notes.md`, following the pattern established in 004's

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — T001/T002 parallel; T003 depends on T002
- **Foundational (Phase 2)**: Depends on Phase 1. Internal order: T004 ∥ T005; T006 depends on T004+T005; T007 parallel with T006; T008 parallel with T006/T007; T009 depends on T006+T007
- **US1 (Phase 3)**: Depends on Phase 2. T010 → T011; T012 parallel with backend; T013 depends on T012; T014 ∥ T015 depend on T013
- **US2 (Phase 4)**: Depends on Phase 2 (not on US1). T016 → T017 → T018 → T019; T020 parallel with backend; T021 depends on T020; T022 ∥ T023 depend on T021
- **US3 (Phase 5)**: Depends on Phase 2 and reuses US1's `SurveyDetailView`/US2's `ProjectDetailView`/`deletion.py` (T016). T024 depends on T016; T025 depends on T024; T026 independent of T024/T025 (restores a survey directly); T027 depends on the deleted-scoping from Phase 2; T028 depends on T025-T027; T029 depends on T002; T030 depends on T029; T031 parallel with backend; T032 depends on T031; T033 ∥ T034 depend on T032

### User Story Dependencies

- **US1 (P1)**: Foundational only — delivers the MVP (delete a survey)
- **US2 (P2)**: Foundational only (independent of US1's frontend work, though both touch `ProjectDetailPage.tsx` sequentially if done by the same person)
- **US3 (P3)**: Foundational + US1's survey-delete view (extended with restore) + US2's project-delete view and cascade helper — restoring assumes deleting already works

### Parallel Opportunities

- Phase 1: T001 ∥ T002
- Phase 2: (T004 ∥ T005) → T006; T007 ∥ T008 (once T006 lands); T009 last
- Phase 3: T012 ∥ (T010→T011); T014 ∥ T015
- Phase 4: T020 ∥ (T016→T017→T018→T019); T022 ∥ T023
- Phase 5: T026 ∥ (T024→T025); T031 ∥ (T027→T028); T033 ∥ T034
- US1 and US2 backend work (T010-T011 vs. T016-T019) can proceed in parallel by different developers once Phase 2 is done

## Parallel Example: User Story 1

```bash
# Backend and frontend tracks in parallel after Phase 2:
Task: "delete() on SurveyDetailView in backend/apps/surveys/views_surveys.py"   # T010
Task: "deleteSurvey API client in frontend/src/api/client.ts"                    # T012

# Once T010 lands:
Task: "Integration test in backend/tests/integration/test_survey_deletion.py"   # T011
```

## Implementation Strategy

### MVP First (US1)

1. Phase 1 (setup) → Phase 2 (schema, scoping, permissions, error vocabulary)
2. Phase 3 (US1) → **STOP and VALIDATE** with quickstart Scenarios 1–2: an owner can delete one survey independently, blocked correctly by ownership/in-flight processing
3. Deploy/demo: deleting a survey is the smallest, safest, most requested slice ("no se procesaron... o simplemente ya no los quiero")

### Incremental Delivery

- US1 = MVP (delete a survey)
- US2 adds whole-project deletion with correct cascading
- US3 adds the safety net (Recently Deleted + restore + background purge) once deletion itself is proven
- Each checkpoint leaves the platform fully working with prior behavior intact — deleted rows simply stop appearing; nothing else changes until the purge job (US3) ever touches storage

## Notes

- No task ever deletes an object-storage file outside `purge_expired_deletions` (T029) — every delete/restore endpoint only flips DB columns, keeping the operation fast (SC-001/SC-007) and reversible up to the recovery window (FR-006).
- `deleted_via_project_cascade` is the only signal separating "restore this survey on its own" from "this survey comes back only if its project is restored" — get T016/T024/T027 right and the rest of US3 follows directly.
