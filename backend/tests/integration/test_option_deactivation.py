"""T027: option deactivation (FR-008 + edge case) — an inactive option is
absent from the catalog and rejected on a new selection; historical runs and
artifacts stay served exactly as before; retry of a run that includes the
now-inactive option is still allowed (deactivation only blocks new selections)."""

import pytest

from apps.surveys.models import DerivedArtifact, ProcessingRun, RunOption, Survey
from pipeline import options as registry

pytestmark = pytest.mark.django_db


@pytest.fixture
def deprecated_option():
    spec = registry.OptionSpec(
        id="legacy_flag",
        label_key="options.legacy_flag.label",
        description_key="options.legacy_flag.description",
        input_types=frozenset({"point_cloud"}),
        target_view="map2d",
        required=False,
        default_selected=False,
        active=False,
        prerequisites=(),
        producer=lambda ctx: {},
    )
    registry.register_option(spec)
    registry.validate_registry()
    yield spec
    del registry._options["legacy_flag"]


def test_inactive_option_absent_from_catalog(api, deprecated_option):
    catalog = api.get("/api/v1/processing-options").json()
    assert "legacy_flag" not in {o["id"] for o in catalog["options"]}


def test_inactive_option_rejected_on_new_initiation(api, project, deprecated_option):
    response = api.post(
        f"/api/v1/projects/{project.id}/uploads",
        {
            "filename": "v.laz",
            "size_bytes": 1,
            "capture_date": "2026-07-01",
            "selected_options": ["legacy_flag"],
        },
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_options"
    assert response.json()["error"]["detail"]["invalid"] == ["legacy_flag"]


def test_historical_artifacts_still_served(api, project, user, deprecated_option):
    survey = Survey.objects.create(
        project=project,
        name="s.laz",
        capture_date="2026-01-01",
        source_size_bytes=1,
        source_key=f"projects/{project.id}/surveys/s/source/s.laz",
        created_by=user,
        status=Survey.Status.COMPLETED,
    )
    run = ProcessingRun.objects.create(
        survey=survey, number=1, state=ProcessingRun.State.COMPLETED
    )
    RunOption.objects.create(run=run, option_id="legacy_flag", state=RunOption.State.COMPLETED)
    DerivedArtifact.objects.create(
        run=run,
        kind="legacy_flag",
        option_id="legacy_flag",
        storage_key="k/legacy",
        size_bytes=1,
        sha256="a" * 64,
    )

    detail = api.get(f"/api/v1/surveys/{survey.id}").json()
    option_ids = {o["option_id"] for o in detail["runs"][0]["options"]}
    assert "legacy_flag" in option_ids

    products = api.get(f"/api/v1/surveys/{survey.id}/artifacts").json()["products"]
    assert "legacy_flag" in products


def test_retry_of_run_with_now_inactive_option_still_allowed(
    api, project, user, deprecated_option, stub_chain
):
    survey = Survey.objects.create(
        project=project,
        name="s2.laz",
        capture_date="2026-01-02",
        source_size_bytes=1,
        source_key=f"projects/{project.id}/surveys/s2/source/s2.laz",
        created_by=user,
        status=Survey.Status.FAILED,
    )
    run = ProcessingRun.objects.create(
        survey=survey,
        number=1,
        state=ProcessingRun.State.FAILED,
        failure_code="internal_error",
        failure_message_key="errors.internal_error",
    )
    RunOption.objects.create(run=run, option_id="elevation", state=RunOption.State.COMPLETED)
    RunOption.objects.create(
        run=run,
        option_id="legacy_flag",
        state=RunOption.State.FAILED,
        failure_code="internal_error",
        failure_message_key="errors.internal_error",
    )

    response = api.post(f"/api/v1/surveys/{survey.id}/retry")

    assert response.status_code == 202
    new_run = ProcessingRun.objects.get(survey=survey, number=2)
    options = {o.option_id: o for o in new_run.options.all()}
    assert set(options) == {"elevation", "legacy_flag"}
    assert options["elevation"].state == RunOption.State.REUSED
    # wasn't completed before -> re-executes despite being inactive now
    assert options["legacy_flag"].state == RunOption.State.PENDING
