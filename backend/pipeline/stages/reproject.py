"""Reprojection stage: PDAL stream-mode pipeline to the project CRS (R6).

Runs the ``pdal`` CLI in a subprocess; stream mode keeps memory bounded
regardless of cloud size (constitution memory budgets).
"""

import json
import logging
import subprocess
import time
from pathlib import Path

from pipeline.errors import StageError

logger = logging.getLogger(__name__)


def reproject(input_path: Path, target_crs: str, output_path: Path) -> Path:
    started = time.monotonic()
    pipeline = {
        "pipeline": [
            {"type": "readers.las", "filename": str(input_path)},
            {"type": "filters.reprojection", "out_srs": target_crs},
            {
                "type": "writers.las",
                "filename": str(output_path),
                "compression": "laszip",
                "forward": "all",
            },
        ]
    }
    proc = subprocess.run(
        ["pdal", "pipeline", "--stdin"],
        input=json.dumps(pipeline).encode(),
        capture_output=True,
    )
    if proc.returncode != 0:
        raise StageError("internal_error", f"pdal reprojection failed: {proc.stderr[-2000:]!r}")
    logger.info(
        "reprojection ok: target=%s duration=%.1fs", target_crs, time.monotonic() - started
    )
    return output_path
