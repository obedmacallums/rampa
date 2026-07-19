"""Periodic maintenance: expire abandoned upload sessions (FR-004).

MinIO/S3 lifecycle rules (see infra/minio-init) reap the staged bytes; this
task expires the UploadSession rows so stale uploads disappear from listings
and never become surveys.
"""

import datetime
import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import UploadSession

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
