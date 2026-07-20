"""T009: soft-deleted scoping is enforced at the single access.py chokepoint
(005 Phase 2), plus ProjectSummarySerializer.is_owner (T007)."""

from types import SimpleNamespace

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

from apps.projects import access
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


def _survey(project, user, name="vuelo.laz"):
    return Survey.objects.create(
        project=project,
        name=name,
        capture_date="2026-01-01",
        source_size_bytes=1,
        source_key="tus-staging/x",
        created_by=user,
    )


def test_soft_deleted_project_hidden_from_projects_for_and_listing(ana, project):
    assert project in access.projects_for(ana.user)
    project.deleted_at = timezone.now()
    project.deleted_by = ana.user
    project.save(update_fields=["deleted_at", "deleted_by"])

    assert project not in access.projects_for(ana.user)
    assert ana.client.get("/api/v1/projects").json() == []
    with pytest.raises(Exception):
        access.get_project_or_404(ana.user, project.id)


def test_soft_deleted_survey_hidden(ana, project):
    survey = _survey(project, ana.user)
    assert access.get_survey_or_404(ana.user, survey.id) == survey

    survey.deleted_at = timezone.now()
    survey.deleted_by = ana.user
    survey.save(update_fields=["deleted_at", "deleted_by"])

    with pytest.raises(Exception):
        access.get_survey_or_404(ana.user, survey.id)
    listed = ana.client.get(f"/api/v1/projects/{project.id}/surveys").json()
    assert survey.name not in [s["name"] for s in listed]


def test_survey_hidden_when_its_project_is_soft_deleted(ana, project):
    survey = _survey(project, ana.user)
    project.deleted_at = timezone.now()
    project.deleted_by = ana.user
    project.save(update_fields=["deleted_at", "deleted_by"])

    with pytest.raises(Exception):
        access.get_survey_or_404(ana.user, survey.id)


def test_project_summary_is_owner_true_for_owner_false_for_member(ana, beto, project):
    ProjectMembership.objects.create(
        project=project, user=beto.user, role=ProjectMembership.Role.MEMBER, granted_by=ana.user
    )

    owner_view = {p["id"]: p for p in ana.client.get("/api/v1/projects").json()}
    member_view = {p["id"]: p for p in beto.client.get("/api/v1/projects").json()}

    assert owner_view[str(project.id)]["is_owner"] is True
    assert member_view[str(project.id)]["is_owner"] is False
