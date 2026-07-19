"""T019: real-LAZ end-to-end ingest (constitution: every ingest change is
validated against at least one real LAZ sample).

Run inside the worker image (pdal/gdal/untwine present) with:
    pytest tests/integration -m real_laz --laz-sample /samples/flight.laz
"""

from pathlib import Path

import pytest

from tests.conftest import has_binary

pytestmark = [pytest.mark.django_db, pytest.mark.real_laz]


@pytest.mark.skipif(not has_binary("pdal"), reason="pdal binary not available")
def test_real_laz_full_pipeline(request, tmp_path, project):
    from pipeline.stages.reproject import reproject
    from pipeline.stages.surfaces import generate_surfaces
    from pipeline.stages.validate import validate_file

    sample = Path(request.config.getoption("--laz-sample"))
    assert sample.exists(), f"sample not found: {sample}"

    result = validate_file(sample)
    assert result.point_count > 0
    assert result.crs_wkt

    reprojected = reproject(sample, project.crs.code, tmp_path / "reproj.laz")
    artifacts = {a.kind: a for a in generate_surfaces(reprojected, tmp_path / "out")}
    assert set(artifacts) == {"dem", "hillshade", "copc"}
    for artifact in artifacts.values():
        assert artifact.path.exists() and artifact.size_bytes > 0

    # reproducibility: a second run over the same input yields identical checksums
    again = {a.kind: a for a in generate_surfaces(reprojected, tmp_path / "out_again")}
    assert {k: a.sha256 for k, a in again.items()} == {
        k: a.sha256 for k, a in artifacts.items()
    }
