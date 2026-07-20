# Tasks: Selectable & Extensible Processing Options

**Input**: Design documents from `/specs/004-processing-options/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/rest-api.md, quickstart.md

**Tests**: Included where the spec/constitution demands them: US2's acceptance IS a test
(dummy-option e2e, SC-003), pipeline changes require pytest coverage + one real-LAZ
validation (constitution dev flow), and per-option publication/backfill are
regression-critical. No blanket TDD elsewhere.

**Organization**: Tasks grouped by user story (US1 selection at upload, US2
extensibility, US3 additional options on existing surveys) after a foundational
phase that reworks models and orchestration shared by all stories.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 (user-story phases only)

## Phase 1: Setup (Registry Foundation)

**Purpose**: The option/input-type registry every other task builds on

- [X] T001 Create option & input-type registry in `backend/pipeline/options.py`: `OptionSpec` and `InputTypeSpec` dataclasses per data-model.md (id, label_key, description_key, input_types, target_view, required, default_selected, active, prerequisites, producer), a module-level registry with `register_option` / `register_input_type`, helpers `options_for(input_type)`, `effective_selection(input_type, requested_ids)` (adds required + prerequisite closure; raises on unknown/inactive/inapplicable ids), `topo_order(ids)`, and import-time validation (unique ids, acyclic prerequisites, prerequisites cover the option's input types). Declare `point_cloud` input type and the three initial options (`elevation` required, `hillshade` prereq `elevation`, `point_cloud_3d`) with `producer=None` placeholders (wired in T005)
- [X] T002 [P] Unit tests for the registry in `backend/tests/unit/test_options_registry.py`: duplicate id rejected, prerequisite cycle rejected, input-type mismatch rejected, `effective_selection` adds required + closure and rejects invalid/inactive/inapplicable ids, `topo_order` puts prerequisites first, initial catalog matches research R8
- [X] T003 [P] Add i18n keys in `frontend/src/i18n/es/common.json` and `frontend/src/i18n/en/common.json`: `options.elevation.label/description`, `options.hillshade.label/description`, `options.point_cloud_3d.label/description`, option state labels (`options.state.pending/running/completed/failed/skipped/reused`), upload selection heading/help text

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Per-option producers, schema + backfill, and the dynamic per-option
orchestration — required by ALL user stories

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Split `backend/pipeline/stages/surfaces.py` into per-option producers: `produce_elevation(ctx)` (PDAL binning → COG DEM), `produce_hillshade(ctx, dem_path)` (gdaldem → COG), `produce_point_cloud_3d(ctx)` (untwine → COPC, PDAL fallback), each returning artifact descriptors (kind, path, resolution) without uploading; introduce a `RunContext` (workdir, input LAZ path, resolution) in the same module or `backend/pipeline/stages/context.py`; update `backend/tests/unit/test_stage_surfaces.py` to cover producers individually (hillshade consuming a DEM input; COPC fallback path)
- [X] T005 Wire producers into the registry in `backend/pipeline/options.py` (replace T001 placeholders); support a producer fulfilling several options (signature returns per-option artifact descriptors keyed by option id) per FR-015/R4
- [X] T006 Schema migration in `backend/apps/surveys/models.py` + `backend/apps/surveys/migrations/`: new `RunOption` model (run FK related_name="options", option_id, state enum pending/running/completed/failed/skipped/reused, reused_from FK null, failure_code, failure_message_key, started_at, finished_at, unique (run, option_id)); add `Survey.input_type` and `ProcessingRun.input_type` (CharField default `point_cloud`); `UploadSession.selected_options` (JSONField, schema default `list` — the effective selection is always computed from the registry and written by the initiation view (T016), never hardcoded in the schema, so the migration doesn't duplicate catalog knowledge); `DerivedArtifact.option_id` (CharField null here; promoted to NOT NULL in T033 after backfill)
- [X] T007 Backfill data migration in `backend/apps/surveys/migrations/` per data-model.md: `DerivedArtifact.option_id` from kind (dem→elevation, hillshade→hillshade, copc→point_cloud_3d); `RunOption` rows for every existing run (completed where artifact exists; failed/skipped consistent with run outcome); `UploadSession.selected_options` = standard set
- [X] T008 [P] Backfill integration test in `backend/tests/integration/test_options_backfill.py`: build pre-feature rows (runs with/without artifacts, failed runs), run migration, assert RunOption states, artifact attribution, and that survey detail/artifacts endpoints serve them (FR-012)
- [X] T009 Rework orchestration in `backend/apps/surveys/tasks.py`: `enqueue_run(survey, selection=None)` resolves effective selection (registry) and builds a dynamic chain — input-type prep steps (relocate → validation → reprojection; prep failure still aborts via `_AbortChain`) then one `run_option` task per option in topo order, then `finalize_run`; `run_option` wrapper marks its RunOption running/completed/failed, skips itself if a prerequisite's RunOption failed/skipped (marks skipped), and on success uploads + checksums + creates `DerivedArtifact` rows with option_id (per-option publication, FR-009); `finalize_run` sets run/survey state (completed only if all options completed/reused) and cleans the workdir; retry path creates the new run's RunOptions as `reused` (with reused_from) for options completed in a prior run (R5)
- [X] T010 Update `backend/apps/surveys/serializers.py`: `RunOptionSerializer`; `RunStatusSerializer` gains `input_type` and nested `options`; `SurveySummarySerializer`/`SurveyDetailSerializer` gain `input_type` per contracts/rest-api.md
- [X] T011 Artifact resolution helper in `backend/apps/surveys/resolution.py`: latest-completed-per-option across a survey's runs following `reused_from` transitively (FR-016), returning option→(artifact, producing run); unit test in `backend/tests/unit/test_artifact_resolution.py`
- [X] T012 [P] Per-option publication integration tests in `backend/tests/integration/test_per_option_publication.py`: subset selection produces exactly those artifacts; one option failing → run failed, completed options' artifacts published, dependents skipped (FR-009/FR-010); error codes translated keys only
- [X] T013 [P] Extend `backend/tests/integration/test_api_status_retry.py`: retry creates a new run reusing selection, `reused` states for previously completed options, only incomplete options re-execute (FR-004)

**Checkpoint**: Foundation ready — per-option pipeline works end-to-end with default selection; user story phases can start

---

## Phase 3: User Story 1 - Choose processing options when uploading (Priority: P1) 🎯 MVP

**Goal**: Options checklist at upload start; selection travels with the upload,
processing runs unattended with exactly that selection; products appear in their
declared views

**Independent Test**: Upload a file with only some options selected; verify exactly
those products are generated, appear in their declared views, and unselected
products are absent (quickstart Scenarios 1–3)

- [X] T014 [P] [US1] Catalog endpoint `GET /processing-options` in new `backend/apps/surveys/views_options.py` (query param `input_type` default `point_cloud`, `invalid_input_type` 400, serves active applicable options from registry per contracts/rest-api.md) + route in `backend/apps/surveys/urls.py`
- [X] T015 [P] [US1] Catalog contract test in `backend/tests/integration/test_api_options_catalog.py`: shape per contract, required/default/prerequisites flags, i18n keys only, inactive options absent, unknown input_type → 400
- [X] T016 [US1] Upload initiation in `backend/apps/surveys/views_uploads.py`: accept optional `selected_options`, validate + complete closure via registry (`invalid_options` 400 with `detail.invalid`), store effective selection on `UploadSession.selected_options`, echo `effective_options` in the 201 response; add `invalid_options`/`invalid_input_type` messages to `frontend/src/i18n/es/errors.json` and `frontend/src/i18n/en/errors.json`
- [X] T017 [US1] tusd hook in `backend/apps/surveys/views_hooks.py`: copy the session's effective selection and the survey's `input_type` into `enqueue_run(survey, selection=session.selected_options)` on post-finish
- [X] T018 [P] [US1] Selection ingest integration test in `backend/tests/integration/test_api_ingest_selection.py`: initiate with `["hillshade"]` → effective includes `elevation`; deselect `point_cloud_3d` → COPC never produced and absent from artifacts; deselect-all-optional → required-only run (quickstart Scenarios 2–3)
- [X] T019 [US1] Artifacts endpoint in `backend/apps/surveys/views_surveys.py`: replace latest-full-run logic with per-option resolution (T011) returning the `products` map per contracts/rest-api.md; 409 `not_ready` only when no option ever completed
- [X] T020 [US1] Frontend API client in `frontend/src/api/client.ts`: `getProcessingOptions(inputType)`, `selected_options` on `initiateUpload` (+ `effective_options` in response type), survey detail types with `input_type`/`options[]`, new `products`-keyed artifacts type
- [X] T021 [P] [US1] `OptionPicker` component in `frontend/src/components/OptionPicker.tsx`: checklist from catalog; required checked+disabled; defaults pre-checked; checking a dependent auto-checks prerequisites, unchecking a prerequisite unchecks dependents (visible cascade, FR-006); labels/descriptions/target-view badge via i18n keys
- [X] T022 [US1] Integrate selection into `frontend/src/components/UploadWidget.tsx`: fetch catalog on mount, render OptionPicker, send `selected_options` on initiation (selection confirmed at upload start per clarification Q4)
- [X] T023 [US1] Per-option progress in `frontend/src/components/SurveyStatus.tsx` (+ `frontend/src/stores/surveys.ts` types): render each run's options with state badges (pending/running/completed/failed/skipped/reused) and translated failure message for the failing option (FR-010, SC-006)
- [X] T024 [US1] Product-driven viewer gating in `frontend/src/pages/ProjectDetailPage.tsx`, `frontend/src/viewers/Map2D.tsx`, `frontend/src/viewers/Cloud3D.tsx`: consume the `products` map — add 2D layers only for present products, enable the 3D tab only when `point_cloud_3d` resolves (FR-005/FR-016)
- [X] T025 [P] [US1] Frontend tests in `frontend/tests/option-picker.test.tsx` (required locked, dependency cascade both directions, defaults) and `frontend/tests/survey-status.test.tsx` (per-option states render, failed option shows translated message)

**Checkpoint**: US1 fully functional — quickstart Scenarios 1–5 pass

---

## Phase 4: User Story 2 - Add a new option without disturbing the platform (Priority: P2)

**Goal**: Prove (and keep proving in CI) that a new option is a pure registration:
declaration + producer + i18n keys, zero orchestration/UI plumbing changes

**Independent Test**: Register a minimal test option end to end; it becomes
selectable, runs, publishes an attributed artifact — while existing options and
completed surveys behave exactly as before (quickstart Scenario 7)

- [X] T026 [P] [US2] Dummy-option e2e test in `backend/tests/integration/test_dummy_option_e2e.py`: fixture registers a `test_flag` option (map2d, trivial producer writing a tiny file) in the registry for the test; assert it appears in the catalog endpoint, is selectable at initiation, executes in a run, publishes a `DerivedArtifact` with `option_id="test_flag"`, and resolves in `/artifacts` products — importing but never modifying tasks/serializers/views (SC-003). Also register a dummy `InputTypeSpec` (`test_input`, own prep steps, its own option subset) and assert: catalog filtered by `input_type=test_input` returns only its options, `effective_selection` validates against it, and no orchestration/view code needed changes (FR-013 extensibility proof)
- [X] T027 [P] [US2] Deactivation test in `backend/tests/integration/test_option_deactivation.py`: inactive option absent from catalog and rejected on new initiation (`invalid_options`), historical artifacts still served, retry of a run containing the now-inactive option still allowed (FR-008 + edge case)
- [X] T028 [US2] Developer guide `backend/pipeline/README.md`: how to add an option (OptionSpec declaration, producer contract incl. multi-option producers for future NodeODM routes, i18n keys es/en, required tests), how to add an input type (InputTypeSpec + prep steps), pointing at the dummy-option test as the template

**Checkpoint**: US2 verified — adding options is registration-only, enforced by CI

---

## Phase 5: User Story 3 - Process additional options on an existing survey (Priority: P3)

**Goal**: Request more products on an already-processed survey reusing the stored
source file (no re-upload), as a new versioned run

**Independent Test**: On a completed survey, request one additional option; a new
run generates only that product, previous artifacts untouched, zero re-upload
(quickstart Scenario 4/5 mechanics)

- [X] T029 [US3] Contract addition in `specs/004-processing-options/contracts/rest-api.md`: `POST /surveys/{surveyId}/process` accepting `selected_options` → 202 `{"run": …}`; 409 `not_processable` while a run is queued/running; validation identical to upload initiation (closure, `invalid_options`)
- [X] T030 [US3] Endpoint in `backend/apps/surveys/views_surveys.py` + route in `backend/apps/surveys/urls.py`: validate selection against the survey's `input_type`, call `enqueue_run(survey, selection)`; options already completed in prior runs are created as `reused` (T009 mechanics — no re-execution)
- [X] T031 [P] [US3] Integration test in `backend/tests/integration/test_additional_options.py`: completed survey + request `point_cloud_3d` only → new run executes only that option (`reused` for the rest), previous artifacts unchanged, `/artifacts` resolves the union per FR-016, no upload session involved (SC-005)
- [X] T032 [US3] Frontend: "process more options" action on the survey detail in `frontend/src/components/SurveyStatus.tsx` (or a small `ProcessMoreDialog` in `frontend/src/components/`) reusing `OptionPicker` (already-produced options shown as such), calling a new `processSurvey(surveyId, selectedOptions)` in `frontend/src/api/client.ts`; i18n keys es/en in `frontend/src/i18n/*/common.json`

**Checkpoint**: All user stories independently functional

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T033 [P] Cleanup in `backend/pipeline/stages/surfaces.py` and `backend/apps/surveys/`: remove any dead `generate_surfaces`-era code paths and stale `stage` handling superseded by per-option progress; keep historical `surface_generation` value readable. Promote `DerivedArtifact.option_id` to NOT NULL via a follow-up migration in `backend/apps/surveys/migrations/` (safe: T007 backfilled every row) so attribution (FR-005) is enforced by the database, not just by code
- [X] T034 [P] Update `specs/004-processing-options/checklists/requirements.md` notes (resolved atomicity note) and verify SC-001…SC-006 against the implementation
- [X] T035 Run full quickstart validation (`specs/004-processing-options/quickstart.md` Scenarios 1–7) including one real-LAZ ingest against the compose stack (constitution dev-flow rule); record results in the spec directory as done for 001 (validation notes)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — T001 first; T002/T003 parallel after T001
- **Foundational (Phase 2)**: Depends on Phase 1. Internal order: T004 → T005; T006 → T007 → T008; T009 depends on T005 + T006; T010 depends on T006; T011 depends on T006; T012/T013 depend on T009
- **US1 (Phase 3)**: Depends on Phase 2. T014/T015 parallel; T016 → T017 → T018; T019 depends on T011; T020 depends on T014/T016/T019 shapes; T021 parallel with backend tasks; T022 depends on T020+T021; T023/T024 depend on T020; T025 depends on T021/T023
- **US2 (Phase 4)**: Depends on Phase 2 (+ T014/T016 for catalog/initiation assertions). Independent of US1's frontend work
- **US3 (Phase 5)**: Depends on Phase 2 and reuses US1's T011/T019/T020/T021
- **Polish (Phase 6)**: After desired stories complete

### User Story Dependencies

- **US1 (P1)**: Foundational only — delivers the MVP
- **US2 (P2)**: Foundational + US1's catalog/initiation endpoints (T014, T016) for its assertions; no frontend dependency
- **US3 (P3)**: Foundational + US1 components (OptionPicker, resolution endpoint)

### Parallel Opportunities

- After T001: T002 ∥ T003
- Phase 2: (T004→T005) ∥ (T006→T007→T008); then T009; then T010 ∥ T011 ∥ T012 ∥ T013
- Phase 3 backend (T014–T019) ∥ frontend component work (T021); T015 ∥ T018 ∥ T025
- Phase 4: T026 ∥ T027
- Phases 4 and 5 can proceed in parallel by different developers once US1 lands

## Parallel Example: User Story 1

```bash
# Backend and frontend tracks in parallel after Phase 2:
Task: "Catalog endpoint GET /processing-options in backend/apps/surveys/views_options.py"   # T014
Task: "OptionPicker component in frontend/src/components/OptionPicker.tsx"                   # T021

# Test tasks in parallel once their targets exist:
Task: "Catalog contract test in backend/tests/integration/test_api_options_catalog.py"      # T015
Task: "Selection ingest test in backend/tests/integration/test_api_ingest_selection.py"     # T018
Task: "Frontend tests in frontend/tests/option-picker.test.tsx"                              # T025
```

## Implementation Strategy

### MVP First (US1)

1. Phase 1 (registry) → Phase 2 (producers, schema+backfill, per-option orchestration) — this is the bulk of the work and where regressions live; T012/T013 gate it
2. Phase 3 (US1) → **STOP and VALIDATE** with quickstart Scenarios 1–5 + one real LAZ
3. Deploy/demo: default selection reproduces today's behavior exactly (safe rollout)

### Incremental Delivery

- US1 = MVP (selection + per-option pipeline + viewers)
- US2 adds the CI-enforced extensibility guarantee (cheap, high value)
- US3 adds reprocessing without re-upload (reuses US1 pieces)
- Each checkpoint leaves the platform fully working with prior behavior intact

## Notes

- Default selection == today's three products, so a run with no user interaction
  is byte-for-byte equivalent to the current pipeline output — use this for
  regression comparison during Phase 2
- The 001 artifacts-endpoint shape changes in T019/T020 within the same release
  (breaking change documented in contracts/rest-api.md; no external consumers)
