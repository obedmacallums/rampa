"""T015: GET /processing-options catalog contract (contracts/rest-api.md)."""

import pytest

pytestmark = pytest.mark.django_db


def test_catalog_shape_and_flags(api):
    response = api.get("/api/v1/processing-options")
    assert response.status_code == 200
    body = response.json()
    assert body["input_type"] == "point_cloud"
    options = {o["id"]: o for o in body["options"]}
    assert set(options) == {"elevation", "hillshade", "point_cloud_3d"}

    elevation = options["elevation"]
    assert elevation["required"] is True
    assert elevation["default_selected"] is True
    assert elevation["prerequisites"] == []
    assert elevation["target_view"] == "map2d"
    assert elevation["label_key"] == "options.elevation.label"
    assert elevation["description_key"] == "options.elevation.description"

    hillshade = options["hillshade"]
    assert hillshade["required"] is False
    assert hillshade["prerequisites"] == ["elevation"]
    assert hillshade["target_view"] == "map2d"

    point_cloud_3d = options["point_cloud_3d"]
    assert point_cloud_3d["required"] is False
    assert point_cloud_3d["target_view"] == "view3d"
    assert point_cloud_3d["prerequisites"] == []

    # i18n keys only — never display text (Principle IX)
    for option in body["options"]:
        assert option["label_key"].startswith("options.")
        assert option["description_key"].startswith("options.")


def test_catalog_defaults_to_point_cloud(api):
    default_response = api.get("/api/v1/processing-options")
    explicit_response = api.get("/api/v1/processing-options?input_type=point_cloud")
    assert default_response.json() == explicit_response.json()


def test_catalog_unknown_input_type_400(api):
    response = api.get("/api/v1/processing-options?input_type=nope")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_input_type"


def test_catalog_requires_auth(client):
    response = client.get("/api/v1/processing-options")
    assert response.status_code == 401
