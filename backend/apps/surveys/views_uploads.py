"""Upload initiation and pending-upload listing (contracts: Uploads)."""

import datetime
import urllib.request

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.errors import ApiError
from apps.projects.models import Project

from .models import UploadSession
from .serializers import UploadSessionSerializer


def _tus_offset(tus_upload_id: str) -> int | None:
    """Best-effort progress from tusd; listing must not fail if tusd is down."""
    try:
        req = urllib.request.Request(
            settings.TUS_INTERNAL_URL + tus_upload_id,
            method="HEAD",
            headers={"Tus-Resumable": "1.0.0"},
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            return int(resp.headers.get("Upload-Offset", 0))
    except Exception:
        return None


class ProjectUploadsView(APIView):
    def post(self, request, project_id):
        project = get_object_or_404(Project, id=project_id)
        filename = (request.data.get("filename") or "").strip()
        size = request.data.get("size_bytes")
        capture_date = request.data.get("capture_date")

        if not isinstance(size, int) or size <= 0:
            raise ApiError("invalid_size")
        if size > settings.MAX_UPLOAD_BYTES:
            raise ApiError("file_too_large", detail={"max_bytes": settings.MAX_UPLOAD_BYTES})
        if not filename.lower().endswith(settings.SUPPORTED_EXTENSIONS):
            raise ApiError(
                "unsupported_extension",
                detail={"accepted": list(settings.SUPPORTED_EXTENSIONS)},
            )
        try:
            capture_date = datetime.date.fromisoformat(capture_date or "")
        except ValueError:
            raise ApiError("invalid_capture_date") from None

        session = UploadSession.objects.create(
            project=project,
            declared_filename=filename,
            declared_size_bytes=size,
            capture_date=capture_date,
            survey_name=(request.data.get("name") or filename)[:120],
            created_by=request.user,
        )
        return Response(
            {
                "upload_session_id": str(session.id),
                "tus_endpoint": settings.TUS_PUBLIC_URL,
                "tus_metadata": {
                    "upload_session_id": str(session.id),
                    "filename": filename,
                },
            },
            status=201,
        )

    def get(self, request, project_id):
        project = get_object_or_404(Project, id=project_id)
        sessions = project.upload_sessions.filter(state=UploadSession.State.ACTIVE).order_by(
            "-created_at"
        )
        data = []
        for session in sessions:
            item = UploadSessionSerializer(session).data
            item["received_bytes"] = (
                _tus_offset(session.tus_upload_id) if session.tus_upload_id else None
            )
            item["upload_session_id"] = item.pop("id")
            data.append(item)
        return Response(data)
