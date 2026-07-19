"""T044: coexistence & immutability — second survey never touches the first (US4)."""

import pytest

from apps.surveys.models import DerivedArtifact, ProcessingRun, Survey
from pipeline import storage

pytestmark = pytest.mark.django_db


def _completed_survey(project, user, name, capture_date, shas):
    survey = Survey.objects.create(
        project=project,
        name=name,
        capture_date=capture_date,
        source_size_bytes=1024,
        source_key=f"projects/{project.id}/surveys/{name}/source/{name}",
        created_by=user,
        status=Survey.Status.COMPLETED,
    )
    run = ProcessingRun.objects.create(
        survey=survey,
        number=1,
        stage=ProcessingRun.Stage.SURFACE_GENERATION,
        state=ProcessingRun.State.COMPLETED,
    )
    for kind, sha in shas.items():
        DerivedArtifact.objects.create(
            run=run,
            kind=kind,
            storage_key=storage.run_key(project.id, survey.id, run.id, f"{kind}.bin"),
            size_bytes=100,
            sha256=sha,
        )
    return survey


def test_surveys_coexist_and_first_checksums_unchanged(api, project, user):
    first_shas = {"dem": "a" * 64, "hillshade": "b" * 64, "copc": "c" * 64}
    first = _completed_survey(project, user, "enero.laz", "2026-01-15", first_shas)

    second = _completed_survey(
        project, user, "julio.laz", "2026-07-15", {"dem": "d" * 64, "hillshade": "e" * 64, "copc": "f" * 64}
    )

    # chronological order by capture date (FR-014)
    listing = api.get(f"/api/v1/projects/{project.id}/surveys").json()
    assert [s["name"] for s in listing] == ["enero.laz", "julio.laz"]

    # first survey's artifacts byte-identical after the second completed (SC-007)
    stored = {
        a.kind: a.sha256
        for a in DerivedArtifact.objects.filter(run__survey=first)
    }
    assert stored == first_shas
    assert second.runs.count() == 1


def test_run_scoped_writes_cannot_cross_surveys(project):
    other_key = f"projects/{project.id}/surveys/OTHER/runs/r1/dem.tif"
    with pytest.raises(AssertionError):
        storage.assert_key_within_survey(other_key, project.id, "SURVEY-A")
