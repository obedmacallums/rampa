import datetime

from django.conf import settings
from rest_framework import serializers

from .models import ProcessingRun, RunOption, Survey, UploadSession


class RunOptionSerializer(serializers.ModelSerializer):
    reused_from_run_id = serializers.UUIDField(source="reused_from_id", read_only=True)

    class Meta:
        model = RunOption
        fields = [
            "option_id",
            "state",
            "failure_code",
            "failure_message_key",
            "started_at",
            "finished_at",
            "reused_from_run_id",
        ]


class RunStatusSerializer(serializers.ModelSerializer):
    options = RunOptionSerializer(many=True, read_only=True)

    class Meta:
        model = ProcessingRun
        fields = [
            "id",
            "number",
            "stage",
            "state",
            "input_type",
            "failure_code",
            "failure_message_key",
            "started_at",
            "finished_at",
            "options",
        ]


class SurveySummarySerializer(serializers.ModelSerializer):
    current_stage = serializers.SerializerMethodField()

    class Meta:
        model = Survey
        fields = [
            "id",
            "name",
            "capture_date",
            "source_format",
            "source_size_bytes",
            "status",
            "current_stage",
            "input_type",
        ]

    def get_current_stage(self, obj):
        run = obj.runs.order_by("-number").first()
        return run.stage if run else None


class SurveyDetailSerializer(SurveySummarySerializer):
    runs = RunStatusSerializer(many=True, read_only=True)
    latest_run = serializers.SerializerMethodField()

    class Meta(SurveySummarySerializer.Meta):
        fields = SurveySummarySerializer.Meta.fields + ["runs", "latest_run"]

    def get_latest_run(self, obj):
        run = obj.runs.order_by("-number").first()
        return RunStatusSerializer(run).data if run else None


class DeletedSurveySerializer(serializers.ModelSerializer):
    """GET /deleted entry (005 US3) for an independently-deleted survey."""

    project = serializers.SerializerMethodField()
    purge_at = serializers.SerializerMethodField()

    class Meta:
        model = Survey
        fields = ["id", "name", "capture_date", "project", "deleted_at", "purge_at"]

    def get_project(self, obj):
        return {"id": str(obj.project_id), "name": obj.project.name}

    def get_purge_at(self, obj):
        return obj.deleted_at + datetime.timedelta(days=settings.DELETE_RECOVERY_DAYS)


class UploadSessionSerializer(serializers.ModelSerializer):
    received_bytes = serializers.IntegerField(read_only=True, default=None, allow_null=True)

    class Meta:
        model = UploadSession
        fields = [
            "id",
            "declared_filename",
            "state",
            "received_bytes",
            "declared_size_bytes",
        ]
