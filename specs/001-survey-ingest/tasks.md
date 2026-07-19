# Tasks: Survey Ingest

**Input**: Design documents from `/specs/001-survey-ingest/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/rest-api.md, quickstart.md

**Tests**: Included — the constitution mandates pytest coverage for pipeline stages
(synthetic known-truth fixtures) and validation against at least one real LAZ
sample for any ingest change.

**Organization**: Tasks grouped by user story (US1–US4 from spec.md) so each story
is independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 (upload→results), US2 (progress/failures), US3 (resumable), US4 (coexistence)

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Repository scaffolding, containers, and toolchain

- [x] T001 Create repository structure per plan.md: `backend/` (config, apps, pipeline, tests), `frontend/`, `infra/` directories with placeholder `__init__.py`/README stubs
- [x] T002 Initialize backend Python project in `backend/pyproject.toml` (Django 5, GeoDjango, DRF, Celery, redis, boto3, rasterio, pytest, pytest-django, ruff) and `backend/manage.py`
- [x] T003 [P] Initialize frontend in `frontend/package.json` with Vite + React 18 + TypeScript + Zustand + MapLibre GL + Uppy (tus) + i18n library, plus Vitest; scaffold `frontend/src/main.tsx` and `frontend/index.html`
- [x] T004 [P] Write `infra/backend.Dockerfile` (multi-arch base with GDAL/PDAL/untwine + Python deps) and `infra/frontend.Dockerfile` (Node build → static serve)
- [x] T005 Write `infra/docker-compose.yml` with services db (postgis), redis, minio (+ `infra/minio-init/` bucket bootstrap), tusd (S3 backend, 7-day expiry, hooks URL), titiler, backend, worker (celery), frontend (published at `localhost:8080`); single `docker compose up` must bring all up healthy
- [x] T006 [P] Configure lint/format: `backend/pyproject.toml` ruff config and `frontend/.eslintrc.cjs` + prettier

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Django/Celery/storage/auth/i18n groundwork every story needs

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T007 Create Django project config in `backend/config/`: `settings.py` (GeoDjango, DRF, PostGIS, env-based config, MinIO/S3 storage settings), `urls.py`, `wsgi.py`
- [x] T008 Configure Celery app in `backend/config/celery.py` (Redis broker, `acks_late`, task routing for pipeline queue) and wire into `backend/config/__init__.py`
- [x] T009 [P] Implement object-storage helpers in `backend/pipeline/storage.py`: key-scheme builders (`projects/{p}/surveys/{s}/source|runs/{r}/…` per research R9), presigned GET issuing, upload/download, SHA-256 streaming checksum
- [x] T010 [P] Implement uniform API error envelope + exception handler (`{error: {code, message_key, detail}}` per contracts) in `backend/apps/common/errors.py` and register in DRF settings
- [x] T011 Create accounts app in `backend/apps/accounts/`: session-auth endpoints `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/me` (serializers, views, urls) and `createuser` management command in `backend/apps/accounts/management/commands/createuser.py`
- [x] T012 [P] Create `CrsCatalogEntry` model + migration + seed fixture (WGS84/UTM Chile zones + SIRGAS-Chile realizations, EPSG codes verified against the image's PROJ db) in `backend/apps/projects/models.py` and `backend/apps/projects/fixtures/crs_catalog.json`, with `GET /api/v1/crs-catalog` endpoint
- [x] T013 [P] Scaffold frontend foundations: typed API client with CSRF + error-envelope handling in `frontend/src/api/client.ts`, session store in `frontend/src/stores/session.ts`, i18n setup with `es` (primary) and `en` catalogs in `frontend/src/i18n/`, router + login page in `frontend/src/pages/LoginPage.tsx`
- [x] T014 Configure pytest in `backend/tests/conftest.py` (pytest-django, MinIO/moto strategy, `real_laz` marker) and create synthetic fixture generator script producing tiny LAS/LAZ files (valid, truncated, no-CRS variants) plus a small E57 file as unsupported-format fixture in `backend/tests/fixtures/make_fixtures.py`

**Checkpoint**: Compose stack boots, login works, CRS catalog served — user story implementation can begin

---

## Phase 3: User Story 1 — Upload a survey and get analysis-ready results (Priority: P1) 🎯 MVP

**Goal**: Create project → resumable upload → async pipeline → DEM COG + COPC + hillshade visible in 2D/3D

**Independent Test**: Upload a real LAZ to a fresh project; after processing, the elevation surface, 3D view, and hillshade layer are all available with zero manual steps (quickstart Scenario 1)

### Tests for User Story 1

> Write first; they must fail before implementation

- [x] T015 [P] [US1] Unit tests for validation stage (valid georeferenced LAS/LAZ pass; E57 rejected as unsupported; size/extension re-check) in `backend/tests/unit/test_stage_validate.py`
- [x] T016 [P] [US1] Unit tests for reprojection stage (synthetic cloud in EPSG:A → project CRS B; coordinates land where expected) in `backend/tests/unit/test_stage_reproject.py`
- [x] T017 [P] [US1] Unit tests for surface stage (known-truth ramp fixture → DEM COG at 0.20 m with expected elevations; hillshade + COPC produced; artifacts checksummed) in `backend/tests/unit/test_stage_surfaces.py`
- [x] T018 [P] [US1] API contract tests for projects + uploads initiation + tusd hook + artifacts endpoints in `backend/tests/integration/test_api_ingest.py`
- [x] T019 [P] [US1] Real-LAZ end-to-end test (`real_laz` marker): upload → chain → three artifacts exist, CRS = project CRS in `backend/tests/integration/test_real_laz_ingest.py`

### Implementation for User Story 1

- [x] T020 [P] [US1] Create `Project` model + migration + `GET/POST /api/v1/projects` (name uniqueness, immutable CRS FK) in `backend/apps/projects/` (models, serializers, views, urls)
- [x] T021 [P] [US1] Create `Survey`, `ProcessingRun`, `DerivedArtifact`, `UploadSession` models + migrations with state enums and unique constraints per data-model.md in `backend/apps/surveys/models.py`
- [x] T022 [US1] Implement upload initiation `POST /api/v1/projects/{id}/uploads` (50 GB / extension / capture-date fast reject per FR-002, creates UploadSession, returns tus endpoint + metadata) in `backend/apps/surveys/views_uploads.py`
- [x] T023 [US1] Implement tusd completion hook `POST /api/v1/hooks/tusd` (shared-secret check, record tusd object key, create Survey `queued`, enqueue run #1 — no file operations in the request path, per constitution Principle III) in `backend/apps/surveys/views_hooks.py`
- [x] T024 [P] [US1] Implement validation stage (readability, LAS/LAZ content-format check, CRS presence in header VLRs, SHA-256 of source) in `backend/pipeline/stages/validate.py`
- [x] T025 [P] [US1] Implement reprojection stage (PDAL `filters.reprojection` stream mode to project CRS) in `backend/pipeline/stages/reproject.py`
- [x] T026 [US1] Implement surface-generation stage (PDAL stream → DEM GTiff 0.20 m → COG with overviews; `gdaldem` hillshade → COG; untwine → COPC; returns artifact descriptors with checksums) in `backend/pipeline/stages/surfaces.py`
- [x] T027 [US1] Implement Celery chain + stage-transition persistence (`relocate_source` → `run_validation` → `run_reprojection` → `run_surfaces`; the first step moves the uploaded object from the tusd staging prefix to the canonical `source/` key via async multipart server-side copy; ProcessingRun stage/state updates; DerivedArtifact rows only on fully materialized outputs) in `backend/apps/surveys/tasks.py`
- [x] T028 [US1] Implement `GET /api/v1/projects/{id}/surveys`, `GET /api/v1/surveys/{id}`, `GET /api/v1/surveys/{id}/artifacts` (presigned URLs + titiler tile template per contracts) in `backend/apps/surveys/views_surveys.py` + serializers
- [x] T029 [P] [US1] Build projects UI: list + create dialog (name + CRS from catalog) in `frontend/src/pages/ProjectsPage.tsx` and `frontend/src/stores/projects.ts`
- [x] T030 [P] [US1] Build upload widget (Uppy + tus plugin wired to initiation endpoint; capture-date + name fields) in `frontend/src/components/UploadWidget.tsx` and `frontend/src/stores/uploads.ts`
- [x] T031 [US1] Build project detail page with survey list (name, capture date, size, status) in `frontend/src/pages/ProjectDetailPage.tsx` and `frontend/src/stores/surveys.ts`
- [x] T032 [P] [US1] Build 2D viewer: MapLibre map consuming hillshade titiler tiles from ArtifactSet in `frontend/src/viewers/Map2D.tsx`
- [x] T033 [P] [US1] Build 3D viewer: Potree loading COPC via presigned URL (progressive LOD; auto-refresh of expired presigned URLs by re-fetching the ArtifactSet, for long viewing sessions) in `frontend/src/viewers/Cloud3D.tsx`

**Checkpoint**: MVP — quickstart Scenario 1 passes end-to-end

---

## Phase 4: User Story 2 — Follow progress and understand failures (Priority: P2)

**Goal**: Per-stage progress visible across sessions; failures show plain-language cause + corrective action; retry without re-upload

**Independent Test**: Quickstart Scenarios 2–3 (close browser mid-processing → stage visible on return; four bad-file fixtures → four distinct messages; retry creates run #2)

### Tests for User Story 2

- [x] T034 [P] [US2] Unit tests for failure classification (zip-as-las and E57 → `unsupported_format`; truncated → `unreadable_file`; no CRS → `missing_crs`) in `backend/tests/unit/test_failure_codes.py`
- [x] T035 [P] [US2] Integration tests for status polling shape and `POST /surveys/{id}/retry` (409 on non-failed; new run number; old runs untouched) in `backend/tests/integration/test_api_status_retry.py`

### Implementation for User Story 2

- [x] T036 [US2] Harden task error handling: map stage exceptions to `failure_code`/`failure_message_key`, mark run + survey `failed`, never emit partial DerivedArtifact rows in `backend/apps/surveys/tasks.py`
- [x] T037 [US2] Implement `POST /api/v1/surveys/{id}/retry` (only from `failed`, creates run n+1 reusing `source_key`, re-enqueues chain) in `backend/apps/surveys/views_surveys.py`
- [x] T038 [P] [US2] Add es/en message catalogs for all failure keys (cause + corrective action, Chilean mining terminology, no jargon) in `frontend/src/i18n/es/errors.json` and `frontend/src/i18n/en/errors.json`
- [x] T039 [US2] Build status UI: stage indicator (validación → reproyección → generación de superficies), terminal badges, failure panel with localized message + retry button, 3–5 s polling that stops on terminal states in `frontend/src/components/SurveyStatus.tsx`

**Checkpoint**: Scenarios 2–3 pass; US1 unaffected

---

## Phase 5: User Story 3 — Resume an interrupted upload (Priority: P2)

**Goal**: Interrupted transfers resume from last confirmed offset, surviving browser/machine restarts; abandoned uploads expire at 7 days

**Independent Test**: Quickstart Scenario 4 (kill network at ≳ 50%, resume, < 1% re-sent, survey processes fine)

### Tests for User Story 3

- [x] T040 [P] [US3] Integration tests for pending-uploads listing and expiry purge (active listed; expired absent and UploadSession → `expired`; no Survey created; two concurrent active sessions on one project yield two independent surveys) in `backend/tests/integration/test_api_uploads_resume.py`

### Implementation for User Story 3

- [x] T041 [US3] Implement `GET /api/v1/projects/{id}/uploads` (active sessions with progress hint queried from tusd/object store) in `backend/apps/surveys/views_uploads.py`
- [x] T042 [P] [US3] Implement periodic purge task (Celery beat) marking expired UploadSessions and cleaning tusd leftovers past 7 days in `backend/apps/surveys/tasks_maintenance.py`; verify tusd expiry config in `infra/docker-compose.yml`
- [x] T043 [US3] Frontend resumption flow: persist tus upload URLs (Uppy resumability across restarts), re-offer pending uploads on project open with resume/discard actions in `frontend/src/components/PendingUploads.tsx` and `frontend/src/stores/uploads.ts`

**Checkpoint**: Scenario 4 passes; interrupted uploads recoverable, stale ones vanish

---

## Phase 6: User Story 4 — Successive surveys coexist (Priority: P3)

**Goal**: Multiple dated surveys per project, chronologically listed, mutually untouchable

**Independent Test**: Quickstart Scenario 5 (second upload leaves first survey's artifact checksums byte-identical)

### Tests for User Story 4

- [x] T044 [P] [US4] Integration test: two surveys in one project → independent runs/artifacts; first survey's sha256 set unchanged after second completes; list ordered by capture_date in `backend/tests/integration/test_coexistence.py`

### Implementation for User Story 4

- [x] T045 [US4] Enforce chronological ordering + survey-count in ProjectSummary, and verify run-scoped key prefixes make cross-survey writes impossible (assertion in storage helpers) in `backend/apps/surveys/views_surveys.py` and `backend/pipeline/storage.py`
- [x] T046 [P] [US4] Frontend: capture-date-ordered survey list with per-survey status/date/size columns and empty-state in `frontend/src/pages/ProjectDetailPage.tsx`

**Checkpoint**: All four stories independently functional

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T047 [P] Verify multi-arch builds (`docker buildx build --platform linux/arm64,linux/amd64`) for both Dockerfiles in `infra/`
- [x] T048 [P] i18n sweep: no hardcoded user-visible strings outside `frontend/src/i18n/`; Spanish default locale verified
- [x] T049 [P] Structured logging for pipeline stages (run_id, survey_id, stage, duration) in `backend/pipeline/` and `backend/apps/surveys/tasks.py`
- [ ] T050 Performance validation: 10 GB LAZ ≤ 60 min (SC-005) and 3D first-render < 5 s (SC-006); tune PDAL stream chunk size / untwine parallelism if missed
- [x] T051 [P] Update `README.md` with quickstart pointer and dev setup for this feature
- [ ] T052 Run full quickstart.md validation (Scenarios 1–5 + automated checks) and record results in `specs/001-survey-ingest/quickstart.md` notes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** → **Foundational (Phase 2)** → user stories
- **US1 (Phase 3)**: only depends on Phase 2 — the MVP
- **US2 (Phase 4)**: depends on US1's models/tasks/endpoints (T021, T027, T028)
- **US3 (Phase 5)**: depends on US1's upload flow (T022, T023, T030); independent of US2
- **US4 (Phase 6)**: depends on US1 completed; independent of US2/US3
- **Polish (Phase 7)**: after desired stories complete

### Within Each User Story

- Tests first (must fail) → models → pipeline stages/services → endpoints → frontend
- T021 blocks T022–T028; T024–T026 block T027; T027–T028 block T032–T033

### Parallel Opportunities

- Phase 1: T003, T004, T006 in parallel after T001–T002
- Phase 2: T009, T010, T012, T013 in parallel after T007–T008
- US1 tests T015–T019 all parallel; stages T024/T025 parallel; frontend T029/T030/T032/T033 parallel
- After US1: US2, US3, US4 can proceed in parallel (different files)

## Parallel Example: User Story 1

```bash
# All US1 tests together:
Task: "Unit tests validation stage in backend/tests/unit/test_stage_validate.py"
Task: "Unit tests reprojection stage in backend/tests/unit/test_stage_reproject.py"
Task: "Unit tests surfaces stage in backend/tests/unit/test_stage_surfaces.py"
Task: "API contract tests in backend/tests/integration/test_api_ingest.py"

# Then models/stages in parallel:
Task: "Project model + API in backend/apps/projects/"
Task: "Survey/Run/Artifact/UploadSession models in backend/apps/surveys/models.py"
Task: "Validation stage in backend/pipeline/stages/validate.py"
Task: "Reprojection stage in backend/pipeline/stages/reproject.py"
```

## Implementation Strategy

**MVP first**: Phases 1–3 (T001–T033) deliver the demonstrable product — "upload
your flight, see your site in 2D and 3D". Stop, run quickstart Scenario 1, demo.

**Incremental delivery**: then US2 (observability/failures) → US3 (resumability)
→ US4 (coexistence guarantees), validating each with its quickstart scenario
before moving on. Each story leaves previous ones green.
