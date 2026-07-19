"""T016: reprojection stage — requires the pdal binary (runs in the image)."""

import laspy

from tests.conftest import requires_pdal
from tests.fixtures import make_fixtures


@requires_pdal
def test_reprojects_to_target_crs(fixture_dir):
    from pipeline.stages.reproject import reproject

    source = make_fixtures.make_ramp_laz(fixture_dir)  # EPSG:32719
    output = reproject(source, "EPSG:32718", fixture_dir / "out.laz")

    with laspy.open(output) as reader:
        crs = reader.header.parse_crs()
        assert crs is not None and crs.to_epsg() == 32718
        # UTM 18S easting for this longitude sits far east of the 19S values.
        chunk = next(reader.chunk_iterator(1000))
        assert abs(chunk.x[0] - make_fixtures.ORIGIN_X) > 100_000
