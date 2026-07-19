"""Membership-scoped access helpers — the single enforcement point (002 R1).

User-request views must resolve projects and surveys through these helpers,
never through ``Project.objects`` / ``Survey.objects`` directly, so denial to
non-members raises the same 404 as true nonexistence (FR-002). Server-to-server
paths (tusd hook, pipeline tasks) act as the platform and stay unscoped
(FR-012).
"""

from django.http import Http404

from .models import Project, ProjectMembership


def projects_for(user):
    """Projects visible to ``user``: exactly their memberships (FR-001)."""
    return Project.objects.filter(memberships__user=user)


def get_project_or_404(user, project_id):
    try:
        return projects_for(user).get(id=project_id)
    except Project.DoesNotExist:
        raise Http404 from None


def get_survey_or_404(user, survey_id, queryset=None):
    """Resolve a survey through the caller's project scope (FR-002)."""
    from apps.surveys.models import Survey

    qs = queryset if queryset is not None else Survey.objects.all()
    try:
        return qs.filter(project__memberships__user=user).get(id=survey_id)
    except Survey.DoesNotExist:
        raise Http404 from None


def is_owner(user, project) -> bool:
    return ProjectMembership.objects.filter(
        project=project, user=user, role=ProjectMembership.Role.OWNER
    ).exists()
