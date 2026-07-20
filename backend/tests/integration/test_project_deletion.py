"""T019: DELETE /projects/{id} cascade semantics (US2, contracts/rest-api.md)."""

from types import SimpleNamespace

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

from apps.projects.models import Project, ProjectMembership
from apps.surveys.models import Survey, UploadSession

pytestmark = pytest.mark.django_db

PASSWORD = "pw12345678"


def _actor(username):
    user = User.objects.create_user(username, password=PASSWORD)
    client = Client()
    client.login(username=username, password=PASSWORD)
    return SimpleNamespace(user=user, client=client)


@pytest.fixture
def ana(db):
    return _actor("ana")


@pytest.fixture
def beto(db):
    return _actor("beto")


@pytest.fixture
def project(ana, crs_entry):
    project = Project.objects.create(name="Rajo Ana", crs=crs_entry, created_by=ana.user)
    ProjectMembership.objects.create(
        project=project, user=ana.user, role=ProjectMembership.Role.OWNER, granted_by=ana.user
    )
    return project


def _survey(project, user, name="vuelo.laz", status=Survey.Status.COMPLETED):
    return Survey.objects.create(
        project=project,
        name=name,
        capture_date="2026-01-01",
        source_size_bytes=1,
        source_key="tus-staging/x",
        created_by=user,
        status=status,
    )


def _delete_project(actor, project):
    return actor.client.delete(f"/api/v1/projects/{project.id}")


def test_owner_deletes_project_cascades_active_surveys(ana, project):
    survey_a = _survey(project, ana.user, name="a.laz", status=Survey.Status.COMPLETED)
    survey_b = _survey(project, ana.user, name="b.laz", status=Survey.Status.FAILED)

    response = _delete_project(ana, project)
    assert response.status_code == 204

    assert ana.client.get("/api/v1/projects").json() == []
    assert ana.client.get(f"/api/v1/projects/{project.id}/surveys").status_code == 404

    project.refresh_from_db()
    assert project.deleted_at is not None
    assert project.deleted_by == ana.user
    for survey in (survey_a, survey_b):
        survey.refresh_from_db()
        assert survey.deleted_at is not None
        assert survey.deleted_via_project_cascade is True


def test_independently_deleted_survey_stays_independent(ana, project):
    survey = _survey(project, ana.user, name="a.laz")
    survey.deleted_at = timezone.now()
    survey.deleted_by = ana.user
    survey.deleted_via_project_cascade = False
    survey.save()

    assert _delete_project(ana, project).status_code == 204

    survey.refresh_from_db()
    assert survey.deleted_via_project_cascade is False


@pytest.mark.parametrize("status", [Survey.Status.QUEUED, Survey.Status.PROCESSING])
def test_blocked_while_a_survey_is_processing(ana, project, status):
    _survey(project, ana.user, status=status)
    response = _delete_project(ana, project)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_deletable"


def test_blocked_while_an_upload_is_active(ana, project):
    UploadSession.objects.create(
        project=project,
        declared_filename="x.laz",
        declared_size_bytes=1,
        capture_date="2026-01-01",
        survey_name="x",
        created_by=ana.user,
        state=UploadSession.State.ACTIVE,
    )
    response = _delete_project(ana, project)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_deletable"


def test_non_owner_rejected(ana, beto, project):
    ProjectMembership.objects.create(
        project=project, user=beto.user, role=ProjectMembership.Role.MEMBER, granted_by=ana.user
    )
    response = _delete_project(beto, project)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_owner"


def test_deleting_already_deleted_or_nonexistent_is_404(ana, project):
    assert _delete_project(ana, project).status_code == 204
    assert _delete_project(ana, project).status_code == 404
