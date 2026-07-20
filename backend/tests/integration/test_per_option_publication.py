"""T012: per-option publication & failure isolation (FR-009/FR-010).

Runs the real orchestration (enqueue_run + task chain) synchronously: the
Celery dispatch itself is stubbed (`stub_chain`), then each captured
signature is invoked directly in-process via the shared `fake_pipeline`
harness (conftest.py) — filesystem/object-storage and the pdal/gdal-backed
producers are faked so the test needs neither a broker nor real binaries.
"""

import pytest

from apps.surveys import tasks as tasks_mod
from apps.surveys.models import ProcessingRun, Survey
from pipeline.errors import StageError
from pipeline.stages import surfaces as surfaces_mod
from tests.conftest import run_chain

pytestmark = pytest.mark.django_db


@pytest.fixture
def survey(project, user):
    return Survey.objects.create(
        project=project,
        name="vuelo.laz",
        capture_date="2026-07-01",
        source_size_bytes=1024,
        source_key=f"projects/{project.id}/surveys/x/source/vuelo.laz",
        created_by=user,
    )


def test_subset_selection_produces_exactly_those_artifacts(survey, stub_chain, fake_pipeline):
    run = tasks_mod.enqueue_run(survey, selection=["hillshade"])
    run_chain(stub_chain)

    run.refresh_from_db()
    assert run.state == ProcessingRun.State.COMPLETED
    option_states = {o.option_id: o.state for o in run.options.all()}
    assert option_states == {"elevation": "completed", "hillshade": "completed"}
    assert "point_cloud_3d" not in option_states
    produced_kinds = {a.option_id for a in run.artifacts.all()}
    assert produced_kinds == {"elevation", "hillshade"}


def test_one_option_failing_isolates_others_and_fails_the_run(survey, stub_chain, fake_pipeline):
    def failing_point_cloud_3d(ctx):
        raise StageError("internal_error", "forced failure")

    fake_pipeline.setattr(surfaces_mod, "produce_point_cloud_3d", failing_point_cloud_3d)

    run = tasks_mod.enqueue_run(survey, selection=["elevation", "hillshade", "point_cloud_3d"])
    run_chain(stub_chain)

    run.refresh_from_db()
    assert run.state == ProcessingRun.State.FAILED
    assert run.survey.status == Survey.Status.FAILED

    states = {o.option_id: o.state for o in run.options.all()}
    assert states["elevation"] == "completed"
    assert states["hillshade"] == "completed"
    assert states["point_cloud_3d"] == "failed"

    failed_option = run.options.get(option_id="point_cloud_3d")
    assert failed_option.failure_code == "internal_error"
    assert failed_option.failure_message_key == "errors.internal_error"

    # completed options' artifacts are still published (FR-009)
    published = {a.option_id for a in run.artifacts.all()}
    assert published == {"elevation", "hillshade"}


def test_failed_prerequisite_skips_dependent(survey, stub_chain, fake_pipeline):
    def failing_elevation(ctx):
        raise StageError("internal_error", "forced failure")

    fake_pipeline.setattr(surfaces_mod, "produce_elevation", failing_elevation)

    run = tasks_mod.enqueue_run(survey, selection=["elevation", "hillshade"])
    run_chain(stub_chain)

    run.refresh_from_db()
    assert run.state == ProcessingRun.State.FAILED
    states = {o.option_id: o.state for o in run.options.all()}
    assert states["elevation"] == "failed"
    assert states["hillshade"] == "skipped"
    assert run.artifacts.count() == 0
