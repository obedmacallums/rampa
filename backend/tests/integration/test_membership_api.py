"""002 T011: membership management API (US3, contracts/rest-api.md)."""

from types import SimpleNamespace

import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.projects.models import Project, ProjectMembership

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


def _members_url(project):
    return f"/api/v1/projects/{project.id}/members"


def _add(owner, project, username, role="member"):
    return owner.client.post(
        _members_url(project), {"username": username, "role": role},
        content_type="application/json",
    )


# --- GET (FR-007, FR-009) ---


def test_list_visible_to_any_member_with_audit_columns(ana, beto, project):
    _add(ana, project, "beto")
    for actor in (ana, beto):
        rows = actor.client.get(_members_url(project)).json()
        assert {r["username"]: r["role"] for r in rows} == {"ana": "owner", "beto": "member"}
        by_name = {r["username"]: r for r in rows}
        assert by_name["beto"]["granted_by"] == "ana"
        assert by_name["ana"]["granted_at"]


def test_list_404_for_non_member(beto, project):
    response = beto.client.get(_members_url(project))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# --- POST (FR-005) ---


def test_add_member_grants_access(ana, beto, project):
    created = _add(ana, project, "beto")
    assert created.status_code == 201
    assert created.json()["role"] == "member"
    assert [p["name"] for p in beto.client.get("/api/v1/projects").json()] == ["Rajo Ana"]


def test_add_requires_owner(ana, beto, project):
    _add(ana, project, "beto")
    _actor("carla")
    response = _add(beto, project, "carla")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_owner"


def test_add_unknown_username(ana, project):
    response = _add(ana, project, "nadie")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "user_not_found"


def test_add_already_member(ana, beto, project):
    _add(ana, project, "beto")
    response = _add(ana, project, "beto")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "already_member"
    assert project.memberships.count() == 2


def test_add_invalid_role(ana, beto, project):
    response = _add(ana, project, "beto", role="viewer")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_role"


# --- PATCH (US3 scenario 6, FR-006) ---


def test_sole_owner_cannot_downgrade_self(ana, project):
    response = ana.client.patch(
        f"{_members_url(project)}/ana", {"role": "member"}, content_type="application/json"
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "last_owner"


def test_ownership_handover_with_two_owners(ana, beto, project):
    _add(ana, project, "beto", role="owner")

    downgraded = beto.client.patch(
        f"{_members_url(project)}/ana", {"role": "member"}, content_type="application/json"
    )
    assert downgraded.status_code == 200
    assert downgraded.json()["role"] == "member"

    # beto is now sole owner: self-downgrade must be refused
    refused = beto.client.patch(
        f"{_members_url(project)}/beto", {"role": "member"}, content_type="application/json"
    )
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "last_owner"


def test_patch_unknown_membership(ana, project):
    _actor("carla")  # exists as user, not as member
    response = ana.client.patch(
        f"{_members_url(project)}/carla", {"role": "owner"}, content_type="application/json"
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# --- DELETE (FR-006, FR-008) ---


def test_remove_member_ends_access(ana, beto, project):
    _add(ana, project, "beto")
    removed = ana.client.delete(f"{_members_url(project)}/beto")
    assert removed.status_code == 204

    assert beto.client.get("/api/v1/projects").json() == []
    assert beto.client.get(f"/api/v1/projects/{project.id}/surveys").status_code == 404


def test_remove_sole_owner_refused(ana, project):
    response = ana.client.delete(f"{_members_url(project)}/ana")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "last_owner"


def test_delete_unknown_membership(ana, project):
    response = ana.client.delete(f"{_members_url(project)}/nadie")
    assert response.status_code == 404


def test_mutations_are_owner_only(ana, beto, project):
    _add(ana, project, "beto")
    patch = beto.client.patch(
        f"{_members_url(project)}/ana", {"role": "member"}, content_type="application/json"
    )
    delete = beto.client.delete(f"{_members_url(project)}/ana")
    assert patch.status_code == 403 and delete.status_code == 403
