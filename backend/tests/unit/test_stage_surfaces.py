"""T017: surface stage against the known-truth 9% ramp (needs pdal/gdal)."""

import json
import shutil
import subprocess

import pytest

from tests.conftest import has_binary, requires_pdal
from tests.fixtures import make_fixtures


@requires_pdal
@pytest.mark.skipif(not has_binary("gdal_translate"), reason="gdal not available")
def test_ramp_dem_hillshade_copc(fixture_dir):
    from pipeline.stages.surfaces import generate_surfaces

    source = make_fixtures.make_ramp_laz(fixture_dir)
    artifacts = {a.kind: a for a in generate_surfaces(source, fixture_dir / "out", 0.20)}

    assert set(artifacts) == {"dem", "hillshade", "copc"}
    for artifact in artifacts.values():
        assert artifact.path.exists() and artifact.size_bytes > 0
        assert len(artifact.sha256) == 64

    # Known truth: mean elevation of a 9% ramp over 0..20 m in x is ~0.09*10.
    info = json.loads(
        subprocess.run(
            ["gdalinfo", "-stats", "-json", str(artifacts["dem"].path)],
            capture_output=True,
            check=True,
        ).stdout
    )
    mean = info["bands"][0]["mean"]
    assert 0.8 < mean < 1.0, f"unexpected DEM mean {mean}"


@requires_pdal
@pytest.mark.skipif(
    not (has_binary("untwine") or has_binary("pdal")), reason="no copc writer available"
)
def test_copc_readable(fixture_dir):
    import laspy

    from pipeline.stages.surfaces import generate_surfaces

    if not has_binary("gdal_translate"):
        pytest.skip("gdal not available")
    source = make_fixtures.make_ramp_laz(fixture_dir)
    artifacts = {a.kind: a for a in generate_surfaces(source, fixture_dir / "out2", 0.20)}
    with laspy.open(artifacts["copc"].path) as reader:
        assert reader.header.point_count > 0
