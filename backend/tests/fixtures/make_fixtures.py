"""Synthetic known-truth fixtures (constitution Principle VIII).

Generates tiny point clouds on demand (never committed as binaries):
- ramp.laz        : 20x20 m grid, z = 9% grade along +x, EPSG:32719
- valid.laz       : alias of ramp.laz semantics, small valid georeferenced LAZ
- nocrs.las       : valid LAS without CRS metadata
- truncated.laz   : valid.laz cut right after the header (unreadable points)
- fake.e57        : E57 magic bytes (unsupported format)
- zip_as.las      : ZIP magic bytes with a .las extension
"""

from pathlib import Path

import laspy
import numpy as np
from pyproj import CRS

GRADE = 0.09  # 9% ramp: known truth for DEM assertions
SPACING = 0.1
EXTENT = 20.0
ORIGIN_X, ORIGIN_Y = 350_000.0, 6_300_000.0  # inside UTM 19S


def _ramp_points():
    coords = np.arange(0, EXTENT, SPACING)
    xx, yy = np.meshgrid(coords, coords)
    zz = GRADE * xx
    return xx.ravel() + ORIGIN_X, yy.ravel() + ORIGIN_Y, zz.ravel()


def _write_cloud(path: Path, with_crs: bool) -> Path:
    header = laspy.LasHeader(point_format=6, version="1.4")
    if with_crs:
        header.add_crs(CRS.from_epsg(32719))
    x, y, z = _ramp_points()
    header.offsets = np.array([ORIGIN_X, ORIGIN_Y, 0.0])
    header.scales = np.array([0.001, 0.001, 0.001])
    las = laspy.LasData(header)
    las.x, las.y, las.z = x, y, z
    las.write(str(path))
    return path


def make_valid_laz(directory: Path) -> Path:
    return _write_cloud(directory / "valid.laz", with_crs=True)


def make_ramp_laz(directory: Path) -> Path:
    return _write_cloud(directory / "ramp.laz", with_crs=True)


def make_nocrs_las(directory: Path) -> Path:
    return _write_cloud(directory / "nocrs.las", with_crs=False)


def make_truncated_laz(directory: Path) -> Path:
    source = _write_cloud(directory / "_full.laz", with_crs=True)
    data = source.read_bytes()
    target = directory / "truncated.laz"
    target.write_bytes(data[: 375 + 64])  # LAS 1.4 header + a stub of the VLRs
    return target


def make_fake_e57(directory: Path) -> Path:
    target = directory / "fake.e57"
    target.write_bytes(b"ASTM-E57" + b"\x00" * 128)
    return target


def make_zip_as_las(directory: Path) -> Path:
    target = directory / "zip_as.las"
    target.write_bytes(b"PK\x03\x04" + b"\x00" * 128)
    return target


if __name__ == "__main__":
    out = Path(__file__).parent / "generated"
    out.mkdir(exist_ok=True)
    for fn in (
        make_valid_laz,
        make_ramp_laz,
        make_nocrs_las,
        make_truncated_laz,
        make_fake_e57,
        make_zip_as_las,
    ):
        print(fn(out))
