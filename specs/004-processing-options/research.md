# Research: Selectable & Extensible Processing Options

**Date**: 2026-07-19 | **Plan**: [plan.md](./plan.md)

No NEEDS CLARIFICATION markers remained after `/speckit-clarify` (5 questions
resolved in spec). Research below settles the implementation-level unknowns.

## R1 — Where the option catalog lives

**Decision**: A code registry (`backend/pipeline/options.py`): declarative
`OptionSpec` dataclasses (id, `label_key`, `description_key`, `input_types`,
`target_view`, `required`, `default_selected`, `active`, `prerequisites`,
`producer`) plus `InputTypeSpec` (id, prep steps). The database stores only
**plain option-id strings** on runs and artifacts, validated against the
registry at write time. The catalog API serves the registry directly.

**Rationale**: FR-007 defines "adding an option" as registering a declaration
plus a processing routine — inherently a code release, since the routine must
ship in the worker image. A DB catalog table would be a second source of truth
requiring sync (fixtures, ordering, drift between image and DB). String ids on
rows keep referential stability without FK ceremony; deactivating/retiring an
option never breaks historical rows (FR-008). Principle IX is satisfied by
storing i18n keys, never display text.

**Alternatives considered**: (a) DB table à la `CrsCatalogEntry` — rejected:
CRS entries are pure data usable without code; options are code-bound, and the
dual source of truth is the main failure mode. (b) Django admin-managed catalog
— rejected: spec explicitly scopes catalog management to dev releases.

## R2 — Selection capture, validation, and closure

**Decision**: `POST /projects/:id/uploads` accepts `selected_options`
(list of ids, optional — defaults to the registry's default set). The backend
validates: every id exists, is active, and applies to the upload's input type;
then it **adds required options and prerequisite closure** server-side and
stores the effective selection on `UploadSession.selected_options` (JSONField).
Invalid ids or an inactive option yield `invalid_options` (400). The tusd
post-finish hook copies the effective selection onto the run.

**Rationale**: The UI auto-selects prerequisites visibly (clarification Q2),
but the server cannot trust the client — recomputing the closure server-side
makes the invariant "no run with missing inputs" (FR-006) unconditional, and
auto-adding required options enforces FR-002 regardless of client behavior.
Storing the selection on the upload session implements clarification Q4
(selection at upload start, unattended processing at completion) with zero new
endpoints. JSONField (not M2M) because the catalog is not a table (R1).

**Alternatives considered**: rejecting instead of completing the closure —
rejected: forces every client to reimplement closure logic; server completion
plus a UI that mirrors it gives one canonical behavior.

## R3 — Orchestration: dynamic chain, per-option tasks

**Decision**: Keep Celery `chain`. `enqueue_run` builds it dynamically:
mandatory prep tasks per input type (`relocate_source → run_validation →
run_reprojection` for `point_cloud`), followed by **one `run_option` task per
selected option in deterministic topological order** (prerequisites first),
then a `finalize_run` task. Prep failures abort the chain (nothing can
proceed). Option tasks never abort the chain: each wraps its producer, marks
its `RunOption` row running/completed/failed, and on failure marks dependent
selected options `skipped`; subsequent tasks check their own state and no-op
if skipped. `finalize_run` sets run state (completed if all options completed,
failed otherwise) and survey status, and cleans the workdir.

**Rationale**: Preserves 001's worker-safety pattern (each task re-downloads
inputs it misses, transitions persisted per task) while implementing
per-option isolation (clarification Q3). Sequential execution respects the
constitution's memory budgets (no two heavy stages competing for RAM on one
worker); parallel groups are a later optimization the shape already permits.
A single monolithic "run all options" task was rejected: it loses per-task
crash tolerance and observable transitions.

**Alternatives considered**: Celery `group`/`chord` for independent options —
deferred (memory budgets, single-worker dev); `link_error` chains — rejected
as harder to reason about than explicit skip-state checks.

## R4 — Producers, shared intermediates, and multi-option routes (FR-015)

**Decision**: Split `generate_surfaces` into per-option producers:
`produce_elevation` (PDAL binning → COG DEM), `produce_hillshade` (gdaldem
from the DEM **artifact of the same run** — its prerequisite), and
`produce_point_cloud_3d` (untwine → COPC, PDAL fallback). A producer receives
a `RunContext` (run, workdir, storage helpers) and returns artifact
descriptors; the task wrapper uploads, checksums, and creates
`DerivedArtifact` rows **when the option completes** (per-option publication).
The registry's `producer` field may map several options to one routine later
(NodeODM emitting DEM + orthophoto + cloud in one execution): the wrapper
already supports a producer declaring multiple fulfilled options, marking all
their `RunOption` rows from a single execution.

**Rationale**: Directly implements FR-015's option/route decoupling with the
minimum machinery: options are the unit of selection, publication, progress
and failure; routes are just Python callables. Hillshade consuming the DEM as
a within-run prerequisite artifact keeps the dependency explicit and testable.

**Alternatives considered**: keeping `generate_surfaces` monolithic and
filtering outputs — rejected: couples all products to one failure domain,
contradicting per-option publication.

## R5 — Retry semantics and artifact resolution (FR-004, FR-016)

**Decision**: Retry stays `POST /surveys/:id/retry` and **creates a new run**
(append-only history) carrying the same effective selection; options that
already have a completed `RunOption` in the previous run are created as state
`reused` (no re-execution, no new artifact). US3's "additional options" later
reuses the same mechanism with a different selection — the enqueue path takes
`(survey, selection)` regardless. Viewers resolve products via a per-survey
query: for each option, the artifact from the **latest run whose RunOption
completed** (`reused` rows point back, transitively, to the producing run).
`GET /surveys/:id/artifacts` returns this resolved set.

**Rationale**: Append-only runs preserve Principle III's "reprocess creates a
new version, never mutates" without re-running expensive completed options
(clarification Q3/Q5). Resolution at read time (simple query over
`RunOption` + `DerivedArtifact`) avoids denormalized "current artifact"
pointers that could drift.

**Alternatives considered**: re-executing failed options inside the same run —
rejected: mutates a finished run's history and breaks run-level versioning;
a `current_artifact` FK on Survey — rejected as denormalization with no
measured need.

## R6 — Backward compatibility & backfill (FR-012)

**Decision**: One migration adds columns with safe defaults
(`input_type='point_cloud'` on Survey/ProcessingRun; `option_id` nullable on
DerivedArtifact) plus a data migration: for every existing artifact, set
`option_id` from its `kind` (`dem→elevation`, `hillshade→hillshade`,
`copc→point_cloud_3d`) and create completed `RunOption` rows for every
existing run from its artifacts (failed runs get rows for the then-standard
selection with states inferred from run state). `ProcessingRun.stage` keeps
its values; `surface_generation` remains valid for historical rows and new
runs use per-option progress as the primary signal.

**Rationale**: Old surveys keep rendering (viewers resolve per option) and
their detail shows a truthful "then-standard options" selection — exactly
FR-012 — without touching object storage.

**Alternatives considered**: leaving old rows unattributed and special-casing
readers — rejected: every consumer would carry the legacy branch forever.

## R7 — Frontend selection & status UX

**Decision**: `UploadWidget` fetches `GET /processing-options?input_type=
point_cloud` once and renders an `OptionPicker` checklist: required options
checked + disabled; defaults pre-checked; checking a dependent auto-checks its
prerequisites (visibly); unchecking a prerequisite unchecks dependents.
Labels/descriptions come from i18n keys shipped in `frontend/src/i18n` (es/en).
`SurveyStatus` renders per-option rows (pending/running/completed/failed/
skipped/reused) from the extended survey detail; the 2D viewer adds layers
only for products present, and the 3D tab enables only when a
`point_cloud_3d` product resolves.

**Rationale**: Mirrors the server-side closure (R2) so the user always sees
the effective selection before starting the upload (clarification Q2/Q4);
keeps SC-001 (< 1 min added) by defaulting to today's behavior with zero
clicks.

**Alternatives considered**: modal step after upload completes — rejected by
clarification Q4.

## R8 — Naming of initial option ids

**Decision**: Option ids: `elevation` (required, 2D), `hillshade` (optional,
2D, prerequisite: `elevation`), `point_cloud_3d` (optional, 3D). Input type
id: `point_cloud`. `DerivedArtifact.kind` stays the artifact's format kind
(dem/hillshade/copc) — option and kind coincide today but diverge later
(e.g., an orthophoto option adds kind `ortho`).

**Rationale**: Neutral, domain-free names (Principle X); keeping `kind`
separate from `option_id` preserves the option=product / artifact=file
distinction FR-015 relies on.
