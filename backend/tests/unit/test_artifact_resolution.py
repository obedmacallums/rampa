"""T011: latest-completed-per-option resolution across a survey's runs (FR-016)."""

import pytest

from apps.surveys.models import DerivedArtifact, ProcessingRun, RunOption, Survey
from apps.surveys.resolution import resolve_products

pytestmark = pytest.mark.django_db


def _survey(project, user, name="s.laz"):
    return Survey.objects.create(
        project=project,
        name=name,
        capture_date="2026-01-01",
        source_size_bytes=1,
        source_key=f"projects/{project.id}/surveys/{name}/source/{name}",
        created_by=user,
    )


def _run(survey, number, state="completed"):
    return ProcessingRun.objects.create(survey=survey, number=number, state=state)


def _artifact(run, kind, option_id):
    return DerivedArtifact.objects.create(
        run=run,
        kind=kind,
        option_id=option_id,
        storage_key=f"k/{run.id}/{kind}",
        size_bytes=1,
        sha256="a" * 64,
    )


def _run_option(run, option_id, state, reused_from=None):
    return RunOption.objects.create(
        run=run, option_id=option_id, state=state, reused_from=reused_from
    )


def test_resolves_completed_options_only(project, user):
    survey = _survey(project, user)
    run = _run(survey, 1)
    _run_option(run, "elevation", RunOption.State.COMPLETED)
    _run_option(run, "hillshade", RunOption.State.COMPLETED)
    _run_option(run, "point_cloud_3d", RunOption.State.FAILED)
    _artifact(run, "dem", "elevation")
    _artifact(run, "hillshade", "hillshade")

    resolved = resolve_products(survey)

    assert set(resolved) == {"elevation", "hillshade"}
    artifact, producing_run = resolved["elevation"]
    assert artifact.kind == "dem"
    assert producing_run == run


def test_reused_option_resolves_to_original_producing_run(project, user):
    survey = _survey(project, user)
    run1 = _run(survey, 1, state="failed")
    _run_option(run1, "elevation", RunOption.State.COMPLETED)
    _run_option(run1, "hillshade", RunOption.State.COMPLETED)
    _run_option(run1, "point_cloud_3d", RunOption.State.FAILED)
    _artifact(run1, "dem", "elevation")
    _artifact(run1, "hillshade", "hillshade")

    run2 = _run(survey, 2, state="completed")
    _run_option(run2, "elevation", RunOption.State.REUSED, reused_from=run1)
    _run_option(run2, "hillshade", RunOption.State.REUSED, reused_from=run1)
    _run_option(run2, "point_cloud_3d", RunOption.State.COMPLETED)
    _artifact(run2, "copc", "point_cloud_3d")

    resolved = resolve_products(survey)

    assert resolved["elevation"][1] == run1
    assert resolved["hillshade"][1] == run1
    assert resolved["point_cloud_3d"][1] == run2
    assert resolved["point_cloud_3d"][0].kind == "copc"


def test_option_absent_from_latest_run_falls_back_to_earlier_run(project, user):
    survey = _survey(project, user)
    run1 = _run(survey, 1)
    _run_option(run1, "elevation", RunOption.State.COMPLETED)
    _run_option(run1, "hillshade", RunOption.State.COMPLETED)
    _artifact(run1, "dem", "elevation")
    _artifact(run1, "hillshade", "hillshade")

    # run2 only requested point_cloud_3d (US3 additional-options) — no
    # hillshade RunOption row at all in this run.
    run2 = _run(survey, 2)
    _run_option(run2, "elevation", RunOption.State.REUSED, reused_from=run1)
    _run_option(run2, "point_cloud_3d", RunOption.State.COMPLETED)
    _artifact(run2, "copc", "point_cloud_3d")

    resolved = resolve_products(survey)

    assert resolved["hillshade"][1] == run1
    assert resolved["point_cloud_3d"][1] == run2


def test_never_completed_option_is_absent(project, user):
    survey = _survey(project, user)
    run = _run(survey, 1, state="failed")
    _run_option(run, "elevation", RunOption.State.COMPLETED)
    _run_option(run, "hillshade", RunOption.State.SKIPPED)
    _artifact(run, "dem", "elevation")

    resolved = resolve_products(survey)

    assert set(resolved) == {"elevation"}
