"""T040: pending-upload listing, expiry purge, concurrent sessions (US3)."""

import datetime

import pytest
from django.utils import timezone

from apps.surveys.models import UploadSession
from apps.surveys.tasks_maintenance import purge_expired_upload_sessions

pytestmark = pytest.mark.django_db


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


def test_active_sessions_listed_with_sizes(api, project, user, monkeypatch):
    monkeypatch.setattr("apps.surveys.views_uploads._tus_offset", lambda _id: 5_000)
    _session(project, user, tus_upload_id="tus-1")
    listing = api.get(f"/api/v1/projects/{project.id}/uploads").json()
    assert len(listing) == 1
    assert listing[0]["received_bytes"] == 5_000
    assert listing[0]["declared_size_bytes"] == 10_000
    assert listing[0]["state"] == "active"


def test_expired_sessions_purged_and_absent(api, project, user):
    stale = _session(project, user, declared_filename="viejo.laz")
    UploadSession.objects.filter(id=stale.id).update(
        created_at=timezone.now() - datetime.timedelta(days=8)
    )
    fresh = _session(project, user, declared_filename="nuevo.laz")

    assert purge_expired_upload_sessions() == 1
    stale.refresh_from_db()
    assert stale.state == UploadSession.State.EXPIRED

    listing = api.get(f"/api/v1/projects/{project.id}/uploads").json()
    assert [item["declared_filename"] for item in listing] == [fresh.declared_filename]
    # an expired upload never became a survey
    assert api.get(f"/api/v1/projects/{project.id}/surveys").json() == []


def test_concurrent_sessions_yield_independent_surveys(api, project, stub_chain, settings):
    ids = []
    for name in ("a.laz", "b.laz"):
        response = api.post(
            f"/api/v1/projects/{project.id}/uploads",
            {"filename": name, "size_bytes": 1024, "capture_date": "2026-07-01"},
            content_type="application/json",
        )
        ids.append(response.json()["upload_session_id"])

    for i, session_id in enumerate(ids):
        api.post(
            "/api/v1/hooks/tusd",
            {
                "Type": "post-finish",
                "Event": {
                    "Upload": {
                        "ID": f"tus-{i}",
                        "Size": 1024,
                        "MetaData": {"upload_session_id": session_id},
                        "Storage": {"Key": f"tus-staging/tus-{i}", "Bucket": "rampa"},
                    }
                },
            },
            content_type="application/json",
            headers={"X-Rampa-Hook-Secret": settings.TUSD_HOOK_SECRET},
        )

    surveys = api.get(f"/api/v1/projects/{project.id}/surveys").json()
    assert len(surveys) == 2
    assert {s["name"] for s in surveys} == {"a.laz", "b.laz"}
