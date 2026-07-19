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
    from apps.projects.models import Project

    return Project.objects.create(name="Rajo Norte", crs=crs_entry, created_by=user)


@pytest.fixture
def stub_chain(monkeypatch):
    """Let enqueue_run persist the run without dispatching Celery."""
    calls = []

    def fake_chain(*sigs):
        calls.append(sigs)
        return SimpleNamespace(apply_async=lambda: None)

    monkeypatch.setattr("apps.surveys.tasks.chain", fake_chain)
    return calls
