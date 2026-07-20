"""T011: DELETE /surveys/{id} (US1, contracts/rest-api.md)."""

from types import SimpleNamespace

import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.projects.models import Project, ProjectMembership
from apps.surveys.models import Survey

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


def _delete(actor, survey):
    return actor.client.delete(f"/api/v1/surveys/{survey.id}")


def test_owner_deletes_survey_others_unaffected(ana, project):
    target = _survey(project, ana.user, name="a.laz")
    other = _survey(project, ana.user, name="b.laz")

    response = _delete(ana, target)
    assert response.status_code == 204

    remaining = [s["name"] for s in ana.client.get(f"/api/v1/projects/{project.id}/surveys").json()]
    assert remaining == ["b.laz"]
    target.refresh_from_db()
    assert target.deleted_at is not None
    assert target.deleted_by == ana.user
    assert target.deleted_via_project_cascade is False
    other.refresh_from_db()
    assert other.deleted_at is None


def test_non_owner_rejected(ana, beto, project):
    ProjectMembership.objects.create(
        project=project, user=beto.user, role=ProjectMembership.Role.MEMBER, granted_by=ana.user
    )
    survey = _survey(project, ana.user)
    response = _delete(beto, survey)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_owner"


@pytest.mark.parametrize("status", [Survey.Status.QUEUED, Survey.Status.PROCESSING])
def test_processing_survey_rejected(ana, project, status):
    survey = _survey(project, ana.user, status=status)
    response = _delete(ana, survey)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_deletable"


def test_deleting_already_deleted_or_nonexistent_is_404(ana, project):
    survey = _survey(project, ana.user)
    assert _delete(ana, survey).status_code == 204
    assert _delete(ana, survey).status_code == 404

    import uuid

    assert _delete(ana, SimpleNamespace(id=uuid.uuid4())).status_code == 404
