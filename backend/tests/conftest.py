import shutil
from types import SimpleNamespace

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--laz-sample",
        default=None,
        help="Path to a real LAZ sample for the real_laz end-to-end test",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--laz-sample"):
        return
    skip = pytest.mark.skip(reason="requires --laz-sample <path>")
    for item in items:
        if "real_laz" in item.keywords:
            item.add_marker(skip)


import functools
import subprocess


@functools.cache
def has_binary(name: str) -> bool:
    """True only if the binary exists AND actually runs (a broken install —
    e.g. dangling homebrew dylibs — must skip, not fail)."""
    if shutil.which(name) is None:
        return False
    try:
        return subprocess.run(
            [name, "--version"], capture_output=True, timeout=15
        ).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


requires_pdal = pytest.mark.skipif(not has_binary("pdal"), reason="pdal not available/working")


@pytest.fixture
def fixture_dir(tmp_path):
    return tmp_path


@pytest.fixture
def user(db):
    from django.contrib.auth.models import User

    return User.objects.create_user("demo", password="demo1234")


@pytest.fixture
def api(client, user):
    client.login(username="demo", password="demo1234")
    return client


@pytest.fixture
def crs_entry(db):
    from apps.projects.models import CrsCatalogEntry

    return CrsCatalogEntry.objects.create(code="EPSG:32719", label_key="crs.wgs84_utm_19s")


@pytest.fixture
def project(db, user, crs_entry):
    from apps.projects.models import Project, ProjectMembership

    project = Project.objects.create(name="Rajo Norte", crs=crs_entry, created_by=user)
    ProjectMembership.objects.create(
        project=project, user=user, role=ProjectMembership.Role.OWNER, granted_by=user
    )
    return project


@pytest.fixture
def stub_chain(monkeypatch):
    """Let enqueue_run persist the run without dispatching Celery."""
    calls = []

    def fake_chain(*sigs):
        calls.append(sigs)
        return SimpleNamespace(apply_async=lambda: None)

    monkeypatch.setattr("apps.surveys.tasks.chain", fake_chain)
    return calls


def touch_file(dest):
    """Write a tiny placeholder file so code that only checks for existence
    (not real pdal/gdal output) is satisfied."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"x")
    return dest


def run_chain(stub_chain):
    """Execute every signature `enqueue_run` would have dispatched to Celery,
    synchronously and in order — pairs with the `stub_chain` fixture."""
    assert len(stub_chain) == 1
    for sig in stub_chain[-1]:
        sig()


@pytest.fixture
def fake_pipeline(monkeypatch):
    """Stub every filesystem/subprocess/object-storage touchpoint so the real
    orchestration (enqueue_run + task chain) can run synchronously in tests
    without pdal/gdal/S3 or a Celery broker."""
    from apps.surveys import tasks as tasks_mod
    from pipeline.stages import surfaces as surfaces_mod
    from pipeline.stages.validate import ValidationResult

    monkeypatch.setattr(tasks_mod.storage, "download_to", lambda key, dest: touch_file(dest))
    monkeypatch.setattr(tasks_mod.storage, "upload_file", lambda path, key: None)
    monkeypatch.setattr(tasks_mod.storage, "assert_key_within_survey", lambda *a, **k: None)
    monkeypatch.setattr(tasks_mod.storage, "copy_object", lambda *a, **k: None)
    monkeypatch.setattr(tasks_mod.storage, "delete_object", lambda *a, **k: None)
    monkeypatch.setattr(
        tasks_mod,
        "validate_file",
        lambda path: ValidationResult(
            source_format="laz", point_count=10, crs_wkt="fake", sha256="v" * 64
        ),
    )
    monkeypatch.setattr(tasks_mod, "reproject", lambda local, crs, dest: touch_file(dest))

    def fake_elevation(ctx):
        ctx.workdir.mkdir(parents=True, exist_ok=True)
        dem = ctx.workdir / "dem.tif"
        dem.write_bytes(b"dem")
        return surfaces_mod.SurfaceArtifact(
            kind="dem", path=dem, sha256="d" * 64, size_bytes=3, resolution_m=0.2
        )

    def fake_hillshade(ctx, dem_path):
        ctx.workdir.mkdir(parents=True, exist_ok=True)
        hillshade = ctx.workdir / "hillshade.tif"
        hillshade.write_bytes(b"hillshade")
        return surfaces_mod.SurfaceArtifact(
            kind="hillshade", path=hillshade, sha256="h" * 64, size_bytes=9, resolution_m=0.2
        )

    def fake_point_cloud_3d(ctx):
        ctx.workdir.mkdir(parents=True, exist_ok=True)
        copc = ctx.workdir / "cloud.copc.laz"
        copc.write_bytes(b"copc")
        return surfaces_mod.SurfaceArtifact(
            kind="copc", path=copc, sha256="c" * 64, size_bytes=4, resolution_m=None
        )

    monkeypatch.setattr(surfaces_mod, "produce_elevation", fake_elevation)
    monkeypatch.setattr(surfaces_mod, "produce_hillshade", fake_hillshade)
    monkeypatch.setattr(surfaces_mod, "produce_point_cloud_3d", fake_point_cloud_3d)
    return monkeypatch
