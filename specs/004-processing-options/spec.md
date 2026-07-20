# Feature Specification: Selectable & Extensible Processing Options

**Feature Branch**: `004-processing-options`

**Created**: 2026-07-19

**Status**: Draft

**Input**: User description: "al subir una nube de puntos se genera un pipeline de procesamiento, actualmente se procesa solo lo que esta programado y ya, tengo pensado mas adelante crear mas opciones de procesamiento. Hay que asegurarse que exista un sistema adecuado para ir agregando estas nuevas opciones. Tambie al subir las nubes se debe escoger entre las opciones disponibles y luego enviar a procesar, entonces los resultados unos estaran en la vista 2d y otros estaran disponibles en la vista 2d. pero lo que se busca es tener asegurado el sistema o estructura para seguir agregando mas opciones, tambien revisa lo que ya se ha hecho en el piline del procesamiento actual"

## Context

Today, uploading a point cloud triggers a fixed processing sequence that always
produces the same three products: an elevation surface and a terrain-shading
layer (shown in the 2D map view) and a navigable point cloud (shown in the 3D
view). The user has no say in what gets produced, and adding a new kind of
product requires reworking the fixed sequence. This feature introduces a
catalog of **processing options**: at upload time the user chooses which
products to generate, and the platform is structured so that new options can
be added over time without disturbing the upload flow, the existing options,
or previously processed surveys. Each option's results surface in the view
where they belong (2D map layers or 3D view).

The structure must also treat the **input type** as a first-class dimension
of processing, not a hidden constant. Today every survey enters as a
georeferenced point cloud; the roadmap already commits to two more sources —
drone photos processed photogrammetrically into a point cloud/orthophoto,
and georeferenced meshes. Implementing those inputs is out of scope here,
but the catalog, the run model, and the selection flow must be laid out so
that adding a new input type later is a registration exercise, not a rework
of the options system.

## Clarifications

### Session 2026-07-19

- Q: Can the elevation surface be deselected at upload? → A: No — it is a
  required option (always generated); terrain shading and the navigable 3D
  point cloud remain optional. The catalog gains a per-input-type "required"
  flag.
- Q: How are prerequisites between options resolved when the user selects a
  dependent option without its prerequisite? → A: Visible auto-selection:
  selecting the dependent option also marks the prerequisite in the UI, both
  are part of the run's selection, and both products are published.
- Q: When one option fails, are the completed options' products discarded
  (all-or-nothing per run) or published? → A: Per-option publication:
  completed options publish their products; the run is marked failed
  identifying the failing option; retry re-executes only the failed options.
  This replaces the previous run-level all-or-nothing behavior.
- Q: When does the user choose the options — at upload start or after the
  upload completes? → A: At upload start; the selection is recorded with the
  upload and processing starts automatically with that selection when the
  upload completes, preserving the unattended upload-and-walk-away flow.
- Q: When several runs of a survey produced the same product, which version
  do the viewers show? → A: The one from the most recent completed run per
  option; earlier versions remain stored, immutable, and inspectable in the
  survey's run history.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Choose processing options when uploading (Priority: P1)

A mining site user uploads a survey to a project. When starting the upload,
they see the list of available processing options — each with a name and a
short description of what it produces and where the result will appear (2D
map or 3D view) — with the standard options preselected. They adjust the
selection and start the upload; when the upload completes, processing starts
automatically with that selection (no further confirmation needed, so
multi-hour uploads stay unattended), and when processing completes each
selected product is available in its corresponding view. Products they did
not select are not generated.

**Why this priority**: It is the user-facing core of the feature — without
selection at upload time, the catalog has no entry point. It also forces the
structural work (options as first-class catalog entries driving the run)
that everything else builds on.

**Independent Test**: Upload a file with only some options selected and
verify that exactly those products are generated, appear in their declared
views, and the unselected products are absent.

**Acceptance Scenarios**:

1. **Given** a project and a file ready to upload, **When** the user starts
   the upload, **Then** the available active options are listed with name,
   description, and target view, with default options preselected, and the
   confirmed selection is recorded with the upload.
2. **Given** a user deselects one optional product and confirms, **When**
   processing completes, **Then** the selected products appear in their
   corresponding views and the deselected product is not generated and does
   not appear anywhere.
3. **Given** the options list is shown, **When** the user reviews it, **Then**
   required options (the elevation surface) appear selected and cannot be
   deselected, and this is visually evident; deselecting every optional
   product still yields a valid submission that generates the required
   products.
4. **Given** a survey processed with a subset of options, **When** the user
   views the survey detail, **Then** they can see which options the run was
   processed with.

---

### User Story 2 - Add a new processing option without disturbing the platform (Priority: P2)

The development team adds a new processing option (for example, a contour
lines product for the 2D map). Once the new option is registered, it appears
automatically in the upload selection with its name, description, and target
view, and its results surface in the declared view — without modifying the
upload flow, the run orchestration, the storage layout, the results views,
or any previously processed survey.

**Why this priority**: It is the stated purpose of the feature ("tener
asegurado el sistema o estructura para seguir agregando más opciones"). It is
P2 only because it needs the P1 structure in place to be demonstrable.

**Independent Test**: Register a minimal test option end to end and verify it
becomes selectable, runs, and its artifact is listed under the declared view,
while existing options and previously completed surveys behave exactly as
before.

**Acceptance Scenarios**:

1. **Given** a newly registered active option, **When** a user starts a new
   upload, **Then** the option appears in the selection list without any
   change to the upload flow itself.
2. **Given** a newly registered option, **When** it is selected and the run
   completes, **Then** its product appears in the option's declared view,
   with the same progress, failure-reporting, and traceability behavior as
   the pre-existing options.
3. **Given** surveys processed before the option existed, **When** the option
   is registered, **Then** those surveys and their results are unaffected.
4. **Given** an option is deactivated, **When** a user starts a new upload,
   **Then** the option no longer appears for selection, while artifacts it
   produced in past runs remain available.

---

### User Story 3 - Process additional options on an existing survey (Priority: P3)

A user realizes after processing that they need a product they did not select
(or a new option was added after their survey was processed). From the survey
detail they choose the additional options and send the survey to reprocess
using the already-uploaded file — no re-upload — producing a new versioned
run whose products join the survey's results.

**Why this priority**: High convenience value (files are tens of GB) but the
feature is viable without it — the user can re-upload as a workaround.

**Independent Test**: On a completed survey, request one additional option
and verify a new run generates only that product, previous artifacts remain
untouched, and no re-upload occurs.

**Acceptance Scenarios**:

1. **Given** a completed survey, **When** the user requests additional
   options, **Then** the original file stored in the platform is reused and
   the user does not upload anything again.
2. **Given** an additional-options run completes, **When** the user views the
   survey, **Then** the new products appear alongside the earlier ones and
   the earlier ones are unchanged; if a product was re-generated, the viewers
   show the most recent completed version (FR-016).

---

### Edge Cases

- User deselects all optional products: submission remains valid — required
  options (the elevation surface) are always included, so every run produces
  at least the analysis-ready surface (constitution Principle I).
- A selected option's processing fails: the run is marked failed identifying
  the failing option with an understandable message; options that completed
  keep their published products, and no option ever publishes partial
  products of its own.
- An option whose product derives from another option's product (e.g.,
  terrain shading derives from the elevation surface): selecting the
  dependent auto-selects the prerequisite visibly in the UI (FR-006) — the
  user's selection never produces a run that is missing an input it needs.
- Retry of a failed run: reuses the exact option selection of the failed run
  and re-executes only the options that did not complete.
- An option is deactivated between the user opening the upload dialog and
  starting the upload: the start is rejected with a clear message and the
  user re-submits with a valid selection. Once an upload has started, its
  recorded selection stays honored even if an option is deactivated before
  the upload completes (deactivation only affects new selections, FR-008) —
  a multi-hour upload is never invalidated retroactively.
- A survey processed before this feature exists (no recorded selection): its
  results remain visible, treated as having been processed with the standard
  options of the time.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST maintain a catalog of processing options where
  each option declares at minimum: a stable identifier, a user-visible name
  and description (available in Spanish and English), the input types it
  applies to, the view where its results surface (2D map or 3D view),
  whether it is required for a given input type (always generated, shown as
  non-deselectable), whether it is preselected by default, and whether it is
  active. The elevation surface is required for the point-cloud input type.
- **FR-002**: The upload flow MUST present the active options when the user
  starts an upload, with default options preselected; the confirmed
  selection is recorded with the upload and processing starts automatically
  with it when the upload completes, without further user confirmation.
  Required options MUST be shown as selected and non-deselectable, and MUST
  be included in every run regardless of user input.
- **FR-003**: A processing run MUST execute only the options selected for it.
  File validation and reprojection to the project coordinate system are
  mandatory preparation steps of every run, not user-selectable options.
- **FR-004**: The option selection MUST be persisted per run, be visible to
  the user in the survey detail, and be reused as-is when a failed run is
  retried. A retry re-executes only the options that did not complete,
  keeping the already-published products of the same selection.
- **FR-005**: Every generated product MUST be traceable to the option and the
  run that produced it, and MUST be surfaced in the view (2D map layers or
  3D view) declared by its option.
- **FR-006**: The system MUST support options whose products derive from
  other options' products. Selecting a dependent option automatically
  selects its prerequisites, visibly, before submission; the prerequisites
  become part of the run's selection and their products are published like
  any other. Deselecting a prerequisite deselects (or blocks) its dependents,
  so a valid selection can never yield a run with missing inputs.
- **FR-007**: Adding a new processing option MUST require only registering
  the option (its declaration plus its processing routine) — with no changes
  to the upload flow, run orchestration, progress tracking, failure
  reporting, storage layout, or results views, and no effect on previously
  processed surveys.
- **FR-008**: Deactivating an option MUST remove it from new-upload selection
  without affecting products it generated in past runs.
- **FR-009**: Publication is per option: each option's products are
  published when that option completes successfully, and an option never
  publishes partial products of its own. When a selected option fails, the
  run MUST be marked failed identifying the failing option with an
  understandable, translated message; products of options that completed
  remain published and usable.
- **FR-010**: The user MUST be able to follow run progress at the level of
  the selected options (which are pending, running, completed, or failed),
  surviving browser and platform restarts as today.
- **FR-011**: Users MUST be able to request additional options on an
  already-processed survey reusing the stored original file (no re-upload),
  producing a new versioned run; earlier runs and their products are
  immutable.
- **FR-012**: Surveys processed before this feature MUST keep their results
  visible and consistent, treated as runs of the then-standard options.
- **FR-013**: The system MUST model the input type of every survey and run
  explicitly. The only input type in scope is the georeferenced point cloud,
  but the structure MUST allow registering future input types (e.g., drone
  photo sets processed photogrammetrically, georeferenced meshes) — each
  with its own mandatory preparation steps and its own subset of applicable
  options — without reworking the catalog, the selection flow, the run
  model, or existing surveys.
- **FR-014**: The upload selection MUST offer only the options applicable to
  the input type being uploaded, so future input types can coexist with
  point clouds without confusing the user with inapplicable products.
- **FR-015**: A processing option MUST be defined by the product it delivers
  (what the user receives and where it appears), never by how the product is
  produced. The same option MAY be fulfilled by a different production route
  per input type, and a single internal processing step MAY fulfill several
  selected options at once (e.g., a future photogrammetric engine emits an
  elevation surface, an orthophoto, and a point cloud in one execution). The
  user-facing contract — select products, receive exactly those products in
  their declared views, with per-option progress and failure attribution —
  MUST hold regardless of the route.
- **FR-016**: When a survey holds the same product from several runs, the
  viewers MUST surface the version from the most recent completed run for
  each option; earlier versions remain stored and immutable, and the survey
  detail MUST let the user see which run produced the currently displayed
  product.

### Key Entities

- **Input Type**: The kind of source data a survey enters the platform with.
  Only one exists in this feature — the georeferenced point cloud — but it
  is modeled explicitly so future types (drone photo sets, georeferenced
  meshes) register alongside it, each declaring its mandatory preparation
  steps and which processing options apply to it.
- **Processing Option**: A catalog entry describing a product the platform
  can generate from an uploaded survey — identifier, bilingual
  name/description, applicable input types, target view (2D/3D), required
  flag (per input type), default and active flags, and any prerequisite
  options. It names the deliverable, not
  the procedure: per input type it is bound to a production route, and
  several options may share one route. The current elevation surface,
  terrain shading, and navigable point cloud become the initial catalog
  entries, all applicable to the point-cloud input type.
- **Option Selection**: The set of options chosen for a specific processing
  run; recorded with the run for traceability and retry.
- **Processing Run** *(existing)*: A versioned execution of the pipeline for
  a survey; extended to carry its input type, its option selection, and
  per-option progress.
- **Derived Product** *(existing)*: An output of a run; extended to be
  attributable to the option that produced it and routed to that option's
  declared view.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can review and adjust the processing selection and send
  a survey to process in under 1 additional minute compared to the current
  upload flow.
- **SC-002**: 100% of newly generated products are attributable to a specific
  option and run, and appear in the view their option declares.
- **SC-003**: A new processing option can be introduced and become available
  to users without any modification of the upload flow, results views, or
  previously processed surveys — verified by adding one new option end to
  end.
- **SC-004**: At least 90% of users locate each generated product in the
  expected view on first attempt (2D map layer vs 3D view) in usability
  checks.
- **SC-005**: Requesting additional products on an existing survey requires
  zero re-uploads of the source file.
- **SC-006**: 100% of failed runs communicate which option failed in language
  the user understands (Spanish or English), without exposing internal
  details.

## Assumptions

- The user description says results go "unos en la vista 2d y otros en la
  vista 2d"; this is interpreted as **2D and 3D**, matching the platform's
  existing viewers (elevation/shading layers in the 2D map, point cloud in
  the 3D view).
- The three products of the current fixed pipeline become the initial
  catalog: elevation surface (2D, required — every survey stays
  analysis-ready per constitution Principle I), terrain shading (2D, derived
  from the elevation surface, optional), and navigable point cloud (3D,
  optional). All three are active and preselected by default, so the default
  experience matches today's behavior.
- File validation and reprojection to the project coordinate system are
  mandatory preparation steps, never user-selectable options (they guarantee
  every product is in the project's coordinate system).
- New options are introduced by the development team as platform releases
  (declaration + processing routine), not authored by end users or
  administrators through a UI. A management UI for the catalog is out of
  scope.
- Option selection happens per uploaded file (per survey), at upload start;
  it travels with the upload session so processing can start unattended when
  the upload completes (uploads take hours and must not wait for the user to
  return and confirm).
- Publication atomicity moves from the run to the option (2026-07-19
  clarification): each option publishes all of its products or none, but a
  run may end with a mix of completed (published) and failed (unpublished)
  options. This supersedes the previous run-level "never publish partial
  artifacts" behavior; the invariant that no artifact is ever half-published
  is preserved at the option level.
- Results whose natural home is neither viewer (e.g., future downloadable
  reports/files) are out of scope for this feature; the catalog's target
  views are 2D and 3D for now, though the structure should not preclude
  adding other targets later.
- Future input types are anticipated structurally but not implemented:
  photogrammetric processing of drone photo sets (roadmap phase V5, via an
  isolated photogrammetry service whose outputs enter this same product
  pipeline) and georeferenced meshes. This feature only guarantees that the
  input type is modeled explicitly (FR-013/FR-014) so those arrivals are
  registrations, not rework; their upload flows, preparation steps, and
  specific options will be specified in their own features.
- Production routes are expected to differ per input type for the same
  product. For a point cloud, 2D products are derived step by step from the
  cloud; for photos, the photogrammetric engine natively emits several
  deliverables (elevation surface, orthophoto, point cloud, mesh) in a
  single execution. FR-015 keeps the catalog stable across both worlds: the
  option is the product, the route is an internal binding per input type,
  and one route may satisfy many options. Whether an internally co-produced
  but unselected deliverable is discarded or stored is a per-route decision
  deferred to each input type's own feature.
- Out of scope: changes to axis definition, geometric evaluation, reports,
  and the actual implementation of photogrammetric or mesh ingestion (future
  roadmap phases); this feature only restructures how ingest products are
  selected, generated, and surfaced.
