"""T031: additional options on an existing survey (US3, SC-005) — reuses the
stored source file, no re-upload; only the newly requested option executes,
previously completed ones become `reused` and stay untouched."""

import pytest

from apps.surveys.models import DerivedArtifact, ProcessingRun, RunOption, Survey, UploadSession
from tests.conftest import run_chain

pytestmark = pytest.mark.django_db


@pytest.fixture
def completed_survey(project, user):
    survey = Survey.objects.create(
        project=project,
        name="s.laz",
        capture_date="2026-01-01",
        source_size_bytes=1024,
        source_key=f"projects/{project.id}/surveys/s/source/s.laz",
        created_by=user,
        status=Survey.Status.COMPLETED,
    )
    run = ProcessingRun.objects.create(
        survey=survey, number=1, state=ProcessingRun.State.COMPLETED
    )
    RunOption.objects.create(run=run, option_id="elevation", state=RunOption.State.COMPLETED)
    RunOption.objects.create(run=run, option_id="hillshade", state=RunOption.State.COMPLETED)
    DerivedArtifact.objects.create(
        run=run,
        kind="dem",
        option_id="elevation",
        storage_key="k/dem",
        size_bytes=1,
        sha256="a" * 64,
        resolution_m="0.200",
    )
    DerivedArtifact.objects.create(
        run=run,
        kind="hillshade",
        option_id="hillshade",
        storage_key="k/hillshade",
        size_bytes=1,
        sha256="b" * 64,
    )
    return survey, run


def test_additional_option_executes_only_new_option(
    api, completed_survey, stub_chain, fake_pipeline
):
    survey, first_run = completed_survey

    response = api.post(
        f"/api/v1/surveys/{survey.id}/process",
        {"selected_options": ["point_cloud_3d"]},
        content_type="application/json",
    )
    assert response.status_code == 202
    new_run_id = response.json()["run"]["id"]

    new_run = ProcessingRun.objects.get(id=new_run_id)
    assert new_run.number == 2
    options = {o.option_id: o for o in new_run.options.all()}
    assert set(options) == {"elevation", "hillshade", "point_cloud_3d"}
    assert options["elevation"].state == RunOption.State.REUSED
    assert options["elevation"].reused_from_id == first_run.id
    assert options["hillshade"].state == RunOption.State.REUSED
    assert options["hillshade"].reused_from_id == first_run.id
    assert options["point_cloud_3d"].state == RunOption.State.PENDING

    run_chain(stub_chain)
    new_run.refresh_from_db()
    assert new_run.state == ProcessingRun.State.COMPLETED
    assert new_run.options.get(option_id="point_cloud_3d").state == RunOption.State.COMPLETED

    # previous run's artifacts untouched
    first_run.refresh_from_db()
    assert {a.option_id: a.sha256 for a in first_run.artifacts.all()} == {
        "elevation": "a" * 64,
        "hillshade": "b" * 64,
    }

    # /artifacts resolves the union across runs (FR-016)
    products = api.get(f"/api/v1/surveys/{survey.id}/artifacts").json()["products"]
    assert set(products) == {"elevation", "hillshade", "point_cloud_3d"}
    assert products["elevation"]["run_id"] == str(first_run.id)
    assert products["hillshade"]["run_id"] == str(first_run.id)
    assert products["point_cloud_3d"]["run_id"] == str(new_run.id)

    # no upload session involved (SC-005)
    assert UploadSession.objects.count() == 0


def test_invalid_options_rejected(api, completed_survey):
    survey, _ = completed_survey
    response = api.post(
        f"/api/v1/surveys/{survey.id}/process",
        {"selected_options": ["nope"]},
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_options"


def test_not_processable_while_run_in_progress(api, completed_survey):
    survey, _ = completed_survey
    survey.status = Survey.Status.PROCESSING
    survey.save()
    response = api.post(
        f"/api/v1/surveys/{survey.id}/process",
        {"selected_options": ["point_cloud_3d"]},
        content_type="application/json",
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_processable"
