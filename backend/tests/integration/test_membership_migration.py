"""002 T021: owner backfill for pre-existing projects (US4, FR-010).

Exercises the data-migration function directly against the live registry:
every project ends with exactly one owner membership for its creator,
``granted_by=NULL`` (system), idempotently and without touching projects
that already have memberships.
"""

from importlib import import_module

import pytest
from django.apps import apps as global_apps
from django.contrib.auth.models import User

from apps.projects.models import Project, ProjectMembership

pytestmark = pytest.mark.django_db

backfill = import_module("apps.projects.migrations.0003_backfill_owner_memberships").backfill


@pytest.fixture
def legacy_projects(crs_entry):
    """Projects created before 002: no membership rows at all."""
    users = [User.objects.create_user(f"creator{i}", password="x12345678") for i in range(2)]
    return [
        Project.objects.create(name=f"Faena {i}", crs=crs_entry, created_by=users[i])
        for i in range(2)
    ]


def test_backfill_promotes_each_creator_to_owner(legacy_projects):
    backfill(global_apps, None)
    for project in legacy_projects:
        memberships = ProjectMembership.objects.filter(project=project)
        assert memberships.count() == 1
        membership = memberships.get()
        assert membership.user == project.created_by
        assert membership.role == ProjectMembership.Role.OWNER
        assert membership.granted_by is None  # rendered as "system" (FR-009)


def test_backfill_is_idempotent(legacy_projects):
    backfill(global_apps, None)
    backfill(global_apps, None)
    assert ProjectMembership.objects.count() == len(legacy_projects)


def test_backfill_leaves_existing_memberships_untouched(legacy_projects):
    project = legacy_projects[0]
    existing = ProjectMembership.objects.create(
        project=project,
        user=project.created_by,
        role=ProjectMembership.Role.OWNER,
        granted_by=project.created_by,
    )
    backfill(global_apps, None)
    existing.refresh_from_db()
    assert existing.granted_by == project.created_by  # not overwritten to "system"
    assert ProjectMembership.objects.filter(project=project).count() == 1
