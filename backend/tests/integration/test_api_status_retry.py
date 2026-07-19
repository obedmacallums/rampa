"""T035: status polling shape and retry semantics (US2)."""

import pytest

from apps.surveys.models import ProcessingRun, Survey

pytestmark = pytest.mark.django_db


@pytest.fixture
def failed_survey(project, user):
    survey = Survey.objects.create(
        project=project,
        name="vuelo1.laz",
        capture_date="2026-07-01",
        source_size_bytes=1024,
        source_key=f"projects/{project.id}/surveys/x/source/vuelo1.laz",
        created_by=user,
        status=Survey.Status.FAILED,
    )
    ProcessingRun.objects.create(
        survey=survey,
        number=1,
        stage=ProcessingRun.Stage.VALIDATION,
        state=ProcessingRun.State.FAILED,
        failure_code="missing_crs",
        failure_message_key="errors.missing_crs",
    )
    return survey


def test_detail_exposes_runs_and_failure(api, failed_survey):
    detail = api.get(f"/api/v1/surveys/{failed_survey.id}").json()
    assert detail["status"] == "failed"
    assert detail["latest_run"]["failure_code"] == "missing_crs"
    assert detail["latest_run"]["failure_message_key"] == "errors.missing_crs"
    assert [run["number"] for run in detail["runs"]] == [1]


def test_retry_creates_new_run_without_reupload(api, failed_survey, stub_chain):
    retried = api.post(f"/api/v1/surveys/{failed_survey.id}/retry")
    assert retried.status_code == 202
    assert retried.json()["run"]["number"] == 2

    failed_survey.refresh_from_db()
    assert failed_survey.status == Survey.Status.QUEUED
    # old run untouched (immutability of history)
    first = failed_survey.runs.get(number=1)
    assert first.state == ProcessingRun.State.FAILED


def test_retry_rejected_unless_failed(api, failed_survey, stub_chain):
    failed_survey.status = Survey.Status.COMPLETED
    failed_survey.save()
    response = api.post(f"/api/v1/surveys/{failed_survey.id}/retry")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_retriable"
