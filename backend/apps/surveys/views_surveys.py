"""Survey listing, status polling, retry, and artifact delivery (contracts)."""

import datetime

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.errors import ApiError
from apps.projects import access
from pipeline import options as registry
from pipeline import storage

from .models import DerivedArtifact, ProcessingRun, Survey
from .resolution import resolve_products
from .serializers import RunStatusSerializer, SurveyDetailSerializer, SurveySummarySerializer
from .tasks import enqueue_run


class ProjectSurveysView(APIView):
    def get(self, request, project_id):
        project = access.get_project_or_404(request.user, project_id)
        surveys = (
            project.surveys.filter(deleted_at__isnull=True)
            .prefetch_related("runs")
            .order_by("capture_date", "created_at")
        )
        return Response(SurveySummarySerializer(surveys, many=True).data)


class SurveyDetailView(APIView):
    def get(self, request, survey_id):
        survey = access.get_survey_or_404(
            request.user, survey_id, queryset=Survey.objects.prefetch_related("runs")
        )
        return Response(SurveyDetailSerializer(survey).data)

    def delete(self, request, survey_id):
        """Owner-only soft delete, unaffected by anything else in the
        project (FR-001); blocked while processing is in flight (R4)."""
        survey = access.get_survey_or_404(request.user, survey_id)
        if not access.is_owner(request.user, survey.project):
            raise ApiError("not_owner", status_code=403)
        if survey.status in (Survey.Status.QUEUED, Survey.Status.PROCESSING):
            raise ApiError("not_deletable", status_code=409)
        survey.deleted_at = timezone.now()
        survey.deleted_by = request.user
        survey.save(update_fields=["deleted_at", "deleted_by"])
        return Response(status=204)


class SurveyRestoreView(APIView):
    """Owner-only restore of an independently-deleted survey within its
    recovery window (US3); has no effect on a survey currently
    cascade-deleted with its still-deleted project (FR-011) — every other
    failure collapses into the same 404 `not_restorable` (R7)."""

    @transaction.atomic
    def post(self, request, survey_id):
        try:
            survey = Survey.objects.select_related("project").select_for_update().get(id=survey_id)
        except Survey.DoesNotExist:
            raise ApiError("not_restorable", status_code=404) from None
        if not survey.project.memberships.filter(user=request.user).exists():
            raise ApiError("not_restorable", status_code=404)
        if not access.is_owner(request.user, survey.project):
            raise ApiError("not_owner", status_code=403)

        cutoff = timezone.now() - datetime.timedelta(days=settings.DELETE_RECOVERY_DAYS)
        if (
            survey.deleted_at is None
            or survey.deleted_at < cutoff
            or survey.deleted_via_project_cascade
        ):
            raise ApiError("not_restorable", status_code=404)

        survey.deleted_at = None
        survey.deleted_by = None
        survey.save(update_fields=["deleted_at", "deleted_by"])
        return Response(SurveySummarySerializer(survey).data)


class SurveyRetryView(APIView):
    def post(self, request, survey_id):
        survey = access.get_survey_or_404(request.user, survey_id)
        if survey.status != Survey.Status.FAILED:
            raise ApiError("not_retriable", status_code=409)
        run = enqueue_run(survey)  # new run, source re-used — no re-upload (FR-012)
        return Response({"run": RunStatusSerializer(run).data}, status=202)


class SurveyProcessView(APIView):
    """US3: request additional products on an already-processed survey,
    reusing its stored source file — no re-upload, no new upload session."""

    def post(self, request, survey_id):
        survey = access.get_survey_or_404(request.user, survey_id)
        if survey.status in (Survey.Status.QUEUED, Survey.Status.PROCESSING):
            raise ApiError("not_processable", status_code=409)

        requested_options = request.data.get("selected_options")
        if not isinstance(requested_options, list) or not all(
            isinstance(x, str) for x in requested_options
        ):
            raise ApiError("invalid_options", detail={"invalid": []})

        try:
            # enqueue_run unions this with whatever the survey already has
            # selected, validating only the genuinely new ids (R5) — options
            # already completed in a prior run become `reused`, not
            # re-executed.
            run = enqueue_run(survey, selection=requested_options)
        except registry.InvalidSelectionError as exc:
            raise ApiError("invalid_options", detail={"invalid": exc.invalid_ids}) from None

        return Response({"run": RunStatusSerializer(run).data}, status=202)


class SurveyArtifactsView(APIView):
    def get(self, request, survey_id):
        survey = access.get_survey_or_404(request.user, survey_id)
        resolved = resolve_products(survey)
        if not resolved:
            raise ApiError("not_ready", status_code=409)

        expires_in = settings.PRESIGN_EXPIRY_SECONDS
        products = {
            option_id: _artifact_payload(artifact, run, expires_in)
            for option_id, (artifact, run) in resolved.items()
        }
        return Response({"input_type": survey.input_type, "products": products})


def _artifact_payload(artifact: DerivedArtifact, run: ProcessingRun, expires_in: int) -> dict:
    # titiler fetches the COG itself, so its URL is signed for the internal
    # endpoint; browser-facing URLs are signed for the public one (R10).
    base = {"run_id": str(run.id), "kind": artifact.kind, "sha256": artifact.sha256}

    if artifact.kind == DerivedArtifact.Kind.DEM:
        internal = storage.presign_get(artifact.storage_key, public=False)
        return {
            **base,
            "url": storage.presign_get(artifact.storage_key),
            "tilejson_url": (
                f"{settings.TITILER_PUBLIC_URL}/cog/WebMercatorQuad/tilejson.json?url="
                + _urlquote(internal)
            ),
            "statistics_url": (
                f"{settings.TITILER_PUBLIC_URL}/cog/statistics?url=" + _urlquote(internal)
            ),
            "size_bytes": artifact.size_bytes,
            "resolution_m": str(artifact.resolution_m),
            "expires_in": expires_in,
        }

    if artifact.kind == DerivedArtifact.Kind.HILLSHADE:
        internal = storage.presign_get(artifact.storage_key, public=False)
        return {
            **base,
            "tile_url_template": (
                f"{settings.TITILER_PUBLIC_URL}/cog/tiles/WebMercatorQuad"
                "/{z}/{x}/{y}.png?url=" + _urlquote(internal)
            ),
            "tilejson_url": (
                f"{settings.TITILER_PUBLIC_URL}/cog/WebMercatorQuad/tilejson.json?url="
                + _urlquote(internal)
            ),
            "cog_url": storage.presign_get(artifact.storage_key),
            "expires_in": expires_in,
        }

    # copc / any other kind with a direct download URL
    return {
        **base,
        "url": storage.presign_get(artifact.storage_key),
        "size_bytes": artifact.size_bytes,
        "expires_in": expires_in,
    }


def _urlquote(value: str) -> str:
    from urllib.parse import quote

    return quote(value, safe="")
