import datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.errors import ApiError

from . import access
from .models import CrsCatalogEntry, Project, ProjectMembership
from .serializers import (
    CrsCatalogSerializer,
    DeletedProjectSerializer,
    ProjectMembershipSerializer,
    ProjectSummarySerializer,
)


class CrsCatalogView(APIView):
    def get(self, request):
        entries = CrsCatalogEntry.objects.filter(is_active=True).order_by("code")
        return Response(CrsCatalogSerializer(entries, many=True).data)


class ProjectListCreateView(APIView):
    def get(self, request):
        projects = (
            access.projects_for(request.user)
            .select_related("crs")
            .annotate(survey_count=Count("surveys", filter=Q(surveys__deleted_at__isnull=True)))
            .order_by("name")
        )
        return Response(
            ProjectSummarySerializer(projects, many=True, context={"request": request}).data
        )

    def post(self, request):
        name = (request.data.get("name") or "").strip()
        crs_id = request.data.get("crs_id")
        if not name or len(name) > 120:
            raise ApiError("invalid_name")
        if Project.objects.filter(name__iexact=name).exists():
            raise ApiError("name_taken")
        try:
            crs = CrsCatalogEntry.objects.get(id=crs_id, is_active=True)
        except CrsCatalogEntry.DoesNotExist:
            raise ApiError("invalid_crs") from None
        with transaction.atomic():
            project = Project.objects.create(name=name, crs=crs, created_by=request.user)
            ProjectMembership.objects.create(
                project=project,
                user=request.user,
                role=ProjectMembership.Role.OWNER,
                granted_by=request.user,
            )
        project.survey_count = 0
        return Response(ProjectSummarySerializer(project).data, status=201)


class ProjectDetailView(APIView):
    @transaction.atomic
    def delete(self, request, project_id):
        """Owner-only soft delete, cascading to every survey still active at
        that moment (FR-002/FR-011); blocked while a survey is
        queued/processing or an upload is active (R4)."""
        from apps.surveys.deletion import cascade_delete_surveys_for_project
        from apps.surveys.models import Survey, UploadSession

        project = access.get_project_or_404(request.user, project_id)
        _require_owner(request.user, project)

        blocked_survey = project.surveys.filter(
            deleted_at__isnull=True,
            status__in=[Survey.Status.QUEUED, Survey.Status.PROCESSING],
        ).exists()
        blocked_upload = project.upload_sessions.filter(
            state=UploadSession.State.ACTIVE
        ).exists()
        if blocked_survey or blocked_upload:
            raise ApiError("not_deletable", status_code=409)

        project.deleted_at = timezone.now()
        project.deleted_by = request.user
        project.save(update_fields=["deleted_at", "deleted_by"])
        cascade_delete_surveys_for_project(project, request.user)
        return Response(status=204)


class ProjectRestoreView(APIView):
    """Owner-only restore within the recovery window (US3); cascade-restores
    every survey that was cascade-deleted with the project (FR-010/FR-011).

    Every failure other than a plain non-owner (never deleted, already
    restored, past the window, not a member, never existed) collapses into
    the same 404 `not_restorable` — no case is distinguishable (R7)."""

    @transaction.atomic
    def post(self, request, project_id):
        from apps.surveys.deletion import cascade_restore_surveys_for_project

        try:
            project = Project.objects.select_for_update().get(id=project_id)
        except Project.DoesNotExist:
            raise ApiError("not_restorable", status_code=404) from None
        if not project.memberships.filter(user=request.user).exists():
            raise ApiError("not_restorable", status_code=404)
        _require_owner(request.user, project)

        cutoff = timezone.now() - datetime.timedelta(days=settings.DELETE_RECOVERY_DAYS)
        if project.deleted_at is None or project.deleted_at < cutoff:
            raise ApiError("not_restorable", status_code=404)

        project.deleted_at = None
        project.deleted_by = None
        project.save(update_fields=["deleted_at", "deleted_by"])
        cascade_restore_surveys_for_project(project, request.user)

        project.survey_count = project.surveys.filter(deleted_at__isnull=True).count()
        return Response(ProjectSummarySerializer(project, context={"request": request}).data)


class RecentlyDeletedView(APIView):
    """Global (not project-scoped) listing of everything the requester can
    still restore (US3): projects they own that are soft-deleted, and
    surveys they independently deleted (cascade-deleted surveys come back
    only as part of restoring their project, R3)."""

    def get(self, request):
        from apps.surveys.models import Survey
        from apps.surveys.serializers import DeletedSurveySerializer

        owned_project_ids = ProjectMembership.objects.filter(
            user=request.user, role=ProjectMembership.Role.OWNER
        ).values_list("project_id", flat=True)

        projects = (
            Project.objects.filter(id__in=owned_project_ids, deleted_at__isnull=False)
            .select_related("crs")
            .annotate(survey_count=Count("surveys", filter=Q(surveys__deleted_at__isnull=True)))
            .order_by("-deleted_at")
        )
        surveys = (
            Survey.objects.filter(
                project_id__in=owned_project_ids,
                deleted_at__isnull=False,
                deleted_via_project_cascade=False,
            )
            .select_related("project")
            .order_by("-deleted_at")
        )
        return Response(
            {
                "projects": DeletedProjectSerializer(projects, many=True).data,
                "surveys": DeletedSurveySerializer(surveys, many=True).data,
            }
        )


def _require_owner(user, project):
    """Mutations are owner-only; a member already sees the project, so a plain
    403 leaks no existence (contracts/rest-api.md)."""
    if not access.is_owner(user, project):
        raise ApiError("not_owner", status_code=403)


def _other_owners_exist(project, membership) -> bool:
    """FR-006 guard; call inside a transaction holding select_for_update."""
    return (
        project.memberships.filter(role=ProjectMembership.Role.OWNER)
        .exclude(id=membership.id)
        .exists()
    )


class ProjectMembersView(APIView):
    def get(self, request, project_id):
        project = access.get_project_or_404(request.user, project_id)
        memberships = project.memberships.select_related("user", "granted_by").order_by(
            "granted_at"
        )
        return Response(ProjectMembershipSerializer(memberships, many=True).data)

    def post(self, request, project_id):
        project = access.get_project_or_404(request.user, project_id)
        _require_owner(request.user, project)

        role = request.data.get("role") or ProjectMembership.Role.MEMBER
        if role not in ProjectMembership.Role.values:
            raise ApiError("invalid_role")
        username = (request.data.get("username") or "").strip()
        try:
            target = get_user_model().objects.get(username=username)
        except get_user_model().DoesNotExist:
            raise ApiError("user_not_found", status_code=404) from None
        if project.memberships.filter(user=target).exists():
            raise ApiError("already_member", status_code=409)

        membership = ProjectMembership.objects.create(
            project=project, user=target, role=role, granted_by=request.user
        )
        return Response(ProjectMembershipSerializer(membership).data, status=201)


class ProjectMemberDetailView(APIView):
    def _membership(self, request, project_id, username):
        project = access.get_project_or_404(request.user, project_id)
        _require_owner(request.user, project)
        # Lock every membership row of the project so the ≥1-owner count
        # (FR-006) cannot race with a concurrent downgrade/removal.
        rows = {
            m.user.username: m
            for m in project.memberships.select_for_update().select_related("user")
        }
        if username not in rows:
            raise Http404
        return project, rows[username]

    @transaction.atomic
    def patch(self, request, project_id, username):
        project, membership = self._membership(request, project_id, username)
        role = request.data.get("role")
        if role not in ProjectMembership.Role.values:
            raise ApiError("invalid_role")
        if (
            membership.role == ProjectMembership.Role.OWNER
            and role == ProjectMembership.Role.MEMBER
            and not _other_owners_exist(project, membership)
        ):
            raise ApiError("last_owner", status_code=409)
        membership.role = role
        membership.save(update_fields=["role"])
        return Response(ProjectMembershipSerializer(membership).data)

    @transaction.atomic
    def delete(self, request, project_id, username):
        project, membership = self._membership(request, project_id, username)
        if membership.role == ProjectMembership.Role.OWNER and not _other_owners_exist(
            project, membership
        ):
            raise ApiError("last_owner", status_code=409)
        membership.delete()
        return Response(status=204)
