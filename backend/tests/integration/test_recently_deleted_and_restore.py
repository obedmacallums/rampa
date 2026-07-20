"""T028: GET /deleted + POST restore endpoints (US3, contracts/rest-api.md)."""

import uuid
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

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


def _soft_delete_survey(survey, user, via_cascade=False):
    survey.deleted_at = timezone.now()
    survey.deleted_by = user
    survey.deleted_via_project_cascade = via_cascade
    survey.save()


def _soft_delete_project(project, user):
    project.deleted_at = timezone.now()
    project.deleted_by = user
    project.save()


def test_listing_shape_and_ownership_scoping(ana, beto, project):
    other_project = Project.objects.create(
        name="Rajo Beto", crs=project.crs, created_by=beto.user
    )
    ProjectMembership.objects.create(
        project=other_project, user=beto.user, role=ProjectMembership.Role.OWNER,
        granted_by=beto.user,
    )
    ProjectMembership.objects.create(
        project=project, user=beto.user, role=ProjectMembership.Role.MEMBER, granted_by=ana.user
    )

    survey_independent = _survey(project, ana.user, name="a.laz")
    _soft_delete_survey(survey_independent, ana.user, via_cascade=False)
    survey_cascade = _survey(project, ana.user, name="b.laz")
    _soft_delete_survey(survey_cascade, ana.user, via_cascade=True)
    _soft_delete_project(other_project, beto.user)

    body = ana.client.get("/api/v1/deleted").json()
    assert [p["id"] for p in body["projects"]] == []
    survey_ids = [s["id"] for s in body["surveys"]]
    assert str(survey_independent.id) in survey_ids
    assert str(survey_cascade.id) not in survey_ids
    entry = next(s for s in body["surveys"] if s["id"] == str(survey_independent.id))
    assert entry["project"] == {"id": str(project.id), "name": project.name}
    assert entry["deleted_at"] and entry["purge_at"]

    # beto is a plain member of `project` (not owner) and owns `other_project`
    beto_body = beto.client.get("/api/v1/deleted").json()
    assert [p["id"] for p in beto_body["projects"]] == [str(other_project.id)]
    assert beto_body["surveys"] == []


def test_restore_independent_survey(ana, project):
    survey = _survey(project, ana.user, name="a.laz")
    _soft_delete_survey(survey, ana.user, via_cascade=False)

    response = ana.client.post(f"/api/v1/surveys/{survey.id}/restore")
    assert response.status_code == 200

    names = [s["name"] for s in ana.client.get(f"/api/v1/projects/{project.id}/surveys").json()]
    assert "a.laz" in names


def test_restore_project_cascade_restores_surveys_but_not_independent_ones(ana, project):
    independent = _survey(project, ana.user, name="independent.laz")
    _soft_delete_survey(independent, ana.user, via_cascade=False)

    cascaded = _survey(project, ana.user, name="cascaded.laz")
    _soft_delete_survey(cascaded, ana.user, via_cascade=True)
    _soft_delete_project(project, ana.user)

    response = ana.client.post(f"/api/v1/projects/{project.id}/restore")
    assert response.status_code == 200

    names = [s["name"] for s in ana.client.get(f"/api/v1/projects/{project.id}/surveys").json()]
    assert "cascaded.laz" in names
    assert "independent.laz" not in names


def test_restore_past_recovery_window_is_not_restorable(ana, project):
    from datetime import timedelta

    survey = _survey(project, ana.user)
    survey.deleted_at = timezone.now() - timedelta(days=8)
    survey.deleted_by = ana.user
    survey.save()

    response = ana.client.post(f"/api/v1/surveys/{survey.id}/restore")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_restorable"


def test_restore_nonexistent_or_foreign_is_not_restorable(ana, beto, project):
    response = ana.client.post(f"/api/v1/surveys/{uuid.uuid4()}/restore")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_restorable"

    survey = _survey(project, ana.user)
    _soft_delete_survey(survey, ana.user)
    response = beto.client.post(f"/api/v1/surveys/{survey.id}/restore")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_restorable"


def test_restore_non_owner_rejected(ana, beto, project):
    ProjectMembership.objects.create(
        project=project, user=beto.user, role=ProjectMembership.Role.MEMBER, granted_by=ana.user
    )
    survey = _survey(project, ana.user)
    _soft_delete_survey(survey, ana.user)

    response = beto.client.post(f"/api/v1/surveys/{survey.id}/restore")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_owner"

    _soft_delete_project(project, ana.user)
    response = beto.client.post(f"/api/v1/projects/{project.id}/restore")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_owner"
