"""T004: per-option surface producers against the known-truth 9% ramp (needs pdal/gdal)."""

import json
import subprocess
from pathlib import Path

import pytest

from pipeline.stages.context import RunContext
from tests.conftest import has_binary, requires_pdal
from tests.fixtures import make_fixtures


@requires_pdal
@pytest.mark.skipif(not has_binary("gdal_translate"), reason="gdal not available")
def test_produce_elevation_dem(fixture_dir):
    from pipeline.stages.surfaces import produce_elevation

    source = make_fixtures.make_ramp_laz(fixture_dir)
    ctx = RunContext(workdir=fixture_dir / "out", input_laz=source, resolution_m=0.20)
    artifact = produce_elevation(ctx)

    assert artifact.kind == "dem"
    assert artifact.path.exists() and artifact.size_bytes > 0
    assert len(artifact.sha256) == 64

    # Known truth: mean elevation of a 9% ramp over 0..20 m in x is ~0.09*10.
    info = json.loads(
        subprocess.run(
            ["gdalinfo", "-stats", "-json", str(artifact.path)],
            capture_output=True,
            check=True,
        ).stdout
    )
    mean = info["bands"][0]["mean"]
    assert 0.8 < mean < 1.0, f"unexpected DEM mean {mean}"


@requires_pdal
@pytest.mark.skipif(not has_binary("gdal_translate"), reason="gdal not available")
def test_produce_hillshade_consumes_dem_artifact(fixture_dir):
    from pipeline.stages.surfaces import produce_elevation, produce_hillshade

    source = make_fixtures.make_ramp_laz(fixture_dir)
    ctx = RunContext(workdir=fixture_dir / "out", input_laz=source, resolution_m=0.20)
    dem = produce_elevation(ctx)

    hillshade = produce_hillshade(ctx, dem.path)

    assert hillshade.kind == "hillshade"
    assert hillshade.path.exists() and hillshade.size_bytes > 0
    assert len(hillshade.sha256) == 64


@requires_pdal
@pytest.mark.skipif(
    not (has_binary("untwine") or has_binary("pdal")), reason="no copc writer available"
)
def test_produce_point_cloud_3d_readable(fixture_dir):
    import laspy

    from pipeline.stages.surfaces import produce_point_cloud_3d

    source = make_fixtures.make_ramp_laz(fixture_dir)
    ctx = RunContext(workdir=fixture_dir / "out", input_laz=source, resolution_m=0.20)
    artifact = produce_point_cloud_3d(ctx)

    with laspy.open(artifact.path) as reader:
        assert reader.header.point_count > 0


@requires_pdal
def test_produce_point_cloud_3d_falls_back_to_pdal_when_untwine_fails(fixture_dir, monkeypatch):
    from pipeline.stages import surfaces

    if not has_binary("pdal"):
        pytest.skip("pdal not available")

    calls = []
    real_run = surfaces._run

    def fake_run(cmd, step, stdin=None):
        calls.append(step)
        if step == "untwine":
            raise surfaces.StageError("internal_error", "forced failure")
        return real_run(cmd, step, stdin=stdin)

    monkeypatch.setattr(surfaces, "_run", fake_run)

    source = make_fixtures.make_ramp_laz(fixture_dir)
    ctx = RunContext(workdir=fixture_dir / "out", input_laz=source, resolution_m=0.20)
    artifact = surfaces.produce_point_cloud_3d(ctx)

    assert "untwine" in calls
    assert "pdal copc" in calls
    assert artifact.path.exists()


def test_elevation_producer_adapter_returns_option_keyed_dict(monkeypatch):
    from pipeline.stages import surfaces

    sentinel = surfaces.SurfaceArtifact(
        kind="dem",
        path=Path("/tmp/dem.tif"),
        sha256="a" * 64,
        size_bytes=1,
        resolution_m=0.2,
    )
    monkeypatch.setattr(surfaces, "produce_elevation", lambda ctx: sentinel)
    ctx = RunContext(workdir=Path("/tmp"), input_laz=Path("/tmp/in.laz"), resolution_m=0.2)

    result = surfaces.elevation_producer(ctx)

    assert result == {"elevation": sentinel}


def test_hillshade_producer_adapter_uses_elevation_prerequisite(monkeypatch):
    from pipeline.stages import surfaces

    dem_path = Path("/tmp/dem.tif")
    sentinel = surfaces.SurfaceArtifact(
        kind="hillshade", path=Path("/tmp/hillshade.tif"), sha256="b" * 64, size_bytes=1,
        resolution_m=0.2,
    )
    seen = {}

    def fake_produce_hillshade(ctx, dem):
        seen["dem"] = dem
        return sentinel

    monkeypatch.setattr(surfaces, "produce_hillshade", fake_produce_hillshade)
    ctx = RunContext(
        workdir=Path("/tmp"),
        input_laz=Path("/tmp/in.laz"),
        resolution_m=0.2,
        artifacts={"elevation": dem_path},
    )

    result = surfaces.hillshade_producer(ctx)

    assert result == {"hillshade": sentinel}
    assert seen["dem"] == dem_path
