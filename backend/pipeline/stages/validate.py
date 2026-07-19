"""Validation stage: pure function over a local file (no Django imports).

Checks content format (LAS/LAZ by magic + header parse), readability, and CRS
presence in the header VLRs (FR-008). Coordinates are never guessed: a file
without CRS metadata fails ``missing_crs``.
"""

import logging
import time
from dataclasses import dataclass
from pathlib import Path

import laspy

from pipeline.errors import StageError
from pipeline.storage import sha256_of_file

logger = logging.getLogger(__name__)

LAS_MAGIC = b"LASF"


@dataclass
class ValidationResult:
    source_format: str  # "las" | "laz"
    point_count: int
    crs_wkt: str
    sha256: str


def validate_file(path: Path) -> ValidationResult:
    started = time.monotonic()
    try:
        magic = path.open("rb").read(4)
    except OSError as exc:
        raise StageError("unreadable_file", str(exc)) from exc

    if magic != LAS_MAGIC:
        raise StageError("unsupported_format", f"magic={magic!r}")

    try:
        with laspy.open(path) as reader:
            header = reader.header
            # Force a real read of the first chunk to catch truncated files.
            next(reader.chunk_iterator(10_000), None)
            crs = header.parse_crs()
            point_count = header.point_count
    except StageError:
        raise
    except Exception as exc:
        raise StageError("unreadable_file", str(exc)) from exc

    if crs is None:
        raise StageError("missing_crs", "no CRS VLR in header")

    result = ValidationResult(
        source_format="laz" if path.suffix.lower() == ".laz" else "las",
        point_count=point_count,
        crs_wkt=crs.to_wkt(),
        sha256=sha256_of_file(path),
    )
    logger.info(
        "validation ok: format=%s points=%d duration=%.1fs",
        result.source_format,
        result.point_count,
        time.monotonic() - started,
    )
    return result
