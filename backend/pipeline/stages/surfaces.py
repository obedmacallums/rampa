"""Per-option surface producers: elevation (DEM COG), hillshade (COG), 3D
point cloud (COPC) — one function per processing option (data-model.md, R4).

All tools run as subprocesses over local files; PDAL in stream mode and
untwine's out-of-core octree keep memory bounded for 50 GB inputs. Producers
never upload — the per-option task wrapper (apps.surveys.tasks) publishes
only after every artifact is fully materialized and checksummed.
"""

import json
import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from pipeline.errors import StageError
from pipeline.stages.context import RunContext
from pipeline.storage import sha256_of_file

logger = logging.getLogger(__name__)

DEFAULT_RESOLUTION_M = 0.20


@dataclass
class SurfaceArtifact:
    kind: str  # "dem" | "hillshade" | "copc"
    path: Path
    sha256: str
    size_bytes: int
    resolution_m: float | None


def _run(cmd: list[str], step: str, stdin: bytes | None = None) -> None:
    try:
        proc = subprocess.run(cmd, input=stdin, capture_output=True)
    except FileNotFoundError as exc:
        raise StageError("internal_error", f"{step}: binary not found: {cmd[0]}") from exc
    if proc.returncode != 0:
        raise StageError("internal_error", f"{step} failed: {proc.stderr[-2000:]!r}")


def _artifact(kind: str, path: Path, resolution: float | None) -> SurfaceArtifact:
    return SurfaceArtifact(
        kind=kind,
        path=path,
        sha256=sha256_of_file(path),
        size_bytes=path.stat().st_size,
        resolution_m=resolution,
    )


def produce_elevation(ctx: RunContext) -> SurfaceArtifact:
    """DEM: PDAL stream-mode binning to GTiff, then COG with overviews.

    Fulfills option `elevation`.
    """
    started = time.monotonic()
    ctx.workdir.mkdir(parents=True, exist_ok=True)
    raw_dem = ctx.workdir / "dem_raw.tif"
    dem = ctx.workdir / "dem.tif"

    pdal_pipeline = {
        "pipeline": [
            {"type": "readers.las", "filename": str(ctx.input_laz)},
            {
                "type": "writers.gdal",
                "filename": str(raw_dem),
                "resolution": ctx.resolution_m,
                "output_type": "mean",
                "gdaldriver": "GTiff",
                "nodata": -9999,
                "data_type": "float32",
            },
        ]
    }
    _run(["pdal", "pipeline", "--stdin"], "pdal dem", stdin=json.dumps(pdal_pipeline).encode())
    _run(
        ["gdal_translate", "-of", "COG", "-co", "COMPRESS=DEFLATE", str(raw_dem), str(dem)],
        "dem cog",
    )

    artifact = _artifact("dem", dem, ctx.resolution_m)
    logger.info(
        "elevation ok: resolution=%.2fm duration=%.1fs",
        ctx.resolution_m,
        time.monotonic() - started,
    )
    return artifact


def produce_hillshade(ctx: RunContext, dem_path: Path) -> SurfaceArtifact:
    """Hillshade from an elevation DEM (the `elevation` option's artifact, its
    within-run prerequisite).

    Fulfills option `hillshade`.
    """
    started = time.monotonic()
    ctx.workdir.mkdir(parents=True, exist_ok=True)
    hillshade_raw = ctx.workdir / "hillshade_raw.tif"
    hillshade = ctx.workdir / "hillshade.tif"

    _run(
        ["gdaldem", "hillshade", "-compute_edges", str(dem_path), str(hillshade_raw)], "hillshade"
    )
    _run(
        [
            "gdal_translate",
            "-of",
            "COG",
            "-co",
            "COMPRESS=DEFLATE",
            str(hillshade_raw),
            str(hillshade),
        ],
        "hillshade cog",
    )

    artifact = _artifact("hillshade", hillshade, ctx.resolution_m)
    logger.info("hillshade ok: duration=%.1fs", time.monotonic() - started)
    return artifact


def produce_point_cloud_3d(ctx: RunContext) -> SurfaceArtifact:
    """COPC via untwine (out-of-core); PDAL writers.copc as fallback.

    Fulfills option `point_cloud_3d`.
    """
    started = time.monotonic()
    ctx.workdir.mkdir(parents=True, exist_ok=True)
    copc = ctx.workdir / "cloud.copc.laz"

    try:
        _run(["untwine", "-i", str(ctx.input_laz), "-o", str(copc)], "untwine")
    except StageError:
        logger.warning("untwine unavailable/failed; falling back to pdal writers.copc")
        _run(
            ["pdal", "translate", str(ctx.input_laz), str(copc), "--writers.copc.forward=all"],
            "pdal copc",
        )

    artifact = _artifact("copc", copc, None)
    logger.info("point_cloud_3d ok: duration=%.1fs", time.monotonic() - started)
    return artifact


# --- Registry producer adapters (T005) -------------------------------------
#
# Uniform `producer(ctx) -> dict[option_id, SurfaceArtifact]` signature the
# orchestrator (apps.surveys.tasks.run_option) calls generically. A producer
# MAY return artifacts for more than one option from a single execution
# (FR-015) — e.g. a future photogrammetry route emitting DEM + orthophoto +
# cloud together; the wrapper publishes every option id it finds pending in
# the current run.


def elevation_producer(ctx: RunContext) -> dict[str, SurfaceArtifact]:
    return {"elevation": produce_elevation(ctx)}


def hillshade_producer(ctx: RunContext) -> dict[str, SurfaceArtifact]:
    return {"hillshade": produce_hillshade(ctx, ctx.artifacts["elevation"])}


def point_cloud_3d_producer(ctx: RunContext) -> dict[str, SurfaceArtifact]:
    return {"point_cloud_3d": produce_point_cloud_3d(ctx)}
