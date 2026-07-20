"""T019: GET /surveys/{id}/artifacts resolved per option (FR-016,
contracts/rest-api.md) — replaces the 001 latest-full-run dem/copc/hillshade
shape with a `products` map keyed by option id."""

import pytest

from apps.surveys.models import DerivedArtifact, ProcessingRun, RunOption, Survey

pytestmark = pytest.mark.django_db


def _survey_with_run(project, user):
    survey = Survey.objects.create(
        project=project,
        name="s.laz",
        capture_date="2026-01-01",
        source_size_bytes=1,
        source_key=f"projects/{project.id}/surveys/s/source/s.laz",
        created_by=user,
        status=Survey.Status.COMPLETED,
    )
    run = ProcessingRun.objects.create(survey=survey, number=1, state=ProcessingRun.State.COMPLETED)
    return survey, run


def test_products_map_for_subset_selection(api, project, user):
    survey, run = _survey_with_run(project, user)
    RunOption.objects.create(run=run, option_id="elevation", state=RunOption.State.COMPLETED)
    RunOption.objects.create(run=run, option_id="hillshade", state=RunOption.State.COMPLETED)
    DerivedArtifact.objects.create(
        run=run, kind="dem", option_id="elevation", storage_key="k/dem", size_bytes=1,
        sha256="a" * 64, resolution_m="0.200",
    )
    DerivedArtifact.objects.create(
        run=run, kind="hillshade", option_id="hillshade", storage_key="k/hillshade",
        size_bytes=1, sha256="b" * 64,
    )

    response = api.get(f"/api/v1/surveys/{survey.id}/artifacts")
    assert response.status_code == 200
    body = response.json()
    assert body["input_type"] == "point_cloud"
    assert set(body["products"]) == {"elevation", "hillshade"}

    elevation = body["products"]["elevation"]
    assert elevation["kind"] == "dem"
    assert elevation["run_id"] == str(run.id)
    assert "tilejson_url" in elevation and "statistics_url" in elevation

    hillshade = body["products"]["hillshade"]
    assert hillshade["kind"] == "hillshade"
    assert "tile_url_template" in hillshade and "cog_url" in hillshade


def test_not_ready_only_when_nothing_ever_completed(api, project, user):
    survey, run = _survey_with_run(project, user)
    RunOption.objects.create(run=run, option_id="elevation", state=RunOption.State.FAILED)

    response = api.get(f"/api/v1/surveys/{survey.id}/artifacts")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_ready"


def test_ready_with_at_least_one_completed_option(api, project, user):
    survey, run = _survey_with_run(project, user)
    RunOption.objects.create(run=run, option_id="elevation", state=RunOption.State.COMPLETED)
    RunOption.objects.create(run=run, option_id="hillshade", state=RunOption.State.FAILED)
    DerivedArtifact.objects.create(
        run=run, kind="dem", option_id="elevation", storage_key="k/dem", size_bytes=1,
        sha256="a" * 64, resolution_m="0.200",
    )

    response = api.get(f"/api/v1/surveys/{survey.id}/artifacts")
    assert response.status_code == 200
    assert set(response.json()["products"]) == {"elevation"}
