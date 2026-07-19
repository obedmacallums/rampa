"""tusd HTTP hook receiver.

Performs NO file operations (constitution Principle III): it records metadata,
creates the Survey, and enqueues the async chain — the first pipeline step
relocates the object out of the tusd staging prefix.
"""

import logging

from django.conf import settings
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.errors import ApiError

from .models import Survey, UploadSession
from .tasks import enqueue_run

logger = logging.getLogger(__name__)


class TusdHookView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request):
        if request.headers.get("X-Rampa-Hook-Secret") != settings.TUSD_HOOK_SECRET:
            raise ApiError("forbidden", status_code=403)

        payload = request.data or {}
        hook_type = payload.get("Type") or request.headers.get("Hook-Name", "")
        upload = (payload.get("Event") or {}).get("Upload") or payload.get("Upload") or {}
        metadata = upload.get("MetaData") or {}
        session_id = metadata.get("upload_session_id")
        if not session_id:
            return Response({})  # not one of ours; ignore

        try:
            session = UploadSession.objects.get(id=session_id)
        except (UploadSession.DoesNotExist, ValueError):
            logger.warning("tusd hook for unknown upload session %s", session_id)
            return Response({})

        if hook_type == "post-create":
            session.tus_upload_id = upload.get("ID") or session.tus_upload_id
            session.save(update_fields=["tus_upload_id"])
            return Response({})

        if hook_type != "post-finish" or session.state != UploadSession.State.ACTIVE:
            return Response({})

        storage_info = upload.get("Storage") or {}
        staging_key = storage_info.get("Key")
        if not staging_key:
            logger.error("post-finish without storage key (session %s)", session_id)
            return Response({})

        survey = Survey.objects.create(
            project=session.project,
            name=session.survey_name,
            capture_date=session.capture_date,
            source_size_bytes=upload.get("Size") or session.declared_size_bytes,
            source_key=staging_key,  # canonical source/ key set by async relocation
            created_by=session.created_by,
        )
        session.state = UploadSession.State.COMPLETED
        session.completed_at = timezone.now()
        session.save(update_fields=["state", "completed_at"])

        enqueue_run(survey)
        logger.info("survey %s created from upload session %s", survey.id, session.id)
        return Response({})
