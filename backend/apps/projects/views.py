from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count
from django.http import Http404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.errors import ApiError

from . import access
from .models import CrsCatalogEntry, Project, ProjectMembership
from .serializers import (
    CrsCatalogSerializer,
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
            .annotate(survey_count=Count("surveys"))
            .order_by("name")
        )
        return Response(ProjectSummarySerializer(projects, many=True).data)

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
