"""T026: extensibility proof (US2, SC-003, FR-013). A new option must be pure
registration — OptionSpec + producer + i18n keys — with zero changes to
orchestration, serializers, or views. This test only IMPORTS those modules
(apps.surveys.tasks/serializers/views_*): it never edits them, and the dummy
option/input-type it registers are the only thing that makes it selectable,
executable, and resolvable end to end.
"""

import pytest
from django.conf import settings

from apps.surveys.models import DerivedArtifact, ProcessingRun
from pipeline import options as registry
from pipeline.stages.context import RunContext
from pipeline.stages.surfaces import SurfaceArtifact
from pipeline.storage import sha256_of_file
from tests.conftest import run_chain

pytestmark = pytest.mark.django_db


def _test_flag_producer(ctx: RunContext) -> dict:
    ctx.workdir.mkdir(parents=True, exist_ok=True)
    marker = ctx.workdir / "flag.txt"
    marker.write_bytes(b"ok")
    return {
        "test_flag": SurfaceArtifact(
            kind="test_flag",
            path=marker,
            sha256=sha256_of_file(marker),
            size_bytes=marker.stat().st_size,
            resolution_m=None,
        )
    }


@pytest.fixture
def dummy_option():
    spec = registry.OptionSpec(
        id="test_flag",
        label_key="options.test_flag.label",
        description_key="options.test_flag.description",
        input_types=frozenset({"point_cloud"}),
        target_view="map2d",
        required=False,
        default_selected=False,
        active=True,
        prerequisites=(),
        producer=_test_flag_producer,
    )
    registry.register_option(spec)
    registry.validate_registry()
    yield spec
    del registry._options["test_flag"]


@pytest.fixture
def dummy_input_type():
    registry.register_input_type(
        registry.InputTypeSpec(id="test_input", label_key="input_types.test_input.label")
    )
    registry.register_option(
        registry.OptionSpec(
            id="test_input_required",
            label_key="options.test_input_required.label",
            description_key="options.test_input_required.description",
            input_types=frozenset({"test_input"}),
            target_view="map2d",
            required=True,
            default_selected=True,
            active=True,
            prerequisites=(),
            producer=lambda ctx: {},
        )
    )
    registry.validate_registry()
    yield
    del registry._options["test_input_required"]
    del registry._input_types["test_input"]


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


def _finish_hook(api, session_id):
    payload = {
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
    return api.post(
        "/api/v1/hooks/tusd",
        payload,
        content_type="application/json",
        headers={"X-Rampa-Hook-Secret": settings.TUSD_HOOK_SECRET},
    )


def test_dummy_option_selectable_executes_and_resolves(
    api, project, dummy_option, stub_chain, fake_pipeline
):
    # 1. Appears in the catalog endpoint (T014, unmodified).
    catalog = api.get("/api/v1/processing-options").json()
    assert "test_flag" in {o["id"] for o in catalog["options"]}

    # 2. Selectable at upload initiation (T016, unmodified).
    initiated = _initiate(api, project, selected_options=["test_flag"])
    assert initiated.status_code == 201
    assert "test_flag" in initiated.json()["effective_options"]

    session_id = initiated.json()["upload_session_id"]
    _finish_hook(api, session_id)

    run = ProcessingRun.objects.get()
    assert "test_flag" in set(run.options.values_list("option_id", flat=True))

    # 3. Executes in a run (T009's dynamic chain, unmodified) and publishes
    # an attributed artifact.
    run_chain(stub_chain)
    run.refresh_from_db()
    test_flag_option = run.options.get(option_id="test_flag")
    assert test_flag_option.state == "completed"
    artifact = DerivedArtifact.objects.get(option_id="test_flag")
    assert artifact.kind == "test_flag"

    # 4. Resolves in /artifacts products (T019, unmodified).
    products = api.get(f"/api/v1/surveys/{run.survey_id}/artifacts").json()["products"]
    assert "test_flag" in products


def test_dummy_input_type_catalog_and_selection_isolated(api, dummy_input_type):
    # Catalog filtered by input_type returns only its own options — the
    # point_cloud catalog is unaffected (FR-013 extensibility proof).
    point_cloud_catalog = api.get("/api/v1/processing-options").json()
    assert "test_input_required" not in {o["id"] for o in point_cloud_catalog["options"]}

    test_input_catalog = api.get("/api/v1/processing-options?input_type=test_input").json()
    assert {o["id"] for o in test_input_catalog["options"]} == {"test_input_required"}

    # effective_selection validates ids against the *requested* input type only.
    effective = registry.effective_selection("test_input", [])
    assert effective == ["test_input_required"]
    with pytest.raises(registry.InvalidSelectionError):
        registry.effective_selection("test_input", ["elevation"])  # point_cloud-only id
    with pytest.raises(registry.InvalidSelectionError):
        registry.effective_selection("point_cloud", ["test_input_required"])
