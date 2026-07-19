# Quickstart & Validation Guide: Survey Ingest

Runnable scenarios proving the feature end-to-end. References:
[spec.md](./spec.md) · [data-model.md](./data-model.md) ·
[contracts/rest-api.md](./contracts/rest-api.md)

## Prerequisites

- Docker + Docker Compose (Apple Silicon or x86_64 — images are multi-arch)
- A real LAZ sample (any drone survey export with CRS metadata); small synthetic
  fixtures live in `backend/tests/fixtures/`
- No cloud accounts of any kind (constitution: demo-first)

## Setup

```bash
docker compose -f infra/docker-compose.yml up -d
# Services expected healthy: db, redis, minio, tusd, titiler, backend, worker, frontend

# Create a user (no self-registration; FR-015)
docker compose -f infra/docker-compose.yml exec backend \
  python manage.py createuser demo --password demo1234
```

Open http://localhost:8080 (frontend). UI must render in Spanish by default
(Principle IX).

## Scenario 1 — Happy path (US1, SC-001, SC-005)

1. Log in as `demo`.
2. Create project "Rajo Norte", choosing a working CRS from the catalog list.
3. Upload the real LAZ sample, set a capture date, start. Time the flow: selecting
   file → upload started must take < 2 min with no technical steps (SC-001).
4. Watch the survey advance: `queued → processing` with stages
   `validation → reprojection → surface_generation`, then `completed`.
5. Verify all three artifacts exist and open:
   - 2D map shows the hillshade layer over the site (tiles from titiler).
   - 3D view renders the cloud, navigable, detail loads progressively; first
     points and responsive camera within 5 s (SC-006).
   - `GET /api/v1/surveys/{id}/artifacts` returns `dem`, `copc`, `hillshade`
     with sha256 + sizes.
6. For a ~10 GB input: `completed` within 60 min of upload completion (SC-005).

## Scenario 2 — Progress survives the browser (US2, SC-004)

1. Start processing a large file; close the browser mid-processing.
2. Reopen, log in, open the project: current stage or terminal status visible
   within 5 s (SC-004) — no session was kept alive.

## Scenario 3 — Comprehensible failures (US2, SC-003)

Upload each of the following and verify the survey ends `failed` with a distinct,
plain-language Spanish message stating cause + corrective action (no traces):

| File | Expected `failure_code` |
|---|---|
| a `.zip` renamed `.las` | `unsupported_format` |
| truncated LAZ (fixture) | `unreadable_file` |
| LAZ without CRS VLRs (fixture) | `missing_crs` |
| E57 file (fixture) | `unsupported_format` |

Then click retry on one of them after replacing nothing: a **new run** appears
(`number` incremented), no re-upload requested (FR-012).

## Scenario 4 — Resumable upload (US3, SC-002)

1. Start uploading a multi-GB file; at ≳ 50%, kill the network (or close the
   browser entirely).
2. Reopen the project → pending upload is offered for resumption
   (`GET /projects/{id}/uploads`).
3. Resume; verify via tusd/network logs that transfer continues from the last
   offset (< 1% re-sent, SC-002) and the completed survey processes successfully
   (integrity preserved).

## Scenario 5 — Coexistence & immutability (US4, SC-007)

1. With Scenario 1's survey `completed`, record its artifacts' `sha256` values.
2. Upload a second survey (different capture date) to the same project; wait for
   `completed`.
3. Both surveys listed side by side, ordered by capture date, each with its own
   status and artifacts (FR-013/FR-014).
4. Re-fetch the first survey's artifacts: identical `sha256` values (SC-007).

## Automated checks

```bash
# Backend: pipeline stages against synthetic known-truth fixtures + API tests
docker compose -f infra/docker-compose.yml exec backend pytest

# Real-LAZ integration test (constitution: every ingest change validates
# against at least one real LAZ sample)
docker compose -f infra/docker-compose.yml exec backend \
  pytest tests/integration -m real_laz --laz-sample /samples/flight.laz

# Frontend
cd frontend && npm test
```

Expected: all green; the `real_laz` marker test performs upload → pipeline →
artifact assertions (existence, CRS = project CRS, checksums stable across a
re-run into a new processing run).

## Validation notes — 2026-07-19 (T052)

Environment: macOS arm64 host, full docker compose stack, demo user.

**Automated checks**: backend `pytest` 26 passed / 1 skipped (the `real_laz`
test skips — no real drone LAZ sample available on this host); frontend
`npm test` 14 passed.

- **Scenario 1 — PASS (small sample)**: "Vuelo demo" survey processed end-to-end;
  2D hillshade renders over the site and the 3D COPC view renders navigable
  points (verified in Chrome; required the laz-perf wasm bundling fix, commit
  `21774a2`). `GET /surveys/{id}/artifacts` returns `dem` (0.20 m), `copc` and
  `hillshade` with sha256 + sizes + presigned/tile URLs. The 10 GB ≤ 60 min
  timing (SC-005) remains unmeasured — no multi-GB sample on hand.
- **Scenario 2 — PASS (by design + tests)**: stage state is server-side
  (ProcessingRun rows); polling shape covered by
  `test_api_status_retry.py`. Not re-run manually this session.
- **Scenario 3 — PASS (partial manual)**: a real no-CRS upload (`nube.las`)
  ends `failed` with the Spanish cause + corrective action and a retry button
  in the UI; all four failure codes and the retry/new-run flow covered by
  `test_failure_codes.py` and `test_api_status_retry.py`.
- **Scenario 4 — BLOCKED (manual)**: needs a multi-GB upload plus a mid-flight
  network kill; pending-upload listing/expiry covered by
  `test_api_uploads_resume.py`, and the pending-uploads panel renders in the UI.
- **Scenario 5 — PASS (by tests)**: `test_coexistence.py` asserts independent
  runs/artifacts, capture-date ordering and byte-identical sha256 after a
  second survey completes. Not re-run manually.

Doc drift noted: T033/plan mention Potree; the shipped 3D viewer streamed COPC
with copc.js + three.js instead (see commit `3e6e267`). **Resolved
2026-07-19**: the 3D viewer now uses Potree 1.8.2 (vendored under
`frontend/public/potree/`, COPC supported natively since 1.8.2) with
camera-driven progressive LOD, EDL and the measurement/profile sidebar, as
T033 planned. Rendering, sidebar tools and Spanish UI verified manually in
Chrome against the demo flight.
