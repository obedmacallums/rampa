"""DELETE /projects/{id}/uploads/{upload_session_id}: cancel a pending
upload (any project member, matching initiation/listing — neither of which
are owner-gated)."""

from types import SimpleNamespace

import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.projects.models import ProjectMembership
from apps.surveys.models import UploadSession

pytestmark = pytest.mark.django_db

PASSWORD = "pw12345678"


def _actor(username):
    user = User.objects.create_user(username, password=PASSWORD)
    client = Client()
    client.login(username=username, password=PASSWORD)
    return SimpleNamespace(user=user, client=client)


@pytest.fixture
def beto(db):
    return _actor("beto")


def _session(project, user, **overrides):
    defaults = dict(
        project=project,
        declared_filename="vuelo.laz",
        declared_size_bytes=10_000,
        capture_date="2026-07-01",
        survey_name="vuelo.laz",
        created_by=user,
    )
    defaults.update(overrides)
    return UploadSession.objects.create(**defaults)


def _url(project, session):
    return f"/api/v1/projects/{project.id}/uploads/{session.id}"


def test_owner_deletes_own_pending_upload(api, project, user):
    session = _session(project, user, tus_upload_id="tus-1")
    response = api.delete(_url(project, session))
    assert response.status_code == 204
    assert not UploadSession.objects.filter(id=session.id).exists()

    listing = api.get(f"/api/v1/projects/{project.id}/uploads").json()
    assert listing == []


def test_any_member_can_delete_a_pending_upload(project, user, beto):
    ProjectMembership.objects.create(
        project=project, user=beto.user, role=ProjectMembership.Role.MEMBER, granted_by=user
    )
    session = _session(project, user)
    response = beto.client.delete(_url(project, session))
    assert response.status_code == 204
    assert not UploadSession.objects.filter(id=session.id).exists()


def test_deleting_already_deleted_or_nonexistent_is_404(api, project, user):
    session = _session(project, user)
    assert api.delete(_url(project, session)).status_code == 204
    assert api.delete(_url(project, session)).status_code == 404


def test_non_member_rejected_404(project, user, beto):
    session = _session(project, user)
    response = beto.client.delete(_url(project, session))
    assert response.status_code == 404
    assert UploadSession.objects.filter(id=session.id).exists()


def test_completed_session_not_deletable_via_this_endpoint(api, project, user):
    session = _session(project, user, state=UploadSession.State.COMPLETED)
    response = api.delete(_url(project, session))
    assert response.status_code == 404
    assert UploadSession.objects.filter(id=session.id).exists()


def test_terminates_tus_upload_when_present(api, project, user, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "apps.surveys.views_uploads._tus_terminate", lambda tus_id: calls.append(tus_id)
    )
    session = _session(project, user, tus_upload_id="tus-42")
    response = api.delete(_url(project, session))
    assert response.status_code == 204
    assert calls == ["tus-42"]
