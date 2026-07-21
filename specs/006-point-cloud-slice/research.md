# Research: Point Cloud Slice

**Feature**: 006-point-cloud-slice | **Date**: 2026-07-20

All findings below were verified against the vendored bundle at
`frontend/public/potree/build/potree/potree.js` (Potree 1.8.2) and the existing
frontend, not taken from upstream documentation.

## R1 — Point extraction from the cloud

**Decision**: Use Potree's `pointcloud.getPointsInProfile(profile, maxDepth, callback)`.

**Findings**:

- The entry point is `getPointsInProfile(profile, maxDepth, callback)` (`potree.js:64043`),
  which creates a `ProfileRequest` (`potree.js:63855`).
- `maxDepth` defaults to `Number.MAX_VALUE` and is clamped internally to
  `highestLevelServed` (`potree.js:64180`) — the deepest octree level actually loaded.
  This is the mechanism behind FR-012 and FR-021: what you get back is bounded by what
  has streamed in so far.
- The callback receives a `ProfileData` with a `segments[]` array, one per pair of
  consecutive vertices. Each segment carries `start`, `end`, `length`, and `points`.
- `points.data` is a dictionary of typed arrays keyed by attribute (`position`, `rgba`,
  `intensity`, `classification`, …) with `points.numPoints` — the shape `CSVExporter`
  consumes (`potree.js:72603`).
- Potree already computes distance along the line: `mileage[numAccepted] = localMileage +
  totalMileage` (`potree.js:64016`). We reuse it rather than recomputing.

**Rationale**: The octree traversal, LOD streaming, range requests and worker-based
decoding are all solved here. Reimplementing this against COPC directly would be a large
amount of work with no benefit.

**Alternatives considered**: `copc.js` (already vendored at `libs/copc/index.js`) reading
the COPC directly — rejected because it would duplicate the traversal Potree already
performs for the view that is on screen anyway.

## R2 — The band overlap at direction changes (FR-006)

**Decision**: De-duplicate in our own code, keyed on the source point's position.

**Findings**: The acceptance test per segment is (`potree.js:64011`):

```js
if (distance < this.profile.width / 2 && centerDistance < segment.length / 2)
```

where `distance` is the perpendicular distance to the segment's cut plane and
`centerDistance` the distance to the plane bisecting the segment. Geometrically this is
an **axis-aligned box around each segment**, of width `profile.width` and length
`segment.length`.

Two consequences, both confirming the spec:

1. At a vertex the boxes of adjacent segments overlap on the inside of the turn. A point
   in that region satisfies both tests and is emitted **twice, at two different mileages**.
   Potree performs no de-duplication.
2. On the outside of the turn a wedge is covered by neither box, so points there are
   absent. This is inherent to the box formulation and cannot be fixed by de-duplication.

**Rationale**: FR-006 requires each point at most once. Since duplicates carry identical
source coordinates, keying on the quantised position is exact and cheap. FR-006a's vertex
markers make the wedge gaps legible, and FR-006b's warning fires where both effects are
worst — sharper turns overlap more and open a wider wedge.

**Alternatives considered**: Assigning each point to its nearest segment (a true
partition) — rejected as it requires intercepting Potree's traversal rather than
post-processing its output, for a result the de-duplication achieves more simply.

## R3 — Estimating point count before a full-resolution load (FR-023)

**Decision**: Estimate as `cloud density × band area`, computed from the cloud's own
header, and show it as an order-of-magnitude figure.

**Findings**: The point cloud exposes its total point count and bounding box
(`getNumPoints`, `pcoGeometry.boundingBox`). Planimetric density is
`numPoints / bbox_area`. The band's area is `Σ(segment.length) × width`.

**Rationale**: Cheap, needs no traversal, and is accurate enough for a three-way decision
at 2 M and 10 M. It assumes uniform density, which real surveys violate — so the estimate
must be **presented as approximate** and the hard stop enforced against the real count as
loading proceeds, not against the estimate alone.

**Alternatives considered**: Counting via a shallow-depth traversal and extrapolating —
more accurate but adds latency to the very interaction the estimate exists to keep cheap.

## R4 — Default band width (FR-009)

**Decision**: `3 × mean point spacing`, clamped to [5 cm, 2 m], where mean spacing is
`sqrt(bbox_area / numPoints)`.

**Rationale**: Same header-derived density as R3. On a dense survey this yields a thin,
crisp band; on a sparse one, a band wide enough to contain points at all.

**Open risk**: The 3× multiplier and the clamp bounds are reasoned, not observed. The
spec's checklist records this. Confirm against a real survey during implementation.

**Alternatives considered**: Deriving from the DEM's `resolution_m` — rejected because the
DEM is optional per survey (004 made products selectable), so it cannot be a dependency of
a default the tool always needs.

## R5 — Rendering the chart at 30 fps (SC-004)

**Decision**: Canvas 2D with **per-pixel binning**, not WebGL.

**Findings**: `window.THREE` is not exposed by the bundle (verified by grep), so Potree's
embedded three.js is not reachable from application code. A WebGL path would mean adding
`three` or a WebGL wrapper as a new npm dependency.

**Rationale**: The binning insight makes WebGL unnecessary. A chart occupies on the order
of 1000×500 CSS pixels; no matter how many points the band holds, at most ~500k pixels can
be lit. Aggregating points into a per-pixel grid once, then drawing the grid, makes draw
cost proportional to **chart area rather than point count**. Millions of points reduce to a
constant-cost draw, and the reduced-detail pass during a drag is simply a coarser grid.
This satisfies SC-004 and SC-004a without a new rendering dependency.

**Alternatives considered**:

- WebGL point rendering (three.js or regl): genuinely faster for raw point throughput, but
  adds a dependency and a shader surface to maintain for a result binning already reaches.
- Naive Canvas 2D, one `fillRect` per point: fine at 50k points, unusable at millions.
  Rejected — it is the approach that makes SC-004 unachievable.

## R6 — DEM overlay (FR-015, FR-016)

**Decision**: Sample the DEM COG client-side via HTTP range requests, adding `geotiff`
as a frontend dependency.

**Findings**: The frontend has no COG reader today; `titiler` serves *tiles* for the 2D
map, which are rendered images, not elevation values. Titiler's point endpoint returns one
value per HTTP call — unusable for the hundreds of samples a section needs.

**Rationale**: Constitution Principle II requires interactive analysis to run client-side
against the DEM COG via HTTP range requests, with zero server round trips. `geotiff.js`
is the standard library for exactly this and reads the COG's overviews and tiles by range.
This is the only option consistent with Principle II.

**Nodata handling**: The DEM is written with `nodata: -9999`
(`backend/pipeline/stages/surfaces.py:73`). Samples equal to the nodata value must become
gaps in the overlay, never plotted as an elevation of -9999 — this is FR-016, and getting
it wrong would draw a line plunging 10 km below the terrain.

**Alternatives considered**:

- A backend profile-sampling endpoint: simpler to implement, but a direct violation of
  Principle II and slower to interact with.
- Reusing titiler tiles and reading pixel values from the rendered image: the tiles are
  colourised for display, so elevation is not recoverable from them.

## R7 — Exporters (FR-024, FR-025)

**Decision**: Patch the vendored bundle to expose `CSVExporter`, `LASExporter` and
`DXFExporter`; document it in `VENDORED.md`.

**Findings**: All three classes exist (`potree.js:72603`, `72652`, `74046`) but are
**private to the bundle's closure**. The only export is `exports.Exporter`
(`potree.js:68244`), which is `class Exporter` at `potree.js:68133` — a **TIFF** exporter,
unrelated to profiles. Their APIs are static and self-contained: `CSVExporter.toString(points)`,
`LASExporter.toLAS(points)`.

**Rationale**: Reimplementing LAS (binary header, scale/offset handling — the class already
adapts scale to the bounding box diagonal, `potree.js:72659`) and DXF is real work with a
correctness risk, to produce what is already sitting in the bundle. `VENDORED.md` already
documents a `sed` patch to the decoder workers and instructs re-applying it on upgrade;
this becomes a second documented entry in that same procedure.

**Alternatives considered**:

- Reimplementing the three formats in application code: rejected, as above.
- Using the native `ProfileTool` UI solely for export: rejected — it would surface Potree's
  jQuery interface, defeating the purpose of the custom UI.

## R8 — Drawing in top-down orthographic view (FR-002)

**Decision**: Use Potree's `setCameraMode(CameraMode.ORTHOGRAPHIC)` and `setTopView()`.

**Findings**: Both are present in the bundle (verified by grep), as is `CameraMode.ORTHOGRAPHIC`.

**Rationale**: Drawing in the cloud's own coordinate space avoids any conversion between
the map's lon/lat and the project's UTM working CRS (`CrsCatalogEntry`, seeded with Chilean
UTM zones). That conversion would be a source of positional error in a tool whose entire
value rests on positional fidelity.

**Alternatives considered**: Drawing on the MapLibre 2D view with terra-draw — rejected for
the coordinate-conversion risk and because the two viewers are alternate modes today, not
simultaneous.

## R9 — Testing strategy

**Decision**: All geometry, density, binning and measurement logic lives in pure modules
under `frontend/src/domain/slice/`, with no imports from Potree or the DOM, and is tested
first with vitest. React components are tested with testing-library as the existing suite does.

**Rationale**: Potree is a global-script, WebGL-dependent library that cannot be loaded in
jsdom, so anything entangled with it is effectively untestable. Keeping the logic that can
be wrong — de-duplication, mileage, density, estimates, nodata handling — in pure functions
makes the risky parts the testable parts. This follows the spirit of Constitution
Principle VIII (known-truth tests for analysis code) within the constraints of a
client-side feature; see the Constitution Check in `plan.md` for why VIII's
"Python library" letter does not apply here.

**Test fixtures**: Synthetic point sets of known geometry — a plane of known slope, a
vertical face spanning a known height range, a polyline with a known sharp turn producing
a known number of duplicates.
