# REST API Contract: Survey Ingest

Base path: `/api/v1`. All endpoints require session authentication (cookie +
CSRF) except `POST /auth/login`. Errors use a uniform envelope:

```json
{ "error": { "code": "machine_code", "message_key": "i18n.key", "detail": {} } }
```

`message_key` resolves to localized plain-language text in the frontend (es
primary, en secondary) — API responses never embed user-facing prose or stack
traces (FR-008, SC-003).

## Auth

| Method | Path | Body | 200 response | Errors |
|---|---|---|---|---|
| POST | `/auth/login` | `{username, password}` | `{user: {id, username}}` + session cookie | 401 `invalid_credentials` |
| POST | `/auth/logout` | — | `{}` | — |
| GET | `/auth/me` | — | `{user: {id, username}}` | 401 `not_authenticated` |

## Projects

| Method | Path | Body | Response | Errors |
|---|---|---|---|---|
| GET | `/crs-catalog` | — | `[{id, code, label_key}]` (active entries) | — |
| GET | `/projects` | — | `[ProjectSummary]` | — |
| POST | `/projects` | `{name, crs_id}` | 201 `Project` | 400 `name_taken` \| `invalid_crs` |

```json
ProjectSummary = { "id", "name", "crs": {"code", "label_key"}, "survey_count", "created_at" }
```

## Uploads (initiation + tus)

Upload flow: (1) initiate against the backend → receive tus endpoint + metadata;
(2) browser talks tus protocol directly to tusd (resumable, FR-003); (3) tusd
completion hook (server-to-server, `POST /hooks/tusd`, shared-secret header)
creates the `Survey` and enqueues run #1. The hook performs **no file
operations**: relocating the object to the canonical `source/` key happens
asynchronously as the first pipeline step (constitution Principle III — no sync
request touches a raw point cloud file).

| Method | Path | Body | Response | Errors |
|---|---|---|---|---|
| POST | `/projects/{project_id}/uploads` | `{filename, size_bytes, capture_date, name?}` | 201 `{upload_session_id, tus_endpoint, tus_metadata}` | 400 `file_too_large` (> 50 GB) \| `unsupported_extension` (not .las/.laz) \| `invalid_capture_date` (FR-002) |
| GET | `/projects/{project_id}/uploads` | — | `[{upload_session_id, declared_filename, state, received_bytes, declared_size_bytes}]` — lets the UI re-offer resumable uploads after restart (US3) | — |
| POST | `/hooks/tusd` | tusd hook payload | `{}` | 403 without shared secret |

Contract notes:
- Size/extension are enforced at initiation (fast reject) **and** re-verified at
  validation stage (content-based).
- Upload sessions expire server-side after 7 days (FR-004); expired sessions
  disappear from the list and never produce surveys.

## Surveys

| Method | Path | Body | Response | Errors |
|---|---|---|---|---|
| GET | `/projects/{project_id}/surveys` | — | `[SurveySummary]` ordered by `capture_date` (FR-014) | — |
| GET | `/surveys/{survey_id}` | — | `SurveyDetail` (poll target while non-terminal, R8) | 404 |
| POST | `/surveys/{survey_id}/retry` | — | 202 `{run: RunStatus}` — new run, no re-upload (FR-012) | 409 `not_retriable` (only `failed` surveys) |
| GET | `/surveys/{survey_id}/artifacts` | — | `ArtifactSet` for latest completed run | 409 `not_ready` |

```json
SurveySummary = { "id", "name", "capture_date", "source_format",
                  "source_size_bytes", "status", "current_stage" }

SurveyDetail  = SurveySummary + {
  "runs": [ RunStatus ],
  "latest_run": RunStatus
}

RunStatus = { "id", "number", "stage", "state",
              "failure_code", "failure_message_key",
              "started_at", "finished_at" }

ArtifactSet = {
  "run_id",
  "dem":       { "url", "sha256", "size_bytes", "resolution_m", "expires_at" },
  "copc":      { "url", "sha256", "size_bytes", "expires_at" },
  "hillshade": { "tile_url_template", "cog_url", "sha256", "expires_at" }
}
```

Contract notes:
- `dem.url` / `copc.url` are short-lived presigned object-storage URLs supporting
  HTTP range requests (R10); the frontend reads them directly (Principle II).
- `hillshade.tile_url_template` is a titiler XYZ template
  (`.../tiles/{z}/{x}/{y}.png?url=<cog>`).
- Artifacts are immutable: the same `run_id` always yields byte-identical content
  (SC-007); re-requesting only refreshes presigned URLs.

## Failure codes (validation stage → `failure_code` / `failure_message_key`)

| code | trigger | corrective action conveyed |
|---|---|---|
| `unsupported_format` | content not georeferenced LAS/LAZ (e.g. E57, ZIP) | list accepted formats |
| `unreadable_file` | corrupt/truncated | re-export or re-upload |
| `missing_crs` | no CRS metadata | export with CRS information |
| `internal_error` | any stage crash | retry available; contact operator |

## Polling guidance (non-normative)

While `status ∈ {queued, processing}`, poll `GET /surveys/{id}` every 3–5 s;
stop on terminal state. Satisfies SC-004 without push infrastructure.
