# Contracts: Slice Domain Modules

**Feature**: 006-point-cloud-slice | **Date**: 2026-07-20

This feature exposes no HTTP API. Its contract surface is two layers: the **pure modules** under
`frontend/src/domain/slice/` — the testable core, with no imports from Potree, the DOM, or React,
where everything correctness-critical lives — and the **boundary modules** under
`frontend/src/viewers/slice/` (`potreeSlice.ts`, `demSampler.ts`, `useSliceDrawing.ts`), which do
the I/O the pure layer cannot: extraction, DEM sampling, and drawing. Boundary modules interpret
nothing; they hand raw data to the pure layer, which is the single place each rule is enforced
and tested.

Signatures are indicative, not final; the behavioural contracts are binding.

## `geometry.ts`

```ts
export function dedupePoints(segments: RawSegment[]): SlicePoint[]
export function vertexMileages(vertices: Vec3[]): number[]
export function turnAngles(vertices: Vec3[]): number[]
export function sharpTurns(vertices: Vec3[], thresholdDeg = 120): number[]
export function isDegenerate(vertices: Vec3[]): boolean
```

**Contracts**:

- `dedupePoints` MUST emit each source point at most once, keyed on world position. A point in
  the overlap between adjacent segment boxes appears once, keeping the occurrence from the
  segment whose centre it is nearest — so its mileage is the one a reader would expect (FR-006).
- `dedupePoints` MUST preserve ordering by mileage.
- `dedupePoints` MUST be exact for the duplicate case, not approximate: duplicates carry
  bit-identical source coordinates, so no distance tolerance is involved.
- `vertexMileages` MUST return cumulative planimetric distance, ignoring elevation, matching
  how Potree computes mileage (R2).
- `sharpTurns` MUST return the indices of vertices whose interior angle is sharper than the
  threshold (FR-006b).
- `isDegenerate` MUST be true for fewer than 2 vertices, and for any line of zero total
  length (Edge Cases).

**Known-truth tests**: a straight line yields zero duplicates; an L-shaped line with a
90° turn yields a known duplicate count for a given width; a 179° turn yields none.

## `density.ts`

```ts
export function meanPointSpacing(numPoints: number, bboxAreaM2: number): number
export function defaultBandWidth(numPoints: number, bboxAreaM2: number): number
export function estimatePointCount(line: SliceLine, numPoints: number, bboxAreaM2: number): number
export function loadDecision(estimate: number): "free" | "confirm" | "refuse"
```

**Contracts**:

- `meanPointSpacing` returns `sqrt(bboxAreaM2 / numPoints)` (R4).
- `defaultBandWidth` returns `3 × meanPointSpacing`, clamped to [0.05, 2.0] m (FR-009, FR-009a).
  The clamp MUST be applied last, so the bounds always hold.
- `estimatePointCount` returns `density × bandArea`, where `bandArea = totalLength × width`.
  It is an approximation assuming uniform density and MUST be presented to the user as such (R3).
- `loadDecision` returns `"free"` below 2 000 000, `"confirm"` in [2 000 000, 10 000 000], and
  `"refuse"` above 10 000 000 (FR-023a). Boundaries inclusive as written.
- All functions MUST handle `numPoints === 0` and zero area without producing `NaN` or
  `Infinity`; they return the clamp minimum and an estimate of zero respectively.

**Known-truth tests**: a cloud of 1 M points over 10 000 m² has 0.1 m spacing and a 0.3 m
default width; each `loadDecision` boundary is tested on both sides.

## `binning.ts`

```ts
export function binPoints(
  points: SlicePoint[],
  view: { mileageRange: [number, number]; elevationRange: [number, number] },
  grid: { width: number; height: number },
): BinnedGrid
```

**Contracts**:

- Cost MUST be `O(points + gridCells)` with a single pass — no per-point draw call, which is
  what makes SC-004 reachable (R5).
- Points outside the view range MUST be excluded, not clamped into edge cells.
- Each occupied cell MUST carry the aggregate needed by the active colour mode (mean elevation,
  mean intensity, dominant classification, or mean colour).
- A coarser `grid` MUST be usable for the reduced-detail pass during a drag, with the same
  function and no separate code path (FR-008a).

**Known-truth tests**: a known point set into a known grid yields a known occupancy pattern;
a point exactly on a cell boundary lands in a deterministic cell; out-of-range points are absent.

## `measure.ts`

```ts
export function measure(from: ChartPoint, to: ChartPoint): SliceMeasurement
```

**Contracts**:

- Returns horizontal distance and elevation delta in true terrain units.
- MUST be independent of vertical exaggeration — the function never receives it (FR-019, SC-006).
  Exaggeration belongs to the drawing transform alone; keeping it out of this signature makes
  the invariant structural rather than a matter of discipline.

**Known-truth tests**: markers on synthetic terrain of known height difference return that
difference; the same inputs return identical values regardless of any exaggeration in view state.

## `demProfile.ts`

```ts
export function toDemProfile(
  samples: { mileage: number; raw: number }[],
  nodataValue: number,
): DemProfile
```

**Contracts**:

- Any sample equal to `nodataValue` MUST become `null` (FR-016). The DEM is written with
  `-9999` (`backend/pipeline/stages/surfaces.py:73`); plotting it would draw a line 10 km below
  the terrain.
- Comparison MUST tolerate float representation, not rely on exact equality.
- Consecutive `null`s MUST remain a gap, never be interpolated across (FR-016).
- The module performs no I/O. Fetching COG bytes belongs to the Potree/network layer; this
  function only interprets sampled values.

**Known-truth tests**: a sample array containing nodata yields nulls in exactly those
positions; a fully-nodata array yields an all-gap profile rather than an error.

## Boundary module: `viewers/slice/potreeSlice.ts`

Not pure and not unit-tested — the seam that keeps everything above testable. It is the **only**
module in the codebase permitted to reference `Potree.*` for this feature.

**Contracts**:

- Wraps `getPointsInProfile(profile, maxDepth, callback)` and returns raw segments plus
  `loadedDepth` / `maxDepth`, performing no geometric interpretation of its own.
- Exposes the orthographic top-down view toggle (`setCameraMode`, `setTopView`) for FR-002.
- Supports cancellation, and MUST abandon an in-flight request when the line changes (FR-028).
- MUST NOT import from `domain/slice/`; data flows one way, from this module into the pure layer.
- Exposes a `pickPointOnCloud(screenXY)` helper (the Potree-side picking used by the drawing
  hook), so `useSliceDrawing.ts` never references `Potree.*` itself.

## Boundary module: `viewers/slice/demSampler.ts`

Not pure and not unit-tested — the DEM I/O seam. It is the **only** module permitted to perform
network I/O against the DEM COG, using the `geotiff` dependency (R6).

```ts
export function openDemCog(url: string): Promise<DemCogHandle>
export function sampleAlongLine(
  cog: DemCogHandle,
  vertices: Vec3[],
  spacing: number,
): Promise<{ mileage: number; raw: number }[]>
```

**Contracts**:

- Reads the COG's overviews and tiles by HTTP range request — never downloads the whole file,
  and never round-trips to the backend (Constitution Principle II).
- Returns **raw** sampled values, including the nodata sentinel unchanged. Interpreting nodata
  into gaps is `demProfile.ts`'s job (FR-016) — this module performs no interpretation, so the
  pure module stays the single, testable place where the `-9999` rule lives.
- The nodata value is read from the COG's own metadata and passed to `toDemProfile`, not
  hard-coded here.
- MUST NOT import from `domain/slice/` except `import type` from `types.ts`; data flows one way,
  into the pure layer.
- On a fetch or decode failure MUST surface a recoverable error, so the overlay can be reported
  as unavailable (FR-017) without taking down the chart.

## Boundary module: `viewers/slice/useSliceDrawing.ts`

Not pure and not unit-tested at the module level (it is a React hook bound to pointer events and
the Potree canvas); its behaviour is covered by the component/drawing tests. It implements the
vertex-placement mechanism behind FR-001, FR-002 and FR-003 — the interaction the pure modules
all assume has already produced a `vertices` array.

```ts
export function useSliceDrawing(handle: SliceViewerHandle): {
  vertices: Vec3[]
  isDrawing: boolean
  start(): void
  addVertex(screenXY: [number, number]): void
  moveVertex(index: number, screenXY: [number, number]): void
  removeVertex(index: number): void
  finish(): void
  clear(): void
}
```

**Contracts**:

- Resolves screen clicks to world coordinates via `potreeSlice.ts`'s `pickPointOnCloud`; it MUST
  NOT reference `Potree.*` directly, keeping `potreeSlice.ts` the single Potree-touching module.
- Produces vertices in the survey's working CRS (UTM metres), so no coordinate conversion occurs
  between drawing and extraction (R8).
- Editing an existing line (add / move / remove vertex) MUST re-emit the full `vertices` array so
  the downstream recompute (`SliceResult`) is driven by a single source of truth (FR-003).
- MUST NOT import from `domain/slice/` except `import type` from `types.ts`.

## Vendored bundle patch

`frontend/public/potree/build/potree/potree.js` is patched to expose `CSVExporter`,
`LASExporter` and `DXFExporter`, which are otherwise private to the bundle closure (R7).
`exports.Exporter` already present is a **TIFF** exporter and is unrelated.

The patch MUST be documented in `frontend/public/potree/VENDORED.md` alongside the existing
decoder-worker patch, including the command to re-apply it on upgrade — that file already
establishes this convention and an undocumented patch would be silently lost on the next
Potree update.
