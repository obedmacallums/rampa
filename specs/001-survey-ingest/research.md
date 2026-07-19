# Phase 0 Research: Survey Ingest

All Technical Context entries were resolvable; no NEEDS CLARIFICATION markers
remained. This document records the decisions the constitution does not pin down,
with rationale and alternatives considered.

## R1. Resumable upload protocol: tus (tusd) vs S3 presigned multipart

- **Decision**: tus protocol via the stock `tusd` container with its S3 storage
  backend (MinIO in dev), fronted by the Uppy tus plugin in the browser. Completion
  notified to the backend via tusd HTTP hooks; 7-day expiry for stale uploads uses
  tusd's built-in expiration.
- **Rationale**: tus is purpose-built for resumability (FR-003, SC-002): survives
  browser/machine restarts via upload URL + offset negotiation, supports checksums,
  and requires zero custom upload code server-side. Expiration of abandoned uploads
  (FR-004) is configuration, not code. Runs as an isolated stock container, fitting
  the compose-first constraint.
- **Alternatives considered**: (a) Browser-direct S3 multipart with presigned URLs
  (Uppy AWS-S3 plugin) — fewer services, but resumability across browser restarts
  needs client-side state persistence and custom part-tracking endpoints; more
  custom code for the same guarantee. (b) Chunked upload endpoint in Django —
  violates "no sync request touches point cloud files" spirit and reinvents tus.

## R2. COPC generation: untwine vs PDAL `writers.copc`

- **Decision**: `untwine` (Hobu's out-of-core octree builder) producing COPC
  directly from the reprojected LAS/LAZ.
- **Rationale**: untwine is designed for clouds larger than RAM (constitution
  memory-budget constraint; 50 GB inputs), streams from/to disk, and is the
  reference tool for COPC creation. Potree (pinned by the constitution) loads COPC
  natively over HTTP range requests, satisfying progressive detail (FR-010b,
  SC-006).
- **Alternatives considered**: PDAL `writers.copc` — simpler pipeline integration
  but materially slower and more memory-hungry on large clouds; kept as fallback if
  untwine packaging proves problematic on arm64.

## R3. DEM generation: PDAL `writers.gdal` streaming pipeline

- **Decision**: PDAL pipeline `readers.las → filters.range (ground-relevant
  returns) → writers.gdal` (IDW/mean binning) at **0.20 m default resolution**,
  then GDAL translate/overviews to Cloud Optimized GeoTIFF (deflate, tiled,
  internal overviews). Pipeline runs in PDAL stream mode.
- **Rationale**: Stream-mode PDAL keeps memory bounded regardless of cloud size;
  0.20 m sits inside the constitution's 10–25 cm band and matches typical drone
  GSD; COG with overviews is required for client-side range-request analysis
  (Principle I/II). Ground classification/filtering beyond simple return selection
  is deliberately **not** attempted here — the DEM is a surface model; refinement
  belongs to later analysis features.
- **Alternatives considered**: (a) Configurable resolution — excluded by spec
  assumption. (b) TIN-based gridding (e.g. `filters.delaunay`) — better on sparse
  data but not streamable and memory-heavy; rejected for ingest defaults.

## R4. Hillshade: precomputed COG via `gdaldem`, served by titiler

- **Decision**: Generate `hillshade.tif` (COG) from the DEM with `gdaldem
  hillshade` at ingest; serve as XYZ tiles through the stock titiler container;
  MapLibre consumes the tile URL.
- **Rationale**: Precomputing keeps the map layer a dumb, cacheable artifact
  (immutability per run, SC-007 checksums); titiler is already the mandated tiling
  service; no server round-trips during interaction (Principle II).
- **Alternatives considered**: Client-side hillshading from the DEM COG (e.g.
  maplibre-contour/custom shader) — attractive later, but heavier first-load and
  more frontend work; the spec explicitly names terrain shading as a derived
  output, so it is materialized.

## R5. Input format scope: georeferenced LAS/LAZ only

- **Decision**: Ingest accepts only georeferenced LAS/LAZ. Validation checks
  readability and CRS presence via the LAS header EPSG/WKT VLRs; files without
  CRS metadata fail `missing_crs` — coordinates are never guessed. Any other
  content (E57, archives, images) fails `unsupported_format`.
- **Rationale**: One well-supported reader path; LAS/LAZ is the universal drone
  photogrammetry/LiDAR export and carries its CRS in-band, eliminating both the
  E57 multi-scan ambiguity and the need for a user-declared source-CRS fallback.
  User decision of 2026-07-18, superseding the earlier per-file multi-scan-E57
  rejection rule.
- **Alternatives considered**: E57 support with optional declared source CRS —
  designed, then dropped for scope; may return as its own future feature without
  touching this pipeline's contract (new format = new validation branch).

## R6. CRS catalog and reprojection

- **Decision**: A small curated CRS catalog table seeded with WGS84/UTM zones
  covering Chile and SIRGAS-Chile realizations (exact EPSG codes finalized at
  implementation against the PROJ database shipped in the image). Project stores
  one catalog entry; the reprojection stage uses PDAL `filters.reprojection` to
  the project CRS. Files whose CRS cannot be determined fail validation (never
  guessed).
- **Rationale**: Constitution demands one working CRS per project resolved at
  ingest; a curated list keeps the UI simple and avoids invalid user-typed codes.
  SIRGAS-Chile epoch particularities stay encapsulated in the catalog + PROJ.
- **Alternatives considered**: Free EPSG-code input — error-prone for the target
  user; full pyproj CRS search UI — overkill for this feature.

## R7. Authentication: Django session auth for the SPA

- **Decision**: Django's built-in user model + session cookie authentication with
  CSRF protection; SPA served same-origin (via the compose reverse proxy /
  frontend container). Endpoints: login, logout, me. Users created via Django
  admin/management command (no self-registration).
- **Rationale**: FR-015 needs simple individual accounts with no roles; sessions
  are the least code, integrate with Django admin for user provisioning, and avoid
  token-storage pitfalls. Object-storage access is always brokered (presigned or
  proxied), so one auth domain suffices.
- **Alternatives considered**: JWT (simplejwt) — unnecessary complexity and
  refresh-token handling for a same-origin SPA; self-registration — out of scope
  (site data confidentiality; operators provision accounts).

## R8. Pipeline orchestration and progress observability

- **Decision**: One Celery chain per processing run — `validate → reproject →
  generate_surfaces` (surfaces stage internally: DEM → hillshade → COPC). Each
  stage transition updates the `ProcessingRun` row (stage, state, failure reason,
  timestamps) inside the worker. Frontend polls `GET /surveys/{id}` every few
  seconds while non-terminal (satisfies SC-004 without websockets).
- **Rationale**: Persisted per-stage state survives browser and worker restarts
  (FR-006/FR-007); polling persisted metadata is squarely within the thin-backend
  principle; Celery `acks_late` + idempotent stages give crash tolerance.
- **Alternatives considered**: WebSockets/SSE push — nicer latency but adds infra
  (channels) for a ≤ 5 s freshness requirement that polling meets trivially.

## R9. Object storage layout and immutability

- **Decision**: Single bucket, key scheme:
  `projects/{project_id}/surveys/{survey_id}/source/{filename}` (uploaded file,
  relocated from the tusd staging prefix by the first asynchronous pipeline step —
  never inside the completion-hook request, per Principle III) and
  `projects/{project_id}/surveys/{survey_id}/runs/{run_id}/{dem.tif|hillshade.tif|cloud.copc.laz}`.
  Every artifact row stores size + SHA-256. Runs never write into another run's
  prefix; retry = new `run_id`.
- **Rationale**: Run-scoped prefixes make immutability (FR-011, SC-007) a
  structural property, not a discipline; checksums make SC-007 verifiable;
  source retained to enable retry without re-upload (FR-012).
- **Alternatives considered**: Overwriting a `latest/` prefix — simpler URLs but
  violates immutability; content-addressed keys — immutable but harder to browse
  and clean up per survey.

## R10. Artifact delivery to viewers

- **Decision**: DEM and COPC are fetched by the browser via short-lived presigned
  object-storage URLs issued by the backend (`GET .../artifacts` returns them);
  hillshade goes through titiler tile URLs pointing at the hillshade COG. Presigned
  URLs keep range-request support intact (COG/COPC readers require it).
- **Rationale**: Keeps auth enforcement in one place (backend issues URLs only to
  authenticated users), keeps bytes off the Django process, and preserves
  client-side range reads (Principles I/II). MinIO and S3 both honor range
  requests on presigned GETs.
- **Alternatives considered**: Public-read bucket — violates confidentiality
  assumption; proxying bytes through Django — kills range-request performance and
  bloats the thin backend.
