"""T030: purge_expired_deletions physically removes rows + storage past the
recovery window (US3, quickstart Scenario 7)."""

import datetime

import pytest
from django.conf import settings
from django.utils import timezone

from apps.projects.models import Project, ProjectMembership
from apps.surveys.models import Survey
from apps.surveys.tasks_maintenance import purge_expired_deletions
from pipeline import storage

pytestmark = pytest.mark.django_db


@pytest.fixture
def bucket_client():
    client = storage.internal_client()
    try:
        client.head_bucket(Bucket=settings.S3_BUCKET)
    except Exception:
        pytest.skip("MinIO/S3 not reachable — run against the compose stack")
    return client


def _survey(project, user, name="vuelo.laz"):
    return Survey.objects.create(
        project=project,
        name=name,
        capture_date="2026-01-01",
        source_size_bytes=1,
        source_key="tus-staging/x",
        created_by=user,
    )


def _exists(client, key):
    from botocore.exceptions import ClientError

    try:
        client.head_object(Bucket=settings.S3_BUCKET, Key=key)
        return True
    except ClientError:
        return False


def test_expired_project_purged_db_and_storage(bucket_client, user, crs_entry):
    project = Project.objects.create(name="Rajo Expirado", crs=crs_entry, created_by=user)
    ProjectMembership.objects.create(
        project=project, user=user, role=ProjectMembership.Role.OWNER, granted_by=user
    )
    survey = _survey(project, user)
    key = f"projects/{project.id}/surveys/{survey.id}/source/x.laz"
    bucket_client.put_object(Bucket=settings.S3_BUCKET, Key=key, Body=b"x")

    project.deleted_at = timezone.now() - datetime.timedelta(
        days=settings.DELETE_RECOVERY_DAYS + 1
    )
    project.deleted_by = user
    project.save()

    purge_expired_deletions()

    assert not Project.objects.filter(id=project.id).exists()
    assert not Survey.objects.filter(id=survey.id).exists()
    assert not _exists(bucket_client, key)


def test_expired_independent_survey_purged_db_and_storage(bucket_client, project, user):
    survey = _survey(project, user)
    key = f"projects/{project.id}/surveys/{survey.id}/source/x.laz"
    bucket_client.put_object(Bucket=settings.S3_BUCKET, Key=key, Body=b"x")

    survey.deleted_at = timezone.now() - datetime.timedelta(
        days=settings.DELETE_RECOVERY_DAYS + 1
    )
    survey.deleted_by = user
    survey.deleted_via_project_cascade = False
    survey.save()

    purge_expired_deletions()

    assert not Survey.objects.filter(id=survey.id).exists()
    assert not _exists(bucket_client, key)
    assert Project.objects.filter(id=project.id).exists()


def test_deletion_within_window_untouched(project, user):
    survey = _survey(project, user)
    survey.deleted_at = timezone.now()
    survey.deleted_by = user
    survey.save()

    purge_expired_deletions()

    assert Survey.objects.filter(id=survey.id).exists()
    assert Project.objects.filter(id=project.id).exists()
