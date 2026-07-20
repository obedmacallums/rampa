"""T018: selection travels upload initiation -> tusd hook -> enqueue_run
(FR-002/FR-006, quickstart Scenarios 2-3)."""

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


def _finish_hook(api, session_id, settings, size=1024):
    payload = {
        "Type": "post-finish",
        "Event": {
            "Upload": {
                "ID": "tus-abc",
                "Size": size,
                "MetaData": {"upload_session_id": session_id},
                "Storage": {"Key": "tus-staging/tus-abc", "Bucket": "rampa"},
            }
        },
    }
    return api.post(
        "/api/v1/hooks/tusd",
        payload,
        content_type="application/json",
        headers={"X-Rampa-Hook-Secret": settings.TUSD_HOOK_SECRET},
    )


def test_selecting_hillshade_completes_elevation_closure(api, project, stub_chain, settings):
    initiated = _initiate(api, project, selected_options=["hillshade"])
    assert initiated.status_code == 201
    assert set(initiated.json()["effective_options"]) == {"elevation", "hillshade"}

    session_id = initiated.json()["upload_session_id"]
    _finish_hook(api, session_id, settings)

    from apps.surveys.models import ProcessingRun

    run = ProcessingRun.objects.get()
    assert set(run.options.values_list("option_id", flat=True)) == {"elevation", "hillshade"}


def test_deselecting_point_cloud_3d_never_produces_copc(api, project, stub_chain, settings):
    initiated = _initiate(api, project, selected_options=["elevation", "hillshade"])
    session_id = initiated.json()["upload_session_id"]
    _finish_hook(api, session_id, settings)

    from apps.surveys.models import ProcessingRun

    run = ProcessingRun.objects.get()
    assert "point_cloud_3d" not in set(run.options.values_list("option_id", flat=True))


def test_deselect_all_optional_is_required_only_run(api, project, stub_chain, settings):
    initiated = _initiate(api, project, selected_options=[])
    assert initiated.json()["effective_options"] == ["elevation"]

    session_id = initiated.json()["upload_session_id"]
    _finish_hook(api, session_id, settings)

    from apps.surveys.models import ProcessingRun

    run = ProcessingRun.objects.get()
    assert list(run.options.values_list("option_id", flat=True)) == ["elevation"]


def test_omitted_selection_uses_registry_defaults(api, project):
    initiated = _initiate(api, project)
    assert initiated.status_code == 201
    assert set(initiated.json()["effective_options"]) == {
        "elevation",
        "hillshade",
        "point_cloud_3d",
    }


def test_invalid_option_id_rejected(api, project):
    response = _initiate(api, project, selected_options=["nope"])
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_options"
    assert response.json()["error"]["detail"]["invalid"] == ["nope"]


def test_non_list_selection_rejected(api, project):
    response = _initiate(api, project, selected_options="hillshade")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_options"
