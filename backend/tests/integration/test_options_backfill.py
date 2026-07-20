"""T008: backfill migration (FR-012, R6) — pre-004 rows get correct per-option
attribution and RunOption history; survey endpoints keep serving them
afterward.

Rows are built against the schema as it existed right after migration 0003
(option_id still nullable, no RunOption history yet) via Django's migration
executor — the schema change itself (0003) and the NOT NULL promotion (0005,
T033) are exercised for real by `migrate` running clean in CI/T006, so this
test targets the 0004 data transform specifically, against genuinely
nullable rows, the same way it runs against a real pre-004 database. Each
test then advances the DB forward through the *current* latest migration
(0004's backfill + 0005's NOT NULL promotion) before asserting with the
normal model classes, and the fixture restores that latest state for the
rest of the suite on teardown.
"""

import importlib

import pytest
from django.apps import apps as django_apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from apps.surveys.models import ProcessingRun, Survey, UploadSession

pytestmark = pytest.mark.django_db(transaction=True)

APP = "surveys"
BEFORE = "0003_derivedartifact_option_id_processingrun_input_type_and_more"

backfill_module = importlib.import_module("apps.surveys.migrations.0004_backfill_options")


def _advance_to_latest():
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(executor.loader.graph.leaf_nodes())


@pytest.fixture
def pre_backfill_apps():
    """Historical model state as of 0003: DerivedArtifact.option_id is still
    nullable and no RunOption rows exist yet — the real pre-004 shape."""
    executor = MigrationExecutor(connection)
    executor.migrate([(APP, BEFORE)])
    apps_at_before = executor.loader.project_state([(APP, BEFORE)]).apps
    yield apps_at_before
    _advance_to_latest()


def _pre_feature_run(
    pre_backfill_apps, project, user, *, name, status, run_state, artifact_kinds, failure_code=None
):
    HistoricalSurvey = pre_backfill_apps.get_model(APP, "Survey")
    HistoricalProcessingRun = pre_backfill_apps.get_model(APP, "ProcessingRun")
    HistoricalDerivedArtifact = pre_backfill_apps.get_model(APP, "DerivedArtifact")

    survey = HistoricalSurvey.objects.create(
        project_id=project.id,
        name=name,
        capture_date="2026-01-01",
        source_size_bytes=1,
        source_key=f"projects/{project.id}/surveys/{name}/source/{name}",
        created_by_id=user.id,
        status=status,
    )
    run = HistoricalProcessingRun.objects.create(
        survey=survey,
        number=1,
        stage="surface_generation" if artifact_kinds else "validation",
        state=run_state,
        failure_code=failure_code,
        failure_message_key=f"errors.{failure_code}" if failure_code else None,
    )
    for kind in artifact_kinds:
        HistoricalDerivedArtifact.objects.create(
            run=run,
            kind=kind,
            option_id=None,
            storage_key=f"k/{kind}",
            size_bytes=1,
            sha256="a" * 64,
        )
    return survey.id, run.id


def test_backfill_attributes_completed_run(pre_backfill_apps, project, user):
    survey_id, run_id = _pre_feature_run(
        pre_backfill_apps,
        project,
        user,
        name="completed.laz",
        status="completed",
        run_state="completed",
        artifact_kinds=["dem", "hillshade", "copc"],
    )

    _advance_to_latest()

    run = ProcessingRun.objects.get(id=run_id)
    states = {o.option_id: o.state for o in run.options.all()}
    assert states == {
        "elevation": "completed",
        "hillshade": "completed",
        "point_cloud_3d": "completed",
    }
    attribution = {a.kind: a.option_id for a in run.artifacts.all()}
    assert attribution == {"dem": "elevation", "hillshade": "hillshade", "copc": "point_cloud_3d"}


def test_backfill_marks_one_failed_and_rest_skipped(pre_backfill_apps, project, user):
    survey_id, run_id = _pre_feature_run(
        pre_backfill_apps,
        project,
        user,
        name="failed.laz",
        status="failed",
        run_state="failed",
        artifact_kinds=[],
        failure_code="missing_crs",
    )

    _advance_to_latest()

    run = ProcessingRun.objects.get(id=run_id)
    option_ids = {o.option_id for o in run.options.all()}
    assert option_ids == {"elevation", "hillshade", "point_cloud_3d"}
    states = [o.state for o in run.options.all()]
    assert states.count("failed") == 1
    assert states.count("skipped") == 2
    failed_option = run.options.get(state="failed")
    assert failed_option.failure_code == "missing_crs"
    assert failed_option.failure_message_key == "errors.missing_crs"


def test_backfill_sets_standard_selection_on_upload_sessions(project, user):
    session = UploadSession.objects.create(
        project=project,
        declared_filename="a.laz",
        declared_size_bytes=1,
        capture_date="2026-01-01",
        survey_name="a.laz",
        created_by=user,
        selected_options=[],
    )

    backfill_module.backfill(django_apps, None)

    session.refresh_from_db()
    assert session.selected_options == ["elevation", "hillshade", "point_cloud_3d"]


def test_backfill_is_idempotent(pre_backfill_apps, project, user):
    survey_id, run_id = _pre_feature_run(
        pre_backfill_apps,
        project,
        user,
        name="completed.laz",
        status="completed",
        run_state="completed",
        artifact_kinds=["dem", "hillshade", "copc"],
    )

    _advance_to_latest()

    backfill_module.backfill(django_apps, None)  # running again must not duplicate rows

    run = ProcessingRun.objects.get(id=run_id)
    assert run.options.count() == 3


def test_survey_detail_endpoint_serves_backfilled_data(pre_backfill_apps, project, user, api):
    survey_id, run_id = _pre_feature_run(
        pre_backfill_apps,
        project,
        user,
        name="completed.laz",
        status="completed",
        run_state="completed",
        artifact_kinds=["dem", "hillshade", "copc"],
    )

    _advance_to_latest()

    survey = Survey.objects.get(id=survey_id)
    detail = api.get(f"/api/v1/surveys/{survey.id}").json()

    assert detail["input_type"] == "point_cloud"
    latest_run = detail["runs"][0]
    assert latest_run["input_type"] == "point_cloud"
    option_ids = {o["option_id"] for o in latest_run["options"]}
    assert option_ids == {"elevation", "hillshade", "point_cloud_3d"}
    assert all(o["state"] == "completed" for o in latest_run["options"])
