"""002 T005/T009: US1 isolation matrix + US2 creation grants ownership.

Denial for non-members must be byte-identical to true nonexistence (FR-002);
the tusd hook stays unscoped (FR-012).
"""

import uuid
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


def _world(crs_entry):
    """Two users, two projects, disjoint memberships, one survey each."""
    ana, beto = _actor("ana"), _actor("beto")
    projects = {}
    surveys = {}
    for actor, name in ((ana, "Rajo Ana"), (beto, "Rajo Beto")):
        project = Project.objects.create(name=name, crs=crs_entry, created_by=actor.user)
        ProjectMembership.objects.create(
            project=project,
            user=actor.user,
            role=ProjectMembership.Role.OWNER,
            granted_by=actor.user,
        )
        surveys[name] = Survey.objects.create(
            project=project,
            name="vuelo.laz",
            capture_date="2026-07-01",
            source_size_bytes=1024,
            source_key=f"projects/{project.id}/surveys/x/source/vuelo.laz",
            created_by=actor.user,
        )
        projects[name] = project
    return ana, beto, projects, surveys


@pytest.fixture
def world(crs_entry):
    return _world(crs_entry)


UPLOAD_BODY = {"filename": "v.laz", "size_bytes": 1024, "capture_date": "2026-07-01"}


def _surfaces(client, project_id, survey_id):
    """Every project-scoped surface of the API, exercised for the given ids."""
    return [
        ("GET surveys", lambda: client.get(f"/api/v1/projects/{project_id}/surveys")),
        ("GET uploads", lambda: client.get(f"/api/v1/projects/{project_id}/uploads")),
        (
            "POST uploads",
            lambda: client.post(
                f"/api/v1/projects/{project_id}/uploads",
                UPLOAD_BODY,
                content_type="application/json",
            ),
        ),
        ("GET survey", lambda: client.get(f"/api/v1/surveys/{survey_id}")),
        ("GET artifacts", lambda: client.get(f"/api/v1/surveys/{survey_id}/artifacts")),
        ("POST retry", lambda: client.post(f"/api/v1/surveys/{survey_id}/retry")),
    ]


def test_list_shows_only_own_memberships(world):
    ana, beto, projects, _ = world
    for actor, name in ((ana, "Rajo Ana"), (beto, "Rajo Beto")):
        listed = actor.client.get("/api/v1/projects").json()
        assert [p["name"] for p in listed] == [name]
        assert listed[0]["survey_count"] == 1


def test_non_member_indistinguishable_from_nonexistent(world):
    ana, _, projects, surveys = world
    foreign = _surfaces(ana.client, projects["Rajo Beto"].id, surveys["Rajo Beto"].id)
    ghost = _surfaces(ana.client, uuid.uuid4(), uuid.uuid4())
    for (label, hit_real), (_, hit_ghost) in zip(foreign, ghost, strict=True):
        real, fake = hit_real(), hit_ghost()
        assert real.status_code == 404, f"{label}: expected 404, got {real.status_code}"
        assert real.json() == fake.json(), f"{label}: denial differs from nonexistence"
        assert real.json()["error"]["code"] == "not_found"


def test_member_keeps_existing_capabilities(world):
    ana, _, projects, surveys = world
    project, survey = projects["Rajo Ana"], surveys["Rajo Ana"]

    listed = ana.client.get(f"/api/v1/projects/{project.id}/surveys").json()
    assert [s["name"] for s in listed] == ["vuelo.laz"]

    created = ana.client.post(
        f"/api/v1/projects/{project.id}/uploads", UPLOAD_BODY, content_type="application/json"
    )
    assert created.status_code == 201

    pending = ana.client.get(f"/api/v1/projects/{project.id}/uploads")
    assert pending.status_code == 200 and len(pending.json()) == 1

    assert ana.client.get(f"/api/v1/surveys/{survey.id}").status_code == 200


def test_tusd_hook_needs_no_membership(world, settings):
    """FR-012: the hook authenticates by shared secret, not by session."""
    anonymous = Client()
    response = anonymous.post(
        f"/api/v1/hooks/tusd?secret={settings.TUSD_HOOK_SECRET}",
        {"Type": "post-create", "Upload": {"MetaData": {}}},
        content_type="application/json",
    )
    assert response.status_code == 200


# --- US2: creation grants ownership (T009) ---


def test_create_project_grants_owner_membership(world, crs_entry):
    ana, beto, _, _ = world
    created = ana.client.post(
        "/api/v1/projects",
        {"name": "Rajo Nuevo", "crs_id": crs_entry.id},
        content_type="application/json",
    )
    assert created.status_code == 201
    project_id = created.json()["id"]

    memberships = ProjectMembership.objects.filter(project_id=project_id)
    assert memberships.count() == 1
    membership = memberships.get()
    assert membership.user == ana.user
    assert membership.role == ProjectMembership.Role.OWNER
    assert membership.granted_by == ana.user

    assert "Rajo Nuevo" in [p["name"] for p in ana.client.get("/api/v1/projects").json()]
    assert "Rajo Nuevo" not in [p["name"] for p in beto.client.get("/api/v1/projects").json()]
    assert beto.client.get(f"/api/v1/projects/{project_id}/surveys").status_code == 404


def test_name_collision_with_invisible_project(world, crs_entry):
    """Names stay globally unique; minimal disclosure accepted (spec edge case)."""
    _, beto, _, _ = world
    response = beto.client.post(
        "/api/v1/projects",
        {"name": "rajo ana", "crs_id": crs_entry.id},
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "name_taken"
