"""T035: status polling shape and retry semantics (US2). T013 extends this
with per-option reuse semantics (FR-004/R5): retry creates a new run that
reuses the previous effective selection, marks already-completed options
`reused`, and only re-executes the incomplete ones."""

import pytest

from apps.surveys.models import ProcessingRun, RunOption, Survey

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


@pytest.fixture
def failed_survey_with_options(project, user):
    """A run that got as far as per-option execution: elevation + hillshade
    completed, point_cloud_3d failed — the run as a whole is failed."""
    survey = Survey.objects.create(
        project=project,
        name="vuelo2.laz",
        capture_date="2026-07-02",
        source_size_bytes=1024,
        source_key=f"projects/{project.id}/surveys/x2/source/vuelo2.laz",
        created_by=user,
        status=Survey.Status.FAILED,
    )
    run = ProcessingRun.objects.create(
        survey=survey,
        number=1,
        stage=ProcessingRun.Stage.SURFACE_GENERATION,
        state=ProcessingRun.State.FAILED,
        failure_code="internal_error",
        failure_message_key="errors.internal_error",
    )
    RunOption.objects.create(run=run, option_id="elevation", state=RunOption.State.COMPLETED)
    RunOption.objects.create(run=run, option_id="hillshade", state=RunOption.State.COMPLETED)
    RunOption.objects.create(
        run=run,
        option_id="point_cloud_3d",
        state=RunOption.State.FAILED,
        failure_code="internal_error",
        failure_message_key="errors.internal_error",
    )
    return survey, run


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


def test_retry_reuses_completed_options_and_reruns_only_the_rest(
    api, failed_survey_with_options, stub_chain
):
    survey, first_run = failed_survey_with_options

    retried = api.post(f"/api/v1/surveys/{survey.id}/retry")
    assert retried.status_code == 202
    new_run_id = retried.json()["run"]["id"]

    new_run = ProcessingRun.objects.get(id=new_run_id)
    assert new_run.number == 2
    options = {o.option_id: o for o in new_run.options.all()}
    assert set(options) == {"elevation", "hillshade", "point_cloud_3d"}

    assert options["elevation"].state == RunOption.State.REUSED
    assert options["elevation"].reused_from_id == first_run.id
    assert options["hillshade"].state == RunOption.State.REUSED
    assert options["hillshade"].reused_from_id == first_run.id

    # only the previously-failed option is scheduled to actually re-execute
    assert options["point_cloud_3d"].state == RunOption.State.PENDING

    # exactly one run_option task was chained: for point_cloud_3d only
    scheduled_option_tasks = [
        sig for sig in stub_chain[-1] if sig.name == "apps.surveys.tasks.run_option"
    ]
    assert [sig.args[1] for sig in scheduled_option_tasks] == ["point_cloud_3d"]

    # the first run's completed options are untouched (immutability of history)
    first_run.refresh_from_db()
    first_states = {o.option_id: o.state for o in first_run.options.all()}
    assert first_states["elevation"] == RunOption.State.COMPLETED
    assert first_states["hillshade"] == RunOption.State.COMPLETED
