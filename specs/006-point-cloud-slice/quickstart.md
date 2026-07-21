# Quickstart: Point Cloud Slice

**Feature**: 006-point-cloud-slice | **Date**: 2026-07-20

Validation scenarios proving the feature works end to end. The pure logic is covered by
vitest; the scenarios below cover what unit tests structurally cannot — Potree extraction,
WebGL rendering, and the browser's export path.

## Prerequisites

A survey with a **point cloud** product is required. Since 004 made products selectable, a
survey may have a DEM and no cloud — confirm the cloud product resolved before starting.

```bash
cd infra && docker compose up -d --build
docker compose exec backend python manage.py createuser demo --password demo1234
```

Generate a fixture and ingest it **inside the container** — the local venv usually lacks
`untwine`, which silently changes how COPC is produced (see the repo's CLAUDE.md):

```bash
docker compose exec backend python3 -c "
from tests.fixtures import make_fixtures
from pathlib import Path
make_fixtures.make_ramp_laz(Path('/tmp/fixture'))
"
```

Upload `/tmp/fixture/ramp.laz` through the UI at <http://localhost:8080> with both the
elevation and point cloud products selected, and wait for both to resolve.

## Automated tests

```bash
cd frontend && npm test
```

Expected: the five new suites pass — `slice-geometry`, `slice-density`, `slice-binning`,
`slice-dem-profile`, `slice-panel` — alongside the existing ones.

The pure suites carry the correctness weight. `slice-geometry` in particular must prove
de-duplication against a known L-shaped line, since that is logic Potree does not provide
(see R2 in [research.md](./research.md)).

## Scenario 1 — Draw a slice and read the terrain (US1)

1. Open the survey and switch to the 3D view.
2. Activate the slice tool. **Expect**: the camera moves to a top-down orthographic view.
3. Trace a line across the ramp and complete it. **Expect**: a chart appears plotting distance
   against elevation, at a default band width derived from the cloud's density — not a fixed
   value (FR-009).
4. Drag the band width control. **Expect**: the chart updates continuously as you drag, with no
   confirmation step, and points visibly appear and disappear.
5. Drag the vertical exaggeration control. **Expect**: the chart rescales and the active factor
   stays on screen at all times (FR-010).
6. Read the chart header. **Expect**: both the point count and the loaded level of detail
   (FR-012).
7. Cycle the colour modes. **Expect**: only modes the cloud actually carries are offered — a
   fixture without RGB must not present an RGB option (FR-011).

**Validates**: FR-001, FR-002, FR-007 – FR-013, SC-001, SC-004.

## Scenario 2 — Polyline turns (FR-006)

1. Trace a line with a deliberate 90° turn.
2. **Expect**: a vertical marker on the chart at the vertex (FR-006a).
3. **Expect**: no doubled cluster of points around the turn — the inner overlap is
   de-duplicated (FR-006). This is the scenario that fails if de-duplication is skipped, since
   Potree emits those points twice at two different mileages.
4. Trace a line with a turn sharper than 120°. **Expect**: a warning that the section is
   distorted there (FR-006b).

**Validates**: FR-006, FR-006a, FR-006b.

## Scenario 3 — Audit the DEM (US2)

1. Trace a line across a slope face.
2. Enable the DEM overlay. **Expect**: the DEM's elevation drawn over the raw points, visually
   distinct.
3. **Expect**: where the raw points span several metres of height at one location, the overlay
   sits at a single averaged elevation between them — the `output_type: "mean"` artefact this
   feature exists to expose.
4. Find an area the DEM has no data for. **Expect**: a gap in the overlay, **not** a line
   plunging toward -9999 (FR-016).
5. Repeat on a survey with no elevation product. **Expect**: the overlay control is unavailable
   with a stated reason (FR-017).

**Validates**: FR-015 – FR-017, SC-002, SC-003.

## Scenario 4 — Measure by hand (US3)

1. Place two markers spanning a feature of known height on the fixture.
2. **Expect**: horizontal distance and elevation delta matching the known geometry.
3. Change the vertical exaggeration. **Expect**: the reported values do not change (FR-019).
4. Leave the survey and return. **Expect**: no measurement survives (FR-020, FR-005).

**Validates**: FR-018 – FR-020, SC-006, SC-009.

## Scenario 5 — Export (US4)

1. With a chart displayed at partial detail, open the export options. **Expect**: data exports
   unavailable, with the reason given (FR-022).
2. Request a full-resolution load on a small selection. **Expect**: progress shown, cancellable.
3. Cancel mid-load. **Expect**: the chart returns to its previous state and data exports are
   unavailable again (FR-021).
4. Complete a load, then export each format. **Expect**: the CAD file opens in a CAD
   application, the tabular file in a spreadsheet, and the point cloud file in a point cloud
   application — each without repair (SC-007).
5. Compare the exported point count against the chart's count after full load. **Expect**: they
   match; the export contains every point in the band (FR-026, SC-005).
6. Save the chart image. **Expect**: scale and vertical exaggeration factor rendered into the
   image (FR-027).
7. Start a full-resolution load, then edit a vertex mid-load. **Expect**: the load is abandoned,
   not applied to the new line (FR-028).

**Validates**: FR-021 – FR-028, SC-005, SC-007.

## Scenario 6 — Load limits (FR-023)

1. Trace a long line with a wide band so the estimate lands between 2 M and 10 M points.
   **Expect**: the estimate is shown and loading waits for explicit confirmation (FR-023a).
2. Widen further, past 10 M. **Expect**: the load is refused, and the message states how much
   the line or band must shrink — **not** a partial load (FR-023a, FR-023b).

**Validates**: FR-023, FR-023a, FR-023b.

## Scenario 7 — Boundaries and empty states

1. Open a survey with no point cloud product. **Expect**: the tool unavailable with a stated
   reason, not a missing control (FR-004).
2. Place two vertices at the same location. **Expect**: refused with an explanation.
3. Set a band far narrower than the point spacing. **Expect**: an empty result with guidance to
   widen the band — not a blank panel and not an error (FR-014).
4. Trace a line extending beyond the surveyed area. **Expect**: gaps where coverage ends, with
   distances along the line still true.
5. Switch the interface between Spanish and English. **Expect**: no untranslated text in either
   (FR-029, SC-008).

**Validates**: FR-004, FR-014, FR-029, SC-008, Edge Cases.

## Regression check

The slice tool modifies `Cloud3D.tsx`, which serves the existing 3D viewer. Confirm the plain
3D view still loads, still handles an expired presigned URL by remounting, and still switches
between 2D and 3D — with the slice tool never activated.
