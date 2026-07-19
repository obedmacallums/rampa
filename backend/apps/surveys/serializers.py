from rest_framework import serializers

from .models import ProcessingRun, Survey, UploadSession


class RunStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcessingRun
        fields = [
            "id",
            "number",
            "stage",
            "state",
            "failure_code",
            "failure_message_key",
            "started_at",
            "finished_at",
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
