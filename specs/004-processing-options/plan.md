# Implementation Plan: Selectable & Extensible Processing Options

**Branch**: `main` (no feature branch; git extension not installed) | **Date**: 2026-07-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-processing-options/spec.md`

## Summary

Replace the fixed ingest chain (validate → reproject → surfaces, always producing
DEM + hillshade + COPC) with a **registry of processing options**: each option is a
code-declared catalog entry (id, i18n keys, applicable input types, target view,
required/default/active flags, prerequisites, producer routine). At upload start the
user selects options (required ones locked); the selection travels with the upload
session, and on upload completion a run executes the mandatory preparation steps
followed by the selected options in dependency order. Publication becomes
per-option (each option's artifacts publish when it completes; a failing option
fails the run but keeps completed products), retry re-executes only incomplete
options, and viewers resolve the latest completed version of each product across
runs. Input type is modeled explicitly (`point_cloud` today) so photogrammetry and
mesh inputs later register alongside without rework. Technical approach: a Python
option registry in `backend/pipeline/`, new `RunOption` rows for per-option
selection/progress, `option_id` attribution on `DerivedArtifact`, a dynamically
built Celery chain, a catalog endpoint, and an upload widget with an options
checklist.

## Technical Context

**Language/Version**: Python 3.12 (backend/workers), TypeScript 5.x + Node 22 (frontend)

**Primary Dependencies**: Django 5 + DRF, Celery 5 + Redis, PDAL (+ untwine), GDAL, boto3; React 18 + Vite + Zustand + react-i18next; tusd (resumable uploads); titiler (COG tiles); MinIO (dev object storage) — unchanged from 001; no new dependencies

**Storage**: PostGIS (metadata: runs, per-option states, artifact attribution) + S3-compatible object storage (all files). Catalog of options lives in code (registry), not in the database (see research R1)

**Testing**: pytest + pytest-django (registry validation, dynamic chain building, per-option publication, backfill migration, dummy-option end-to-end per US2); Vitest + RTL (options checklist, per-option status); ≥ 1 real-LAZ ingest validation (constitution dev-flow rule)

**Target Platform**: Linux server containers (linux/arm64 + linux/amd64); modern browsers

**Project Type**: Web application (existing backend + frontend + worker + compose infra)

**Performance Goals**: Selection adds < 1 min to upload flow (SC-001); no regression of 001 targets (10 GB processed ≤ 60 min); catalog endpoint is trivial (serves in-memory registry)

**Constraints**: Per-option publication must never publish a half-materialized option (checksummed, fully uploaded artifacts only); no pipeline stage assumes cloud fits in RAM; all user-visible option names/descriptions via i18n keys (es/en); existing surveys must remain consistent (backfill, FR-012); single `docker compose up` unchanged

**Scale/Scope**: 3 initial options (elevation surface, terrain shading, 3D point cloud), 1 input type (`point_cloud`); design validated for ~10s of options and 3 input types without schema change

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Analysis on rasters, viz on tiles | Strengthened: elevation surface (DEM COG) is a **required** option — every survey stays analysis-ready. No feature reads raw points at analysis time. | PASS |
| II. Thin backend, interactive frontend | Catalog endpoint serves static registry metadata; viewers keep reading COG/COPC client-side; per-option status is polled persisted metadata. | PASS |
| III. Async ingest, always | Chain stays Celery + tus + observable per-stage/per-option states. Artifacts remain immutable outputs of versioned runs; atomicity moves from run to option (clarification 2026-07-19) — an option's artifacts are still all-or-nothing and never mutated; retry appends a new run. | PASS |
| IV. Station-based evaluation | Not touched. | N/A |
| V. Assisted detection, human authority | No detection outputs. | N/A |
| VI. Evaluation profiles as data | No thresholds. Option catalog is dev-registered code, not user data — consistent with "profiles as data" applying to normative knowledge, which options do not carry. | N/A |
| VII. Reproducible reports | Groundwork preserved: runs record exact selection; artifacts keep run + option attribution and checksums. | PASS |
| VIII. Test-first analysis core | No analysis engine; registry/orchestration get pytest coverage incl. a dummy-option end-to-end test (US2) and synthetic-LAZ stage tests as in 001. | PASS |
| IX. Bilingual by design | Options expose `label_key`/`description_key`; all new UI text through i18n catalogs (es primary, en secondary). | PASS |
| X. Mining focus, neutral core | New entities generic: `ProcessingOption` (registry), `RunOption`, `input_type`. No domain/normative knowledge in the registry. | PASS |
| XI. AI as isolated service | None involved; the input-type/production-route seam is exactly where future NodeODM (isolated service) plugs in, per constitution's photogrammetry constraint. | PASS |
| Tech constraints | Same stack; files only in object storage; CRS reprojection remains a mandatory prep step per input type; memory budgets unchanged; multi-arch images untouched. | PASS |

**Initial gate result: PASS (no violations, Complexity Tracking empty).**

**Post-Phase-1 re-check**: design artifacts introduce no deviation — the registry
is code (no normative data), per-option publication preserves artifact
immutability and checksums, entities stay generic, viewers stay client-side.
**PASS.**

## Project Structure

### Documentation (this feature)

```text
specs/004-processing-options/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── rest-api.md      # Phase 1 output (delta over 001 contracts)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── pipeline/
│   ├── options.py           # NEW: option + input-type registry (single source of truth)
│   ├── stages/
│   │   ├── validate.py      # unchanged (prep)
│   │   ├── reproject.py     # unchanged (prep)
│   │   └── surfaces.py      # SPLIT: per-option producers (dem, hillshade, copc)
│   └── storage.py           # unchanged helpers
├── apps/surveys/
│   ├── models.py            # Survey.input_type, ProcessingRun.input_type,
│   │                        #   NEW RunOption, DerivedArtifact.option_id
│   ├── migrations/          # schema + backfill (FR-012)
│   ├── tasks.py             # dynamic chain builder, per-option task wrapper,
│   │                        #   per-option publication, retry-incomplete logic
│   ├── serializers.py       # run options, input_type
│   ├── views_options.py     # NEW: GET catalog endpoint
│   ├── views_uploads.py     # selected_options validation on initiation
│   ├── views_surveys.py     # artifacts resolved latest-per-option (FR-016)
│   └── urls.py              # + /processing-options route
└── tests/
    ├── unit/                # registry validation, chain building, selection closure
    └── integration/         # per-option publication, retry, backfill, dummy option e2e

frontend/
├── src/
│   ├── api/client.ts        # catalog fetch, selected_options on initiate,
│   │                        #   new artifacts/response types
│   ├── components/
│   │   ├── UploadWidget.tsx     # options checklist (required locked, deps cascade)
│   │   ├── SurveyStatus.tsx     # per-option progress states
│   │   └── OptionPicker.tsx     # NEW: reusable selection list (upload + US3 later)
│   ├── i18n/                # option label/description keys (es/en)
│   └── viewers/             # layer/tab availability driven by present products
└── tests/
```

**Structure Decision**: Extend the 001 web-application layout in place. The
option registry lives in `backend/pipeline/options.py` next to the stages it
binds, keeping the pipeline package framework-light (importable without Django)
while `apps/surveys` consumes it for API/orchestration — same separation 001
established. No new services or packages.

## Complexity Tracking

No constitution violations — table intentionally empty.
