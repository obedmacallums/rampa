# REST API Contract — Processing Options (delta over 001 contracts)

**Base**: `/api/v1` — session auth, JSON, error shape `{"error": {"code", "message_key", "detail"}}` as in 001.

## GET /processing-options *(new)*

Query: `input_type` (optional, default `point_cloud`; unknown value → `invalid_input_type` 400).

Returns active options applicable to the input type, from the code registry.

```json
{
  "input_type": "point_cloud",
  "options": [
    {
      "id": "elevation",
      "label_key": "options.elevation.label",
      "description_key": "options.elevation.description",
      "target_view": "map2d",
      "required": true,
      "default_selected": true,
      "prerequisites": []
    },
    {
      "id": "hillshade",
      "label_key": "options.hillshade.label",
      "description_key": "options.hillshade.description",
      "target_view": "map2d",
      "required": false,
      "default_selected": true,
      "prerequisites": ["elevation"]
    },
    {
      "id": "point_cloud_3d",
      "label_key": "options.point_cloud_3d.label",
      "description_key": "options.point_cloud_3d.description",
      "target_view": "view3d",
      "required": false,
      "default_selected": true,
      "prerequisites": []
    }
  ]
}
```

## POST /projects/{projectId}/uploads *(modified)*

Request gains optional `selected_options: string[]` (option ids). Omitted →
default set. Server validates (exists ∧ active ∧ applicable) and completes
closure (required + prerequisites); the **effective** selection is stored and
echoed:

```json
// 201 — unchanged fields plus:
{ "effective_options": ["elevation", "hillshade", "point_cloud_3d"], "...": "..." }
```

Errors: `invalid_options` 400 (`detail.invalid` lists offending ids) — raised
for unknown, inactive, or inapplicable ids.

## POST /api/v1/hooks/tusd *(behavior change, same contract)*

`post-finish` copies the session's effective selection and the survey's
`input_type` onto the created run. No payload change.

## GET /surveys/{surveyId} *(modified)*

`runs[]` entries gain `input_type` and `options[]`; survey gains `input_type`.

```json
{
  "id": "…", "name": "…", "status": "failed", "input_type": "point_cloud",
  "runs": [
    {
      "id": "…", "number": 2, "stage": "reprojection", "state": "failed",
      "input_type": "point_cloud",
      "failure_code": null, "failure_message_key": null,
      "options": [
        { "option_id": "elevation", "state": "completed",
          "failure_code": null, "failure_message_key": null,
          "started_at": "…", "finished_at": "…" },
        { "option_id": "hillshade", "state": "skipped", "...": "..." },
        { "option_id": "point_cloud_3d", "state": "failed",
          "failure_code": "internal_error",
          "failure_message_key": "errors.internal_error", "...": "..." }
      ]
    }
  ]
}
```

Option states: `pending | running | completed | failed | skipped | reused`
(`reused` includes `reused_from_run_id`).

## POST /surveys/{surveyId}/retry *(same contract, new semantics)*

Still 202/`{"run": …}`; still 409 `not_retriable` unless survey `failed`.
The new run carries the previous effective selection; options completed in a
prior run are created as `reused` and not re-executed (FR-004/R5).

## POST /surveys/{surveyId}/process *(new, US3)*

Request more products on an already-processed survey, reusing the stored
source file — no re-upload. Same body/validation as upload initiation:

```json
// request
{ "selected_options": ["point_cloud_3d"] }
```

Validation is identical to upload initiation: every id must exist, be
active, and apply to the survey's `input_type`; the server completes the
closure (required + prerequisites) exactly as at upload time. Errors:
`invalid_options` 400 (`detail.invalid` lists offending ids).

```json
// 202
{ "run": { "id": "…", "number": 3, "stage": "validation", "state": "queued", "...": "..." } }
```

409 `not_processable` while the survey already has a run `queued` or
`running` (avoids overlapping runs against the same source). Options in the
effective selection that a prior run already completed are created as
`reused` on the new run and not re-executed (R5, same mechanics as retry);
only the newly requested (incomplete) options actually run.

## GET /surveys/{surveyId}/artifacts *(modified — resolved per option, FR-016)*

Was: latest fully-completed run or 409. Now: resolution per option across
runs (latest completed `RunOption`, following `reused_from`). 409 `not_ready`
only when **no** option has ever completed. Response is keyed by option id;
per-artifact payloads keep their 001 shapes (presigned URLs, titiler URLs,
sha256, sizes, `expires_in`):

```json
{
  "input_type": "point_cloud",
  "products": {
    "elevation":      { "run_id": "…", "kind": "dem",       "url": "…", "tilejson_url": "…", "statistics_url": "…", "sha256": "…", "size_bytes": 1, "resolution_m": "0.250", "expires_in": 3600 },
    "hillshade":      { "run_id": "…", "kind": "hillshade", "tile_url_template": "…", "tilejson_url": "…", "cog_url": "…", "sha256": "…", "expires_in": 3600 },
    "point_cloud_3d": { "run_id": "…", "kind": "copc",      "url": "…", "sha256": "…", "size_bytes": 1, "expires_in": 3600 }
  }
}
```

Options never selected/completed are absent from `products`; viewers enable
layers/tabs from presence (R7). **Breaking change** for the 001 shape
(`dem`/`copc`/`hillshade` top-level keys): the frontend client migrates in the
same release; no external consumers exist.

## Compatibility notes

- All new/changed responses expose i18n **keys** only (Principle IX).
- Existing surveys serve identical data after backfill (FR-012): their runs
  show the then-standard three options as `completed`/`failed`.
