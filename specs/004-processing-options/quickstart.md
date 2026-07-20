# Quickstart Validation: Selectable & Extensible Processing Options

**Plan**: [plan.md](./plan.md) | **Contracts**: [contracts/rest-api.md](./contracts/rest-api.md) | **Data model**: [data-model.md](./data-model.md)

## Prerequisites

- Docker + compose; repo root.
- A small georeferenced `.laz` sample (same as 001 validation; any UTM 18S/19S cloud works).

```bash
cd infra && docker compose up -d --build
# migrations (incl. backfill) run via the compose entrypoint; verify:
docker compose exec backend python manage.py migrate --check
```

## Scenario 1 — Catalog is served from the registry (US2 groundwork)

```bash
curl -s -b cookies.txt http://localhost:8000/api/v1/processing-options | jq .
```

**Expected**: 3 options (`elevation` required, `hillshade` with prerequisite
`elevation`, `point_cloud_3d`), all `default_selected`, i18n keys only (no
display text).

## Scenario 2 — Selection at upload start; only selected products generated (US1)

1. Log in to the SPA (`http://localhost:5173`), open a project, choose a file.
2. **Expected**: options checklist appears with all three pre-checked;
   `elevation` is checked and disabled (required).
3. Uncheck `point_cloud_3d`, start the upload, close the browser.
4. Reopen after processing: survey `completed`; 2D view shows elevation +
   hillshade layers; **3D tab disabled** (no product).
5. API check — per-option states and absence of the deselected product:

```bash
curl -s -b cookies.txt http://localhost:8000/api/v1/surveys/$SURVEY | jq '.runs[-1].options'
curl -s -b cookies.txt http://localhost:8000/api/v1/surveys/$SURVEY/artifacts | jq '.products | keys'
# expected: ["elevation","hillshade"]  (no point_cloud_3d)
```

## Scenario 3 — Prerequisite closure (FR-006)

Initiate an upload via API selecting only `hillshade`:

```bash
curl -s -b cookies.txt -X POST http://localhost:8000/api/v1/projects/$PROJECT/uploads \
  -H 'Content-Type: application/json' \
  -d '{"filename":"a.laz","size_bytes":1000,"capture_date":"2026-07-19","selected_options":["hillshade"]}' | jq .effective_options
# expected: includes "elevation" (required + prerequisite) and "hillshade"
```

Also negative: `"selected_options":["nope"]` → 400 `invalid_options`.

## Scenario 4 — Per-option failure isolation & retry (FR-009, FR-004)

1. Force a COPC failure (e.g., `docker compose exec worker mv /usr/bin/untwine
   /usr/bin/untwine.bak` **and** break the PDAL fallback by pointing
   `writers.copc` off, or use the test hook option if implemented).
2. Upload with all options. **Expected**: run `failed`; `elevation` and
   `hillshade` options `completed` with their products visible in the 2D view;
   `point_cloud_3d` `failed` with a translated message.
3. Restore the binary; `POST /surveys/$SURVEY/retry`.
4. **Expected**: new run where `elevation`/`hillshade` are `reused` (not
   re-executed — check timestamps) and only `point_cloud_3d` runs; survey ends
   `completed`; 3D tab enables.

## Scenario 5 — Latest-per-option resolution (FR-016)

After Scenario 4 the survey has products from two runs. **Expected**:
`/artifacts` returns `elevation`/`hillshade` attributed to run 1 (via
`reused`) and `point_cloud_3d` to run 2; survey detail shows which run
produced each displayed product.

## Scenario 6 — Pre-existing surveys (FR-012, backfill)

On a database with 001-era surveys, after migrating:

```bash
curl -s -b cookies.txt http://localhost:8000/api/v1/surveys/$OLD_SURVEY | jq '.runs[0].options[].option_id'
# expected: elevation, hillshade, point_cloud_3d — states matching the run outcome
```

2D/3D viewers keep working unchanged for those surveys.

## Scenario 7 — Extensibility end-to-end (US2, SC-003)

Automated test (pytest): register a dummy option (`test_flag`, map2d, trivial
producer writing a tiny file) in the registry within the test, then drive
upload-hook → run and assert: appears in catalog endpoint, selectable,
executes, publishes an attributed artifact, appears in `/artifacts` products —
**without any change to orchestration/serializer/view code**.

```bash
docker compose exec backend pytest tests/ -k "dummy_option or options" -q
```

## Full suites

```bash
docker compose exec backend pytest -q          # backend incl. migrations/backfill tests
cd frontend && npm test                        # OptionPicker, SurveyStatus, viewers gating
```

**Done when**: all scenarios pass and one real-LAZ ingest (Scenario 2) has been
run against the compose stack (constitution dev-flow rule).
