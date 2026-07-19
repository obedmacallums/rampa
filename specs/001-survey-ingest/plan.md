# Implementation Plan: Survey Ingest

**Branch**: `main` (no feature branch; git extension not installed) | **Date**: 2026-07-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-survey-ingest/spec.md`

## Summary

First feature of the platform: authenticated users create projects (name + working
CRS), upload georeferenced point clouds (LAS/LAZ, ≤ 50 GB) via resumable transfer, and an
asynchronous, observable pipeline (validation → reprojection → surface generation)
produces immutable, versioned derived artifacts per survey: DEM COG (analysis-ready
elevation surface), COPC (progressive 3D view), and hillshade COG (2D map layer).
Surveys coexist immutably with capture dates. Technical approach: Django/GeoDjango
backend with Celery workers running PDAL/GDAL stages against S3-compatible object
storage (MinIO in dev); tus protocol (tusd) for resumable uploads; titiler for map
tiles; React SPA with MapLibre (2D) and Potree (3D) reading COG/COPC directly via
HTTP range requests. Everything runs with a single `docker compose up`.

## Technical Context

**Language/Version**: Python 3.12 (backend/workers), TypeScript 5.x + Node 22 (frontend build)

**Primary Dependencies**: Django 5 + GeoDjango + DRF, Celery 5 + Redis, PDAL (+ untwine), GDAL/rasterio, boto3; React 18 + Vite + Zustand + MapLibre GL + Potree; tusd (resumable uploads); titiler (COG tiles); MinIO (dev object storage)

**Storage**: PostGIS 16/3.4 (metadata, geometries, statuses only) + S3-compatible object storage (all files; MinIO in dev). Files never in the database.

**Testing**: pytest + pytest-django (backend, pipeline stages against small synthetic LAZ fixtures); Vitest + React Testing Library (frontend); one real-LAZ end-to-end ingest test per constitution

**Target Platform**: Linux server containers (linux/arm64 + linux/amd64 via buildx); modern browsers for the SPA

**Project Type**: Web application (backend + frontend + worker + auxiliary services via docker compose)

**Performance Goals**: 10 GB cloud fully processed ≤ 60 min after upload completes (SC-005); 3D view interactive < 5 s (SC-006); survey status visible < 5 s on project open (SC-004); resume overhead < 1% re-sent (SC-002)

**Constraints**: No pipeline stage may assume the full cloud fits in RAM (tiled/streaming processing); derived artifacts immutable and versioned per processing run; all user-visible text through i18n (es primary, en secondary); single `docker compose up` demo; no cloud dependencies

**Scale/Scope**: Single-site deployments; files ≤ 50 GB; a few concurrent uploads/processing runs; ~10s of surveys per project; 2 apps (backend, frontend) + pipeline package + compose infra

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Analysis on rasters, viz on tiles | Ingest is precisely where cloud → DEM COG happens; raw cloud used only to build COPC for viewing. No feature consumes raw points at analysis time. | PASS |
| II. Thin backend, interactive frontend | Backend does pipelines, persistence, auth, artifact serving. Viewers read COG/COPC client-side via range requests. Status via lightweight polling of persisted state (metadata, not analysis). | PASS |
| III. Async ingest, always | Core of this feature: Celery pipeline, tus resumable uploads to object storage, per-stage observable statuses, immutable versioned artifacts (reprocess = new run). | PASS |
| IV. Station-based evaluation | No evaluation in this feature; data model leaves `Surface`-per-survey ready for downstream alignment/station features. | N/A |
| V. Assisted detection, human authority | No automatic detection outputs in this feature. | N/A |
| VI. Evaluation profiles as data | No thresholds involved. | N/A |
| VII. Reproducible reports | No reports; artifact immutability + checksums lay groundwork. | N/A |
| VIII. Test-first analysis core | No analysis engine here; pipeline stages get pytest coverage with synthetic known-truth LAZ fixtures, and ingest changes validate against ≥ 1 real LAZ sample (constitution dev-flow rule). | PASS |
| IX. Bilingual by design | SPA ships with i18n layer from day one (es primary with Chilean mining terminology, en secondary); no hardcoded user-visible strings. | PASS |
| X. Mining focus, neutral core | Entities generic: `Project`, `Survey`, `ProcessingRun`, `DerivedArtifact` (kind `dem`/`copc`/`hillshade` maps to constitutional `Surface` concept). No DS 132 knowledge in code. | PASS |
| XI. AI as isolated service | No AI components. | N/A |
| Tech constraints | Mandated stack used as-is; files only in object storage; multi-arch images; CRS reprojection at ingest (project-declared working CRS); memory budgets via tiled stages; single `docker compose up`. | PASS |

**Initial gate result: PASS (no violations, Complexity Tracking empty).**

**Post-Phase-1 re-check**: design artifacts (data model, contracts, quickstart)
introduce no deviation — entities stay generic, no file bytes touch PostGIS, all
interactive viewing is client-side, statuses are polled persisted metadata. **PASS.**

## Project Structure

### Documentation (this feature)

```text
specs/001-survey-ingest/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── rest-api.md      # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── pyproject.toml
├── manage.py
├── config/                  # Django project: settings, urls, celery app
├── apps/
│   ├── accounts/            # session auth endpoints (login/logout/me)
│   ├── projects/            # Project model + API (create/list), CRS catalog
│   └── surveys/             # Survey, ProcessingRun, DerivedArtifact models + API,
│                            #   tusd hook endpoint, status serialization
├── pipeline/                # framework-light ingest stages (validate, reproject,
│   │                        #   surfaces) callable from Celery tasks
│   ├── stages/
│   └── storage.py           # object-storage layout helpers (boto3)
└── tests/
    ├── unit/                # stage tests on synthetic LAZ fixtures
    ├── integration/         # API + pipeline integration (real small LAZ)
    └── fixtures/            # tiny synthetic LAS/LAZ/E57 files (committed)

frontend/
├── package.json
├── src/
│   ├── api/                 # typed client for contracts/rest-api.md
│   ├── components/          # upload widget, survey list, status badges
│   ├── pages/               # login, projects, project detail, viewer 2D/3D
│   ├── stores/              # Zustand: session, projects, uploads, surveys
│   ├── i18n/                # es (primary) / en catalogs
│   └── viewers/             # MapLibre map (hillshade via titiler), Potree COPC
└── tests/

infra/
├── docker-compose.yml       # db(postgis), redis, minio, tusd, titiler,
│                            #   backend, worker, frontend
├── backend.Dockerfile       # multi-arch (arm64+amd64), PDAL/GDAL/untwine included
├── frontend.Dockerfile
└── minio-init/              # bucket bootstrap
```

**Structure Decision**: Web application layout (`backend/` + `frontend/` +
`infra/`). The ingest pipeline lives in `backend/pipeline/` as a framework-light
package imported by Celery tasks — mirroring the constitution's future
analysis-library separation without prematurely creating a standalone package.
tusd and titiler run as stock containers (no custom code), consistent with the
isolated-service pattern.

## Complexity Tracking

No constitution violations — table intentionally empty.
