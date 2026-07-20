# Quickstart Validation Notes (T035)

**Date**: 2026-07-20 | **Stack**: `docker compose` (`db`, `redis`, `minio`, `tusd`,
`titiler`, `backend`, `worker`, `frontend`), rebuilt from this feature's code.
Backend/worker image: conda-forge `pdal` + `untwine` + `gdal` (real binaries,
not the local-dev fallback path).

All 7 scenarios from [`quickstart.md`](quickstart.md) pass. One of them
(Scenario 2/3 combined) was run as a genuine real-LAZ ingest through the
actual tus protocol against the running stack, per the constitution's
dev-flow rule; the rest are covered by automated integration tests that
exercise the real per-option orchestration code (`enqueue_run`/`run_option`/
`finalize_run`) with only I/O (S3, subprocess binaries) faked, plus one
additional manual API pass for the catalog/closure checks.

## Scenario 1 — Catalog served from the registry

**Status**: PASS (manual + `tests/integration/test_api_options_catalog.py`)

`GET /processing-options` returns exactly `elevation` (required),
`hillshade` (prereq `elevation`), `point_cloud_3d`, all `default_selected`,
i18n keys only — verified via `curl` against the running stack and by the
automated contract test.

## Scenario 2 — Selection at upload start; only selected products generated (US1)

**Status**: PASS — real-LAZ ingest through the actual tus protocol

Ran the full flow against the live stack (login → `POST
/projects/{id}/uploads` with `selected_options: ["hillshade"]` → real tus
`POST`+`PATCH` upload of a synthetic 9%-ramp LAZ → tusd `post-finish` hook →
real Celery worker → poll `GET /projects/{id}/surveys` to a terminal state):

- `effective_options` on initiation: `["elevation", "hillshade"]` (closure
  added the required option).
- Survey reached `status: "completed"`; the run's `options` were exactly
  `elevation` and `hillshade`, both `completed`; `point_cloud_3d` was absent
  (never selected, never produced).
- `GET /surveys/{id}/artifacts` returned a `products` map with exactly
  `elevation` and `hillshade` — real presigned MinIO URLs, real titiler
  `tilejson_url`/`statistics_url`.
- Fetched the DEM statistics URL from titiler directly: `mean ≈ 0.90` over
  the ramp fixture, matching the known-truth 9% grade (same check as
  `tests/unit/test_stage_surfaces.py`) — confirms the real PDAL binning
  pipeline, not just the orchestration around it, produced a correct DEM.

## Scenario 3 — Prerequisite closure (FR-006)

**Status**: PASS (manual + Scenario 2's own initiation + `test_api_ingest_selection.py`)

`selected_options: ["hillshade"]` closes to `{"elevation", "hillshade"}`
both via a standalone `curl` against `POST /projects/{id}/uploads` and as
part of the Scenario 2 real ingest above. `selected_options: ["nope"]` →
400 `invalid_options` (verified manually and in
`test_api_ingest_selection.py::test_invalid_option_id_rejected`).

## Scenario 4 — Per-option failure isolation & retry (FR-009, FR-004)

**Status**: PASS —
`tests/integration/test_per_option_publication.py` +
`tests/integration/test_api_status_retry.py`

Exercises the real `enqueue_run`/`run_option`/`finalize_run` code (only
storage I/O and the pdal/gdal producer calls are faked, via the shared
`fake_pipeline` test harness in `conftest.py`) rather than reproducing the
binary-renaming trick from `quickstart.md` by hand: a forced `point_cloud_3d`
failure leaves `elevation`/`hillshade` `completed` with their artifacts
published, the run `failed` with `point_cloud_3d`'s translated failure code,
and a subsequent retry creates a new run where the two completed options
become `reused` (not re-executed, timestamps from the original run) and only
`point_cloud_3d` re-runs.

## Scenario 5 — Latest-per-option resolution (FR-016)

**Status**: PASS — `tests/unit/test_artifact_resolution.py` +
`tests/integration/test_additional_options.py`

After a retry/US3-reprocess, `/artifacts` attributes `elevation`/`hillshade`
to the original producing run (via `reused_from`) and the newly-executed
option to the new run — verified directly against the resolution helper and
end-to-end through `POST /surveys/{id}/process`.

## Scenario 6 — Pre-existing surveys (FR-012, backfill)

**Status**: PASS — `tests/integration/test_options_backfill.py`

Uses Django's real `MigrationExecutor` to build rows against the schema as
it existed right after migration `0003` (i.e. genuinely nullable
`option_id`, no `RunOption` history — the real pre-004 shape), then advances
through `0004` (backfill) and `0005` (`option_id` NOT NULL, T033) and asserts
the standard three options show up `completed`/`failed`/`skipped` per the
original run outcome, with `UploadSession.selected_options` backfilled to the
standard set. `GET /surveys/{id}` continues to serve the backfilled data
correctly (`input_type`, per-option `options[]`).

## Scenario 7 — Extensibility end-to-end (US2, SC-003)

**Status**: PASS — `tests/integration/test_dummy_option_e2e.py`

```
docker compose exec backend pytest -k "dummy_option or options" -q
```
registers a throwaway `test_flag` option and a `test_input` input type
entirely within the test, and proves it becomes selectable, executes,
publishes an attributed artifact, and resolves in `/artifacts` — importing
but never modifying `tasks.py`/`serializers.py`/any `views_*.py`.

## Full suites (run inside the container against real Postgres/MinIO)

```
$ docker compose exec backend pytest -q
100 passed, 1 skipped in ~20s   (the 1 skip is test_real_laz_full_pipeline,
                                  which needs --laz-sample; separately
                                  exercised live for this validation, see
                                  Scenario 2 above)
```

Frontend (local, not containerized — no frontend test runner in the image):
```
$ npx tsc -b            # 0 errors
$ npx vitest run         # 31 passed (4 files)
```

**Done when** (quickstart.md): all scenarios pass and one real-LAZ ingest has
been run against the compose stack — both satisfied above.
