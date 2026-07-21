# Data Model: Point Cloud Slice

**Feature**: 006-point-cloud-slice | **Date**: 2026-07-20

## Persistence: none

This feature writes to no database, no object storage, and no browser storage. There are no
migrations, no Django models, and no serializers. Everything below lives in memory for the
duration of a session and is discarded when the user leaves the survey (FR-005).

This is not incidental — it is what keeps the feature inside Constitution Principle I. A
value that cannot be stored cannot leak into the evaluation engine.

## Entities

### SliceLine

The geometry the user traced, plus the band width. One at a time per survey.

| Field | Type | Notes |
|---|---|---|
| `vertices` | `Vec3[]` | Ordered, in the survey's working CRS (UTM metres). Minimum 2. |
| `width` | `number` | Band width in metres. Defaults per FR-009. |

**Validation**:

- Fewer than 2 vertices → no chart; the tool reports why (Edge Cases).
- Two coincident vertices, or a total length of zero → rejected with the same treatment.
- `width` clamped to [0.05, 2.0] m for the derived default (FR-009a); the user may set values
  outside that range manually, bounded by a hard minimum above zero.

**Lifecycle**: `drawing` → `complete` → (`editing` → `complete`)* → discarded. Any edit
invalidates the current `SliceResult` and aborts an in-flight full-resolution load (FR-028).

### SliceResult

The points inside the band, after our own post-processing of what Potree returned.

| Field | Type | Notes |
|---|---|---|
| `points` | `SlicePoint[]` | De-duplicated (FR-006). |
| `vertexMileages` | `number[]` | Cumulative distance at each vertex, for the markers (FR-006a). |
| `totalLength` | `number` | Metres along the line. |
| `elevationRange` | `[number, number]` | For scaling the chart axis. |
| `loadedDepth` | `number` | Octree level reached. |
| `maxDepth` | `number` | Deepest level available. |
| `isComplete` | `boolean` | `loadedDepth === maxDepth`. **Gates data export** (FR-022). |

Where `SlicePoint` is `{ mileage, elevation, intensity?, classification?, rgba?, position }` —
`mileage` and `elevation` drive the chart, `position` (world XYZ) is needed for 3D exports and
as the de-duplication key.

**Validation**:

- An empty `points` array is a legitimate result, reported as such with guidance to widen the
  band (FR-014) — never as an error.
- `isComplete` is false until a full-resolution load finishes. No export path may read
  `points` for a data export while it is false (FR-022, FR-023b).

**Lifecycle**: Recomputed whenever `SliceLine` changes. Superseded results are discarded; an
in-flight computation for a superseded line is abandoned rather than applied (FR-028).

### SliceMeasurement

Two markers the user placed and the values between them. Never stored (FR-020).

| Field | Type | Notes |
|---|---|---|
| `from` | `{ mileage, elevation }` | First marker. |
| `to` | `{ mileage, elevation }` | Second marker. |
| `horizontalDistance` | `number` | `abs(to.mileage - from.mileage)`, metres. |
| `elevationDelta` | `number` | `to.elevation - from.elevation`, metres. |

**Validation**: Both values are computed in true terrain units and are invariant under
vertical exaggeration (FR-019, SC-006). Exaggeration affects only the drawing transform, never
the stored coordinates the measurement reads.

### DemProfile

The DEM's own elevation along the same line, for the overlay. Present only when the survey has
an elevation product.

| Field | Type | Notes |
|---|---|---|
| `samples` | `{ mileage, elevation \| null }[]` | `null` marks nodata. |
| `sampleSpacing` | `number` | Metres between samples. |

**Validation**: A sample equal to the DEM's nodata value (`-9999`, set at
`backend/pipeline/stages/surfaces.py:73`) MUST become `null` and be drawn as a gap, never
plotted (FR-016). Plotting it would draw a line 10 km below the terrain.

## View state (not entities)

Presentation settings held in the store, listed for completeness: `verticalExaggeration`,
`colourMode` (`elevation` | `intensity` | `classification` | `rgb`), `overlayEnabled`,
`viewportRange` for keyboard navigation, and the full-resolution load's
`status` / `progress` / `estimate`.

Available colour modes are filtered to the attributes the cloud actually carries; a mode whose
attribute is absent is not offered (FR-011, Edge Cases).

## Relationships

```text
SliceLine ──produces──> SliceResult ──renders──> chart
    │                        └──gates──> data export (isComplete)
    ├──produces──> DemProfile (when the survey has an elevation product)
    └──hosts────> SliceMeasurement[]  (ephemeral, never consumed by anything)
```

Nothing in this graph has an edge to a persisted entity, an API call that writes, or the
evaluation engine. That absence is the design.
