# Implementation Plan: Point Cloud Slice

**Branch**: `main` | **Date**: 2026-07-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-point-cloud-slice/spec.md`

## Summary

A client-side inspection tool: the user traces a polyline over a survey's point cloud in a
top-down orthographic view, sets a band width, and sees the points inside that band plotted
as distance along the line against elevation. Manual measurement, a DEM overlay for judging
raster fidelity, and export in CAD, tabular, point-cloud and image formats.

The technical approach is to use the already-vendored Potree 1.8.2 as the extraction engine
(`getPointsInProfile`) while building the entire interface from the project's own design
system. All logic that can be wrong — de-duplication across the band's self-overlap, density
estimation, per-pixel binning, DEM nodata handling — lives in pure TypeScript modules with
no Potree or DOM imports, tested first. Two new pieces of supporting work: a documented
patch to expose Potree's private exporters, and `geotiff` as a new dependency to sample the
DEM COG by HTTP range requests.

No backend changes. No migrations. No new endpoints.

## Technical Context

**Language/Version**: TypeScript 5.7, React 18.3

**Primary Dependencies**: Potree 1.8.2 (vendored static build, not npm), `geotiff` (new),
Zustand 5, i18next 24, Tailwind 4

**Storage**: None. The feature persists nothing — no database, no object storage, no
browser storage.

**Testing**: vitest 2.1 + @testing-library/react 16, jsdom 25

**Target Platform**: Modern desktop browsers (WebGL 2 required by the existing 3D viewer)

**Project Type**: Web application — frontend only for this feature

**Performance Goals**: ≥30 chart redraws per second at reduced detail while a control is
dragged (SC-004); refinement to full detail within 1 s of release (SC-004a)

**Constraints**: Full-resolution loads free below 2 M points, confirmed 2–10 M, refused
above 10 M (FR-023a); no truncated data export under any circumstance (FR-023b); all UI
text available in Spanish and English (FR-029)

**Scale/Scope**: One slice at a time per survey; up to 10 M points per full-resolution
load; roughly 6 new UI components and 5 pure logic modules

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Verdict | Notes |
|---|---|---|
| I. Analysis on rasters, visualisation on tiles | **Pass, with declared position** | The feature reads raw cloud points for **display**, which is the role the constitution assigns to COPC. No metric is computed, stored, or fed to the evaluation engine. The spec states this explicitly in *Relationship to Principle I* rather than leaving it implicit. See the note below. |
| II. Thin backend, interactive frontend | **Pass, strongly** | Zero server round trips. Extraction is client-side from the COPC; the DEM overlay samples the COG by HTTP range requests, which is precisely what this principle prescribes. |
| III. Async ingest, always | **N/A** | No ingest path touched. |
| IV. Station-based evaluation model | **N/A** | Produces no stations, metrics or compliance status. |
| V. Assisted detection, human authority | **Pass** | No detection of any kind. Every number originates in a deliberate human act. |
| VI. Evaluation profiles as first-class data | **N/A** | No thresholds, no classification. |
| VII. Reports are reproducible artifacts | **N/A** | Produces no reports. Exports are user-initiated downloads, not platform artifacts. |
| VIII. Test-first for the analysis core | **Pass** (per v1.3.1 scope) | The "Alcance" paragraph added to VIII in constitution v1.3.1 scopes it out of purely visual inspection tools. See the note below. |
| IX. Bilingual by design | **Pass** | FR-029; the custom UI exists partly so the interface can be translated at all. |
| X. Mining focus, neutral core | **Pass** | Inspecting benches, berms and slope faces is squarely the target domain. |
| XI. AI as isolated service | **N/A** | No inference. |

### Note on Principle I

Principle I is marked NON-NEGOTIABLE and states that no feature may query raw points *at
analysis time*. This feature queries raw points at **display** time. The distinction is the
one the principle itself draws when it says the raw cloud "exists only for visualisation."

The boundary is enforced by design, not by intention: nothing in this feature writes to the
database, so no derived value can persist even accidentally; and no module in the feature is
imported by, or exports to, any evaluation code. A future feature that stored metrics
derived from raw points would require a constitutional amendment — this one does not.

There is a second, subtler argument for the feature under Principle I: its DEM overlay
(FR-015) exists to let a user verify that the raster every downstream analysis depends on is
faithful to the terrain. The tool serves the raster-first architecture rather than competing
with it.

### Note on Principle VIII

Principle VIII requires that the analysis engine — and it names "profile extraction"
explicitly — be a framework-independent **Python library** with known-truth pytest coverage.
Read literally, a TypeScript profile extractor in the browser sat uncomfortably against it,
because Principle II is equally explicit in the other direction: "profile navigation" and
"cross-section inspection" **must** run client-side with zero server round trips. One
implementation cannot satisfy both.

**Constitution v1.3.1 resolves this explicitly.** A "Alcance" paragraph added to Principle
VIII scopes it to the engine that produces *persisted, auditable metrics consumed by
evaluation and reports*, and states that purely visual inspection tools which persist no
derived value and feed no evaluation are governed instead by Principle II, isolating their
error-prone logic into pure modules tested against known truth in the client language. This
feature is exactly such a tool, so it falls outside VIII by the principle's own text — not by
interpretation. The amendment keeps its teeth: the day this tool persists a metric, it falls
back under VIII and requires a Python engine. When the road-evaluation module arrives, its
profile extraction will be that Python library with known-truth tests, operating on the DEM
raster as Principle I requires.

What is adopted here is VIII's substance: the logic that can be wrong is isolated into pure
modules and tested first against synthetic geometry of known truth (see R9 in
[research.md](./research.md)).

**Gate result: PASS.** No unjustified violations; Complexity Tracking is therefore empty.

## Project Structure

### Documentation (this feature)

```text
specs/006-point-cloud-slice/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── slice-domain.md  # Phase 1 output — pure module contracts
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
frontend/
├── public/potree/
│   ├── build/potree/potree.js      # patched: expose CSV/LAS/DXF exporters
│   └── VENDORED.md                 # patch documented alongside the worker patch
├── src/
│   ├── domain/slice/               # pure logic — no Potree, no DOM, no React
│   │   ├── types.ts                # shared types; zero imports (see contracts)
│   │   ├── geometry.ts             # de-duplication, mileage, vertex markers, turn angles
│   │   ├── density.ts              # mean spacing, default width, point-count estimate
│   │   ├── binning.ts              # per-pixel aggregation for the chart
│   │   ├── measure.ts              # two-marker distance and elevation delta
│   │   └── demProfile.ts           # pure: interpret DEM samples, nodata → gaps
│   ├── viewers/
│   │   ├── Cloud3D.tsx             # modified: expose viewer handle, mount the tool
│   │   └── slice/                  # Potree-facing and React layers
│   │       ├── SlicePanel.tsx      # the chart panel shell
│   │       ├── SliceChart.tsx      # canvas rendering of the binned grid
│   │       ├── SliceControls.tsx   # width, exaggeration, colouring
│   │       ├── SliceExport.tsx     # full-resolution load + export actions
│   │       ├── potreeSlice.ts      # boundary: the only module that touches Potree's API
│   │       ├── demSampler.ts       # boundary: DEM COG sampling via geotiff (HTTP range)
│   │       ├── useSliceDrawing.ts  # vertex placement/edit on the Potree canvas
│   │       └── useSliceTool.ts     # orchestration hook
│   ├── stores/slice.ts             # ephemeral session state
│   └── i18n/{es,en}/common.json    # new `slice.*` keys
└── tests/
    ├── slice-geometry.test.ts      # pure: de-duplication, mileage, turn detection
    ├── slice-density.test.ts       # pure: spacing, default width, estimates
    ├── slice-binning.test.ts       # pure: aggregation correctness
    ├── slice-dem-profile.test.ts   # pure: nodata → gaps
    └── slice-panel.test.tsx        # component: gating, controls, export availability
```

**Structure Decision**: Frontend-only, splitting along a strict testability seam. Everything
under `src/domain/slice/` is pure TypeScript that vitest can exercise directly in jsdom.
Potree — a global-script, WebGL-dependent library that cannot load in jsdom — is confined to
the single module `viewers/slice/potreeSlice.ts`, which does extraction and nothing else.
This is what makes the correctness-critical logic testable at all, and it follows the
existing convention where `viewers/Cloud3D.tsx` already isolates Potree from the rest of the
application.

## Phase 0: Research

Complete — see [research.md](./research.md). Nine findings, all verified against the
vendored bundle rather than upstream documentation. The decisive ones:

- **R2**: Potree's per-segment acceptance test is a box (`potree.js:64011`); adjacent boxes
  overlap at a turn and Potree does **not** de-duplicate, so FR-006 is our work. It does
  compute cumulative mileage, which we reuse.
- **R5**: `window.THREE` is not exposed, so WebGL would mean a new dependency — but per-pixel
  binning makes draw cost proportional to chart area rather than point count, so Canvas 2D
  meets SC-004 without one.
- **R6**: The DEM overlay needs `geotiff` (new dependency); titiler serves colourised tiles
  from which elevation is not recoverable. Nodata is `-9999` and must become gaps.
- **R7**: The exporters exist but are private to the bundle closure; `exports.Exporter` is an
  unrelated TIFF exporter. A documented patch exposes them.

No unresolved NEEDS CLARIFICATION remain.

## Phase 1: Design & Contracts

Complete. Artifacts:

- **[data-model.md](./data-model.md)** — the three ephemeral session concepts, their fields,
  lifecycle and validation rules. No persistence anywhere.
- **[contracts/slice-domain.md](./contracts/slice-domain.md)** — signatures and behavioural
  contracts of the pure modules. These are the testable surface of the feature.
- **[quickstart.md](./quickstart.md)** — runnable validation scenarios against a real survey.

### Post-design Constitution re-check

Unchanged: **PASS**. The design strengthens rather than weakens the Principle I position —
confining Potree to a single extraction module and keeping all logic pure makes it
structurally evident that no derived value can reach persistence or the evaluation engine.
The `geotiff` dependency introduced in R6 is what makes Principle II's "client-side against
the DEM COG via HTTP range requests" literally achievable, so it moves toward the
constitution rather than away from it.

## Complexity Tracking

No constitutional violations require justification. This section is intentionally empty.
