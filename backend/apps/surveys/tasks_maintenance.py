"""Periodic maintenance: expire abandoned upload sessions (FR-004) and
physically purge deletions past their recovery window (005 US3).

MinIO/S3 lifecycle rules (see infra/minio-init) reap the staged bytes; this
task expires the UploadSession rows so stale uploads disappear from listings
and never become surveys.
"""

import datetime
import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.projects.models import Project
from pipeline import storage

from .models import Survey, UploadSession

logger = logging.getLogger(__name__)


@shared_task(name="apps.surveys.tasks_maintenance.purge_expired_upload_sessions")
def purge_expired_upload_sessions():
    cutoff = timezone.now() - datetime.timedelta(days=settings.UPLOAD_EXPIRY_DAYS)
    expired = UploadSession.objects.filter(
        state=UploadSession.State.ACTIVE, created_at__lt=cutoff
    ).update(state=UploadSession.State.EXPIRED)
    if expired:
        logger.info("expired %d stale upload sessions", expired)
    return expired


@shared_task(name="apps.surveys.tasks_maintenance.purge_expired_deletions")
def purge_expired_deletions():
    """Deletion/restore only ever flip `deleted_at` (SC-001/SC-007); this is
    the sole code path that removes object-storage files and DB rows, once
    `DELETE_RECOVERY_DAYS` has elapsed. A cascade-deleted survey's cleanup is
    subsumed by its project's own purge — the DB `CASCADE` chain already
    removes it once the project row is deleted (R5)."""
    cutoff = timezone.now() - datetime.timedelta(days=settings.DELETE_RECOVERY_DAYS)

    purged_projects = 0
    for project in Project.objects.filter(deleted_at__isnull=False, deleted_at__lte=cutoff):
        storage.delete_prefix(f"projects/{project.id}/")
        project.delete()
        purged_projects += 1

    purged_surveys = 0
    for survey in Survey.objects.filter(
        deleted_at__isnull=False,
        deleted_at__lte=cutoff,
        deleted_via_project_cascade=False,
        project__deleted_at__isnull=True,
    ):
        storage.delete_prefix(f"projects/{survey.project_id}/surveys/{survey.id}/")
        survey.delete()
        purged_surveys += 1

    if purged_projects or purged_surveys:
        logger.info(
            "purged %d expired projects, %d expired surveys", purged_projects, purged_surveys
        )
    return {"projects": purged_projects, "surveys": purged_surveys}
