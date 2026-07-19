"""T034: failure classification mapping (US2)."""

import pytest

from pipeline.errors import FAILURE_CODES, StageError
from pipeline.stages.validate import validate_file
from tests.fixtures import make_fixtures


@pytest.mark.parametrize(
    ("maker", "expected_code"),
    [
        (make_fixtures.make_zip_as_las, "unsupported_format"),
        (make_fixtures.make_fake_e57, "unsupported_format"),
        (make_fixtures.make_truncated_laz, "unreadable_file"),
        (make_fixtures.make_nocrs_las, "missing_crs"),
    ],
)
def test_classification(fixture_dir, maker, expected_code):
    with pytest.raises(StageError) as exc:
        validate_file(maker(fixture_dir))
    assert exc.value.code == expected_code
    assert exc.value.message_key == f"errors.{expected_code}"


def test_every_failure_code_has_message_key_convention():
    for code in FAILURE_CODES:
        assert " " not in code and code.islower()
