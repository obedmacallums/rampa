"""Survey listing, status polling, retry, and artifact delivery (contracts)."""

from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.errors import ApiError
from apps.projects import access
from pipeline import storage

from .models import DerivedArtifact, ProcessingRun, Survey
from .serializers import RunStatusSerializer, SurveyDetailSerializer, SurveySummarySerializer
from .tasks import enqueue_run


class ProjectSurveysView(APIView):
    def get(self, request, project_id):
        project = access.get_project_or_404(request.user, project_id)
        surveys = project.surveys.prefetch_related("runs").order_by("capture_date", "created_at")
        return Response(SurveySummarySerializer(surveys, many=True).data)


class SurveyDetailView(APIView):
    def get(self, request, survey_id):
        survey = access.get_survey_or_404(
            request.user, survey_id, queryset=Survey.objects.prefetch_related("runs")
        )
        return Response(SurveyDetailSerializer(survey).data)


class SurveyRetryView(APIView):
    def post(self, request, survey_id):
        survey = access.get_survey_or_404(request.user, survey_id)
        if survey.status != Survey.Status.FAILED:
            raise ApiError("not_retriable", status_code=409)
        run = enqueue_run(survey)  # new run, source re-used — no re-upload (FR-012)
        return Response({"run": RunStatusSerializer(run).data}, status=202)


class SurveyArtifactsView(APIView):
    def get(self, request, survey_id):
        survey = access.get_survey_or_404(request.user, survey_id)
        run = (
            ProcessingRun.objects.filter(survey=survey, state=ProcessingRun.State.COMPLETED)
            .order_by("-number")
            .first()
        )
        if run is None:
            raise ApiError("not_ready", status_code=409)

        artifacts = {a.kind: a for a in run.artifacts.all()}
        dem = artifacts.get(DerivedArtifact.Kind.DEM)
        copc = artifacts.get(DerivedArtifact.Kind.COPC)
        hillshade = artifacts.get(DerivedArtifact.Kind.HILLSHADE)
        if not (dem and copc and hillshade):
            raise ApiError("not_ready", status_code=409)

        # titiler fetches the COG itself, so its URL is signed for the internal
        # endpoint; browser-facing URLs are signed for the public one (R10).
        hillshade_internal = storage.presign_get(hillshade.storage_key, public=False)
        dem_internal = storage.presign_get(dem.storage_key, public=False)
        expires_in = settings.PRESIGN_EXPIRY_SECONDS
        return Response(
            {
                "run_id": str(run.id),
                "dem": {
                    "url": storage.presign_get(dem.storage_key),
                    "tilejson_url": (
                        f"{settings.TITILER_PUBLIC_URL}/cog/WebMercatorQuad/tilejson.json?url="
                        + _urlquote(dem_internal)
                    ),
                    "statistics_url": (
                        f"{settings.TITILER_PUBLIC_URL}/cog/statistics?url="
                        + _urlquote(dem_internal)
                    ),
                    "sha256": dem.sha256,
                    "size_bytes": dem.size_bytes,
                    "resolution_m": str(dem.resolution_m),
                    "expires_in": expires_in,
                },
                "copc": {
                    "url": storage.presign_get(copc.storage_key),
                    "sha256": copc.sha256,
                    "size_bytes": copc.size_bytes,
                    "expires_in": expires_in,
                },
                "hillshade": {
                    "tile_url_template": (
                        f"{settings.TITILER_PUBLIC_URL}/cog/tiles/WebMercatorQuad"
                        "/{z}/{x}/{y}.png?url=" + _urlquote(hillshade_internal)
                    ),
                    "tilejson_url": (
                        f"{settings.TITILER_PUBLIC_URL}/cog/WebMercatorQuad/tilejson.json?url="
                        + _urlquote(hillshade_internal)
                    ),
                    "cog_url": storage.presign_get(hillshade.storage_key),
                    "sha256": hillshade.sha256,
                    "expires_in": expires_in,
                },
            }
        )


def _urlquote(value: str) -> str:
    from urllib.parse import quote

    return quote(value, safe="")
