"""Surface-generation stage: DEM COG + hillshade COG + COPC (R2/R3/R4).

All tools run as subprocesses over local files; PDAL in stream mode and
untwine's out-of-core octree keep memory bounded for 50 GB inputs.
"""

import json
import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from pipeline.errors import StageError
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


def generate_surfaces(
    input_laz: Path, workdir: Path, resolution_m: float = DEFAULT_RESOLUTION_M
) -> list[SurfaceArtifact]:
    started = time.monotonic()
    workdir.mkdir(parents=True, exist_ok=True)
    raw_dem = workdir / "dem_raw.tif"
    dem = workdir / "dem.tif"
    hillshade_raw = workdir / "hillshade_raw.tif"
    hillshade = workdir / "hillshade.tif"
    copc = workdir / "cloud.copc.laz"

    # 1. DEM: PDAL stream-mode binning to GTiff, then COG with overviews.
    pdal_pipeline = {
        "pipeline": [
            {"type": "readers.las", "filename": str(input_laz)},
            {
                "type": "writers.gdal",
                "filename": str(raw_dem),
                "resolution": resolution_m,
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

    # 2. Hillshade from the DEM, as COG (precomputed map layer, R4).
    _run(["gdaldem", "hillshade", "-compute_edges", str(raw_dem), str(hillshade_raw)], "hillshade")
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

    # 3. COPC via untwine (out-of-core); PDAL writers.copc as fallback (R2).
    try:
        _run(["untwine", "-i", str(input_laz), "-o", str(copc)], "untwine")
    except StageError:
        logger.warning("untwine unavailable/failed; falling back to pdal writers.copc")
        _run(
            ["pdal", "translate", str(input_laz), str(copc), "--writers.copc.forward=all"],
            "pdal copc",
        )

    artifacts = [
        _artifact("dem", dem, resolution_m),
        _artifact("hillshade", hillshade, resolution_m),
        _artifact("copc", copc, None),
    ]
    logger.info(
        "surfaces ok: resolution=%.2fm duration=%.1fs", resolution_m, time.monotonic() - started
    )
    return artifacts
