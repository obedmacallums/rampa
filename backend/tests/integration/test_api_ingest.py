"""T018: API contract tests — auth, projects, upload initiation, hook, artifacts."""

import pytest

pytestmark = pytest.mark.django_db


def _initiate(api, project, **overrides):
    body = {
        "filename": "vuelo.laz",
        "size_bytes": 1024,
        "capture_date": "2026-07-01",
        **overrides,
    }
    return api.post(
        f"/api/v1/projects/{project.id}/uploads", body, content_type="application/json"
    )


def test_login_required(client, project):
    response = client.get("/api/v1/projects")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_login_and_me(client, user):
    bad = client.post(
        "/api/v1/auth/login",
        {"username": "demo", "password": "wrong"},
        content_type="application/json",
    )
    assert bad.status_code == 401
    ok = client.post(
        "/api/v1/auth/login",
        {"username": "demo", "password": "demo1234"},
        content_type="application/json",
    )
    assert ok.status_code == 200
    assert client.get("/api/v1/auth/me").json()["user"]["username"] == "demo"


def test_create_and_list_projects(api, crs_entry):
    created = api.post(
        "/api/v1/projects",
        {"name": "Rajo Sur", "crs_id": crs_entry.id},
        content_type="application/json",
    )
    assert created.status_code == 201
    assert created.json()["crs"]["code"] == "EPSG:32719"

    duplicate = api.post(
        "/api/v1/projects",
        {"name": "rajo sur", "crs_id": crs_entry.id},
        content_type="application/json",
    )
    assert duplicate.status_code == 400
    assert duplicate.json()["error"]["code"] == "name_taken"

    bad_crs = api.post(
        "/api/v1/projects",
        {"name": "Otro", "crs_id": 999},
        content_type="application/json",
    )
    assert bad_crs.json()["error"]["code"] == "invalid_crs"

    listing = api.get("/api/v1/projects").json()
    assert [p["name"] for p in listing] == ["Rajo Sur"]


def test_upload_initiation_fast_rejects(api, project):
    too_big = _initiate(api, project, size_bytes=51 * 1024**3)
    assert too_big.json()["error"]["code"] == "file_too_large"

    bad_ext = _initiate(api, project, filename="scan.e57")
    assert bad_ext.json()["error"]["code"] == "unsupported_extension"
    assert bad_ext.json()["error"]["detail"]["accepted"] == [".las", ".laz"]

    bad_date = _initiate(api, project, capture_date="not-a-date")
    assert bad_date.json()["error"]["code"] == "invalid_capture_date"


def test_upload_initiation_and_tusd_hook_creates_survey(api, project, stub_chain, settings):
    initiated = _initiate(api, project)
    assert initiated.status_code == 201
    session_id = initiated.json()["upload_session_id"]
    assert initiated.json()["tus_metadata"]["upload_session_id"] == session_id

    hook_payload = {
        "Type": "post-finish",
        "Event": {
            "Upload": {
                "ID": "tus-abc",
                "Size": 1024,
                "MetaData": {"upload_session_id": session_id},
                "Storage": {"Key": "tus-staging/tus-abc", "Bucket": "rampa"},
            }
        },
    }
    denied = api.post("/api/v1/hooks/tusd", hook_payload, content_type="application/json")
    assert denied.status_code == 403

    accepted = api.post(
        "/api/v1/hooks/tusd",
        hook_payload,
        content_type="application/json",
        headers={"X-Rampa-Hook-Secret": settings.TUSD_HOOK_SECRET},
    )
    assert accepted.status_code == 200

    surveys = api.get(f"/api/v1/projects/{project.id}/surveys").json()
    assert len(surveys) == 1
    assert surveys[0]["status"] == "queued"
    assert surveys[0]["name"] == "vuelo.laz"
    assert len(stub_chain) == 1  # run enqueued exactly once

    # artifacts are not ready before a completed run
    not_ready = api.get(f"/api/v1/surveys/{surveys[0]['id']}/artifacts")
    assert not_ready.status_code == 409
    assert not_ready.json()["error"]["code"] == "not_ready"
