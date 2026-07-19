# Data Model: Survey Ingest

Entities are generic per Principle X (`Project`, `Survey`, `ProcessingRun`,
`DerivedArtifact`); no domain/normative knowledge lives here. PostGIS stores only
metadata, statuses, geometries, and object-storage references — never file bytes.

## User

Django's built-in `User` (no customization in this feature). Provisioned via
admin/management command; no roles (FR-015).

## CrsCatalogEntry

Curated list of working coordinate systems offered at project creation (R6).

| Field | Type | Notes |
|---|---|---|
| id | PK | |
| code | str, unique | authority code, e.g. `EPSG:xxxxx` |
| label_key | str | i18n key for the human-readable name |
| is_active | bool | allows retiring entries without deleting |

## Project

| Field | Type | Notes |
|---|---|---|
| id | UUID PK | |
| name | str (≤ 120), required | unique per deployment (case-insensitive) |
| crs | FK → CrsCatalogEntry, required | immutable after creation (FR-016) |
| created_by | FK → User | |
| created_at | datetime | |

Constraints: no update/delete endpoints in this feature. All authenticated users
see all projects.

## Survey

One uploaded flight. Immutable identity; processing state lives on runs, with a
denormalized `status` for cheap listing (FR-014).

| Field | Type | Notes |
|---|---|---|
| id | UUID PK | |
| project | FK → Project, required | |
| name | str (≤ 120), required | defaults to source filename (FR-005) |
| capture_date | date, required | user-provided (FR-005) |
| source_format | enum: `las` \| `laz` | from validated file |
| source_size_bytes | bigint | |
| source_key | str | object-storage key of the uploaded file — initially the tusd staging key, updated to the canonical `source/` key by the async relocation step (retained for retries, FR-012) |
| source_sha256 | str, nullable | computed during validation |
| status | enum, denormalized | mirrors latest run: `queued` \| `processing` \| `completed` \| `failed` — upload-in-progress is represented by `UploadSession.state = active`, never by a Survey row |
| created_by | FK → User | |
| created_at | datetime | |

Constraints: never overwritten by other surveys (FR-013); ordering by
`capture_date` (FR-014). Deletion out of scope.

### Survey status lifecycle

```
UploadSession(active) ──(tusd completion hook creates Survey)──▶ queued ──▶ processing ──▶ completed
        │                                                                      │
        └─(expired, 7 days: session reaped, no Survey ever created)            └──▶ failed ──(retry)──▶ queued
```

- A Survey row exists only after the upload completes; in-progress/interrupted
  uploads live as `UploadSession` (`active`, resumable). If never completed, tusd
  expiry (7 days) reaps the partial file and the session (FR-004) — an expired
  upload never appears as a survey in listings.
- Terminal states: `completed`, `failed` (retriable → new run, back to `queued`).

## ProcessingRun

One versioned execution of the pipeline over a survey (FR-011). Retries create new
runs; runs are append-only.

| Field | Type | Notes |
|---|---|---|
| id | UUID PK | doubles as object-storage run prefix |
| survey | FK → Survey, required | |
| number | int | 1..n per survey, unique together |
| stage | enum: `validation` \| `reprojection` \| `surface_generation` | current/last stage (FR-007) |
| state | enum: `queued` \| `running` \| `completed` \| `failed` | |
| failure_code | str, nullable | machine key, e.g. `unsupported_format`, `unreadable_file`, `missing_crs`, `internal_error` |
| failure_message_key | str, nullable | i18n key → plain-language message + corrective action (FR-008, SC-003) |
| started_at / finished_at | datetime, nullable | |

State transitions: `queued → running → completed | failed`. Stage advances only
forward within a run. A run never mutates another run's rows or artifacts.

## DerivedArtifact

Immutable product of a completed (or partially progressed) run. Rows are written
only when the artifact is fully materialized and checksummed — a failed run never
exposes partial artifacts as usable (edge case: mid-pipeline failure).

| Field | Type | Notes |
|---|---|---|
| id | UUID PK | |
| run | FK → ProcessingRun, required | traceability (Key Entities) |
| kind | enum: `dem` \| `hillshade` \| `copc` | the three outputs of FR-010 |
| storage_key | str | `projects/{p}/surveys/{s}/runs/{r}/...` (R9) |
| size_bytes | bigint | |
| sha256 | str | verifies SC-007 byte-identity |
| resolution_m | decimal, nullable | DEM/hillshade: 0.20 default |
| created_at | datetime | |

Constraint: unique (`run`, `kind`). A survey's "current" artifacts are those of its
latest `completed` run.

## UploadSession

Bridges tus uploads to surveys before completion.

| Field | Type | Notes |
|---|---|---|
| id | UUID PK | |
| tus_upload_id | str, unique | from tusd |
| project | FK → Project | |
| declared_filename | str | |
| declared_size_bytes | bigint | rejected at initiation if > 50 GB or bad extension (FR-002) |
| capture_date | date | collected at initiation, copied to Survey on completion |
| survey_name | str | |
| created_by | FK → User | |
| state | enum: `active` \| `completed` \| `expired` | |
| created_at / completed_at | datetime | |

## Relationships overview

```
User ──< Project ──< Survey ──< ProcessingRun ──< DerivedArtifact
                        ▲
UploadSession ──────────┘ (becomes exactly one Survey on tus completion)
Project ──▶ CrsCatalogEntry
```
