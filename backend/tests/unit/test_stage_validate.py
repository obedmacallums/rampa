"""T015: validation stage against synthetic fixtures (no DB, no Django)."""

import pytest

from pipeline.errors import StageError
from pipeline.stages.validate import validate_file
from tests.fixtures import make_fixtures


def test_valid_georeferenced_laz_passes(fixture_dir):
    path = make_fixtures.make_valid_laz(fixture_dir)
    result = validate_file(path)
    assert result.source_format == "laz"
    assert result.point_count == 200 * 200
    assert "32719" in result.crs_wkt or "UTM zone 19S" in result.crs_wkt
    assert len(result.sha256) == 64


def test_valid_las_reports_las_format(fixture_dir):
    path = make_fixtures.make_nocrs_las(fixture_dir)
    with pytest.raises(StageError) as exc:
        validate_file(path)
    assert exc.value.code == "missing_crs"


def test_e57_rejected_as_unsupported(fixture_dir):
    path = make_fixtures.make_fake_e57(fixture_dir)
    with pytest.raises(StageError) as exc:
        validate_file(path)
    assert exc.value.code == "unsupported_format"


def test_zip_as_las_rejected_as_unsupported(fixture_dir):
    path = make_fixtures.make_zip_as_las(fixture_dir)
    with pytest.raises(StageError) as exc:
        validate_file(path)
    assert exc.value.code == "unsupported_format"


def test_truncated_laz_rejected_as_unreadable(fixture_dir):
    path = make_fixtures.make_truncated_laz(fixture_dir)
    with pytest.raises(StageError) as exc:
        validate_file(path)
    assert exc.value.code == "unreadable_file"
