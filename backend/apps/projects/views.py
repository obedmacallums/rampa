from django.db.models import Count
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.errors import ApiError

from .models import CrsCatalogEntry, Project
from .serializers import CrsCatalogSerializer, ProjectSummarySerializer


class CrsCatalogView(APIView):
    def get(self, request):
        entries = CrsCatalogEntry.objects.filter(is_active=True).order_by("code")
        return Response(CrsCatalogSerializer(entries, many=True).data)


class ProjectListCreateView(APIView):
    def get(self, request):
        projects = (
            Project.objects.select_related("crs")
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
        project = Project.objects.create(name=name, crs=crs, created_by=request.user)
        project.survey_count = 0
        return Response(ProjectSummarySerializer(project).data, status=201)
