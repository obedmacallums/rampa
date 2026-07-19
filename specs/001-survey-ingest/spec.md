# Feature Specification: Survey Ingest

**Feature Branch**: `001-survey-ingest`

**Created**: 2026-07-18

**Status**: Draft

**Input**: User description: "Ingesta de levantamientos: como usuario de una faena minera, quiero subir el levantamiento de un vuelo de dron (nube de puntos LAS/LAZ/E57, de hasta 50 GB) a un proyecto de la plataforma, para que quede listo para visualizar y analizar sin intervención técnica de mi parte. La subida debe ser reanudable: si se corta la conexión al 90%, retomo desde donde quedó, no desde cero. Al completarse la subida, el procesamiento ocurre en segundo plano y yo puedo cerrar el navegador; al volver, veo en qué etapa va (validación, reproyección, generación de superficies) o si terminó o falló, con un mensaje de error entendible si el archivo es inválido o el formato no está soportado. Como resultado del procesamiento, el levantamiento queda disponible como: (a) una superficie de elevación lista para análisis geométrico, (b) una vista 3D de la nube navegable con detalle progresivo, (c) un sombreado del terreno como fondo de mapa, visible como capa de mapa. Cada levantamiento tiene fecha de captura y los levantamientos sucesivos de la misma faena coexisten sin sobreescribirse, porque después se compararán entre sí. Fuera de alcance en esta funcionalidad: definición de ejes, evaluación geométrica, reportes, y procesamiento de fotos crudas de dron."

## Clarifications

### Session 2026-07-18

- Q: What level of authentication does this first ingest feature include? → A: Simple
  individual accounts (sign-in required, no roles/permissions); every authenticated
  user can see all projects and upload.
- Q: Does this feature include creating and listing projects in the UI? → A: Yes,
  minimal: create a project (name + working coordinate system) and list projects.
  No project editing or deletion.
- Q: Which input formats does ingest accept? → A: Georeferenced LAS/LAZ only. E57
  was dropped from scope (decision of 2026-07-18, superseding the earlier answer
  that multi-scan E57 files would be rejected individually); E57 may return as a
  future feature.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Upload a survey and get analysis-ready results (Priority: P1)

A mining site user (surveyor, planner, or safety officer) opens a project in the
platform, uploads the point cloud file from a recent drone flight (georeferenced LAS or
LAZ, up to 50 GB), assigns it a capture date, and — without any further technical
intervention on their part — the survey ends up ready to use: an elevation surface
prepared for geometric analysis, a navigable 3D view of the cloud with progressive
detail, and a terrain shading layer usable as a 2D map background.

**Why this priority**: This is the entry point of the entire product. No centerline,
evaluation, or report can exist without an ingested survey. Delivering only this
story already produces a demonstrable product: "upload your flight, see your site in
2D and 3D."

**Independent Test**: Upload a real LAZ file to a fresh project and verify that,
after processing finishes, the elevation surface, the 3D view, and the terrain
shading layer are all available and consistent with the uploaded terrain, without
any manual step between upload and results.

**Acceptance Scenarios**:

1. **Given** a project with a declared working coordinate system, **When** the user
   uploads a valid LAZ file and assigns a capture date, **Then** the survey appears
   in the project with status "processing" and, upon completion, status "completed"
   with its three derived outputs available.
2. **Given** a completed survey, **When** the user opens the 3D view, **Then** the
   point cloud renders and is navigable, loading detail progressively as the user
   zooms in.
3. **Given** a completed survey, **When** the user opens the 2D map, **Then** the
   terrain shading of that survey is visible as a map layer over the site area.
4. **Given** a source file in a coordinate system different from the project's,
   **When** processing completes, **Then** all derived outputs are aligned to the
   project's working coordinate system with no user action required.

---

### User Story 2 - Follow progress and understand failures (Priority: P2)

After completing an upload, the user closes the browser and leaves. Processing
continues in the background. When the user returns hours later, they see at a glance
which stage the survey is in (validation, reprojection, surface generation), or that
it finished, or that it failed — and in case of failure, a message in plain language
explaining what went wrong and what to do about it.

**Why this priority**: Files of tens of GB take significant time to process. Without
visible per-stage progress and comprehensible failure messages, every slow or failed
ingest becomes a support ticket, defeating the goal of "no technical intervention".

**Independent Test**: Start processing a large file, close the session, reopen the
project and verify the current stage is displayed; separately upload a corrupt file
and an unsupported format and verify each produces a distinct, human-readable error
message with no technical jargon.

**Acceptance Scenarios**:

1. **Given** a survey being processed, **When** the user closes the browser and
   returns later, **Then** the project shows the survey's current stage (or terminal
   status) without the user having kept the session open.
2. **Given** an upload of a file with an unsupported format (e.g. a ZIP or an
   image), **When** validation runs, **Then** the survey is marked "failed" with a
   message stating that the format is not supported and listing the accepted formats.
3. **Given** an upload of a corrupt or truncated point cloud file, **When**
   validation runs, **Then** the survey is marked "failed" with a message indicating
   the file could not be read and suggesting re-exporting or re-uploading it.
4. **Given** a survey that failed in a later stage, **When** the user views it,
   **Then** the failed stage is identified and the user can retry processing without
   re-uploading the file.

---

### User Story 3 - Resume an interrupted upload (Priority: P2)

While uploading a 40 GB file over a site network, the connection drops at 90%. When
the user regains connectivity — even after restarting the browser — they resume the
upload from where it left off instead of starting over.

**Why this priority**: On mining site networks, multi-hour uploads of tens of GB
will be interrupted routinely. Without resumability the feature is unusable in the
field precisely for the realistic file sizes it targets.

**Independent Test**: Deliberately interrupt an upload past the halfway point, then
resume it and verify completion without re-sending the already-transferred portion,
and verify the resulting file is processed successfully (integrity preserved).

**Acceptance Scenarios**:

1. **Given** an upload interrupted at 90%, **When** the user resumes it, **Then**
   the transfer continues from the last confirmed portion and only the remaining
   ~10% is sent.
2. **Given** an interrupted upload, **When** the user returns after closing the
   browser or restarting the machine, **Then** the pending upload is offered for
   resumption for that same file.
3. **Given** a resumed and completed upload, **When** processing runs, **Then** the
   assembled file is bit-identical to the source (validation passes as if uploaded
   in one shot).

---

### User Story 4 - Successive surveys coexist (Priority: P3)

A site is flown monthly. Each month the user uploads a new survey to the same
project with its capture date. All surveys remain listed side by side — none
overwrites another — each with its own status, capture date, and derived outputs, so
that future features can compare them over time.

**Why this priority**: Multi-temporal comparison is a later feature, but if
coexistence and capture dates are not guaranteed from the first ingest, historical
data will be lost irrecoverably before that feature arrives.

**Independent Test**: Upload two different surveys to the same project with
different capture dates and verify both remain fully available, with independent
outputs, and that the second upload leaves the first survey's outputs untouched.

**Acceptance Scenarios**:

1. **Given** a project with one completed survey, **When** a second survey is
   uploaded, **Then** both appear in the project list, each with its own capture
   date, status, and derived outputs.
2. **Given** two surveys in a project, **When** the second one finishes processing,
   **Then** the first survey's derived outputs are unchanged.
3. **Given** a survey list, **When** the user views it, **Then** surveys are
   identifiable by capture date and name, ordered chronologically.

---

### Edge Cases

- File with no georeferencing information: validation must fail with a message
  asking the user to export the file with coordinate system metadata, rather than
  producing misplaced outputs.
- File exceeding the 50 GB limit: rejected at upload initiation with a clear
  message, not after hours of transfer.
- E57 or any other unsupported point cloud format: rejected at validation as
  unsupported, listing the accepted formats (LAS/LAZ).
- Processing failure midway (e.g. during surface generation): the survey must show
  "failed" and no partial derived output may appear as usable.
- Two uploads of the same file to the same project: both are accepted as distinct
  surveys (deduplication is not assumed); the list must let the user tell them
  apart by name and capture date.
- Abandoned incomplete uploads: partial transfers that are never resumed must not
  count as surveys nor consume storage indefinitely (expire after a defined period).
- Concurrent uploads by the same user or to the same project: allowed; progress and
  statuses are tracked per survey independently.
- User navigates to a survey whose processing was retried: they see the latest
  processing outcome, and previous outputs (if any) are never silently mutated.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST allow a user to upload georeferenced point cloud
  files in LAS and LAZ formats, up to 50 GB per file, into a project.
- **FR-002**: The system MUST reject at upload initiation any file that exceeds the
  size limit or has a file extension outside the supported set, with a message that
  states the limit and the accepted formats.
- **FR-003**: Uploads MUST be resumable: after a connection loss, browser restart,
  or machine restart, the user can resume the transfer from the last confirmed
  portion instead of restarting, and the assembled file preserves integrity.
- **FR-004**: Incomplete uploads never resumed MUST expire and be discarded after a
  defined period (default: 7 days) without becoming visible surveys.
- **FR-005**: Each survey MUST record a capture date, provided by the user at upload
  time, plus a human-readable name (defaulting to the file name).
- **FR-006**: Once the upload completes, processing MUST run entirely in the
  background: the user can close the browser and the processing state persists and
  progresses independently of any user session.
- **FR-007**: The system MUST expose per-survey processing status covering at least
  the stages "validation", "reprojection", and "surface generation", plus terminal
  states "completed" and "failed", visible whenever the user opens the project.
- **FR-008**: Validation MUST detect and reject unreadable/corrupt files,
  unsupported content, and files lacking coordinate system information, marking
  the survey "failed" with a plain-language message that states the cause and the
  corrective action (no technical jargon, no internal error traces).
- **FR-009**: Every survey MUST be automatically aligned to the project's declared
  working coordinate system during processing, with no user intervention. The
  source coordinate system is taken from the file's georeferencing metadata;
  files without it fail validation.
- **FR-010**: Successful processing MUST produce, for each survey: (a) an elevation
  surface ready for geometric analysis, (b) a navigable 3D view of the point cloud
  with progressive level of detail, and (c) a terrain shading layer usable as a 2D
  map background.
- **FR-011**: Derived outputs MUST be immutable and tied to a versioned processing
  run: reprocessing or retrying a survey produces a new set of outputs and never
  mutates or deletes previously published ones.
- **FR-012**: A survey that failed during processing MUST be retriable without
  re-uploading the source file.
- **FR-013**: Surveys within a project MUST coexist: uploading or processing one
  survey MUST NOT modify the data, status, or outputs of any other survey.
- **FR-014**: The project view MUST list all surveys with name, capture date,
  status/current stage, and file size, ordered by capture date.
- **FR-015**: The system MUST require users to sign in with an individual account
  before accessing projects or uploading surveys. All authenticated users have the
  same capabilities (no roles or per-project permissions in this feature).
- **FR-016**: Users MUST be able to create a project (name + working coordinate
  system, chosen from a supported list including Chilean reference frames) and see
  the list of existing projects. The working coordinate system is fixed at creation;
  project editing and deletion are out of scope for this feature.

### Key Entities

- **Project**: workspace for a single mining site; declares the working coordinate
  system all its surveys are aligned to. (Only the minimum needed for ingest is in
  scope: name + working coordinate system.)
- **Survey**: one uploaded flight/point cloud; has a name, capture date, source
  format, size, and a processing status. Belongs to a project; immutable once
  ingested.
- **Processing Run**: one versioned execution of the ingest pipeline over a survey;
  records per-stage progress, outcome, failure reason if any, and the outputs it
  produced. Retries create new runs.
- **Derived Output**: an immutable product of a processing run — elevation surface,
  3D visualization cloud, or terrain shading — always traceable to its run and
  survey.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user with no technical training completes the upload flow (select
  file, set capture date, start) in under 2 minutes, and needs zero manual steps
  between upload completion and seeing results.
- **SC-002**: An upload interrupted at 90% completes after resumption by
  transferring at most the missing 10% plus a negligible overhead (< 1% of the file
  re-sent).
- **SC-003**: 100% of ingest failures present the user a message that identifies
  the cause and a corrective action, with no internal technical traces.
- **SC-004**: Upon opening a project, the user can determine each survey's current
  stage or terminal status within 5 seconds, including after having closed the
  browser during processing.
- **SC-005**: For a 10 GB point cloud, all three derived outputs are available
  within 60 minutes of upload completion.
- **SC-006**: The 3D view of a completed survey becomes navigable (first points
  rendered, camera responsive) within 5 seconds of opening it, regardless of total
  cloud size.
- **SC-007**: After uploading a new survey to a project with existing surveys, the
  previously derived outputs remain byte-identical (verifiable by checksum).

## Assumptions

- Orthophoto upload (GeoTIFF) is intentionally excluded from this feature; only
  georeferenced point clouds (LAS/LAZ) are ingested. E57 and mesh formats are
  excluded here and may be added by a later feature.
- Minimal project management (create with name + working coordinate system, list)
  is part of this feature (see Clarifications); project editing/deletion and role or
  per-project permission management are out of scope — every authenticated user can
  see all projects and upload.
- The elevation surface is produced at a fixed default resolution suitable for
  geometric analysis of haul roads (in the 10–25 cm range per the project
  constitution); user-configurable resolution is out of scope for this feature.
- Capture date is entered manually by the user; extracting it from file metadata is
  a nice-to-have, not required.
- Deleting surveys is out of scope for this feature; coexistence and immutability
  are the guarantees provided.
- Site data is confidential: uploaded files and derived outputs are only reachable
  by the platform's authenticated users.
- Out of scope (per the description): centerline definition, geometric evaluation,
  reports, and processing of raw drone photos.
