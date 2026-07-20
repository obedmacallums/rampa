"""Project<->survey cascade delete/restore (005 US2/US3).

The one place `apps.projects` lazily imports `apps.surveys` from, mirroring
the existing lazy cross-app import style of `access.get_survey_or_404`.
"""

from django.utils import timezone

from .models import Survey


def cascade_delete_surveys_for_project(project, user) -> None:
    """Soft-delete every survey of `project` still active, tagging each as
    cascade-deleted so an already-independently-deleted survey is untouched
    and a later project restore knows which surveys to bring back (R2)."""
    project.surveys.filter(deleted_at__isnull=True).update(
        deleted_at=timezone.now(), deleted_by=user, deleted_via_project_cascade=True
    )


def cascade_restore_surveys_for_project(project, user) -> None:
    """Restore every survey cascade-deleted alongside `project` (R2); a
    survey deleted independently before the project stays deleted."""
    project.surveys.filter(deleted_via_project_cascade=True).update(
        deleted_at=None, deleted_by=None, deleted_via_project_cascade=False
    )
