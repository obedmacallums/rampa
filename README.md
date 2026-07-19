# Rampa — Geometric Audit Platform for Mining Sites

Web platform to ingest point clouds / meshes of mining sites (typically from drone
flights), define or auto-detect haul road centerlines, evaluate them against
configurable geometric parameters (grade, curvature, berm height, roadway width,
superelevation), visualize compliance as color-coded segments (green/yellow/red), and
generate automatic reports — including per-zone reports — aligned with Chilean mining
regulations (DS 132) and fleet-based design criteria.

Road evaluation is the initial product; the same engine supports future modules within
the same site: stockpile volumetrics and multi-temporal comparison, bench and
containment-berm auditing, sight-distance analysis on curves, in-platform
photogrammetry (drone photos → point cloud/orthophoto via NodeODM), and AI-assisted
capabilities (orthophoto and point-cloud segmentation, report drafting, road
degradation prediction) — always under an assisted-detection, human-authority model.

## Architecture at a glance

- **Analysis on rasters, visualization on tiles**: all geometric computation runs
  against a DEM raster (Cloud Optimized GeoTIFF) produced at ingest; the raw cloud is
  served for visualization only (COPC / Cesium 3D Tiles).
- **Thin backend, interactive frontend**: Django + GeoDjango + DRF + PostGIS for
  ingest pipelines, persistence, and reports; all interactive analysis (threshold
  sliders, recoloring, cross-section inspection) runs client-side against the DEM COG
  via HTTP range requests.
- **Async ingest, always**: Celery + Redis pipelines, resumable uploads to
  S3-compatible object storage, versioned immutable derived artifacts.
- **Station-based evaluation model**: centerline → stations at fixed intervals →
  perpendicular cross-sections sampled from the DEM → per-station metrics →
  per-segment compliance status.
- **Evaluation profiles as data**: green/yellow/red thresholds live in versioned,
  reusable profiles tied to a design vehicle/fleet (e.g. "CAT 797F — DS 132"), never
  in code.

## Stack

| Layer | Technology |
|---|---|
| Backend | Django, GeoDjango, DRF, PostGIS |
| Workers | Celery, Redis, PDAL, GDAL, rasterio, scipy, shapely, scikit-image |
| Frontend | React, TypeScript, Zustand, MapLibre (2D), Potree (3D), terra-draw |
| Tiles / PDF | titiler (dynamic COG tiles), WeasyPrint (HTML → PDF) |
| Storage | S3-compatible object storage (MinIO in development) |
| Infra | Docker (multi-arch: linux/arm64 + linux/amd64), single `docker compose up` for local dev |

## Roadmap

1. **MVP** — ingest → DEM/COPC, manual centerline, grade + horizontal curvature,
   color-coded compliance, basic PDF report.
2. **V2** — cross-sections, width, superelevation, assisted berm detection with review
   UI, evaluation profiles, per-zone reports.
3. **V3** — automatic centerline extraction with persisted edits, DXF import/export,
   stockpile/dump volumetrics with multi-temporal DEM comparison.
4. **V4** — bench, slope, and containment-berm auditing; sight distance on curves per
   design vehicle.
5. **V5** — in-platform photogrammetry (drone photos with GCP and RTK/PPK support,
   processed via NodeODM as an isolated service).
6. **V6** — AI modules as isolated services: SAM/SAM2 orthophoto segmentation,
   point-cloud semantic segmentation, generative report drafting and query assistant,
   road degradation prediction.

## Development workflow

This project is spec-driven using [Spec Kit](https://github.com/github/spec-kit):
features follow `/speckit.specify → clarify → checklist → plan → tasks → analyze →
implement`. The project constitution — principles, technical constraints, and
governance — lives at [`.specify/memory/constitution.md`](.specify/memory/constitution.md)
and takes precedence over ad-hoc practices.

The UI and generated reports are bilingual: Spanish (primary, Chilean mining
terminology) and English. Code, identifiers, commits, and internal documentation are
written in English.
