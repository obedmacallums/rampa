from rest_framework import serializers

from .models import CrsCatalogEntry, Project


class CrsCatalogSerializer(serializers.ModelSerializer):
    class Meta:
        model = CrsCatalogEntry
        fields = ["id", "code", "label_key"]


class ProjectSummarySerializer(serializers.ModelSerializer):
    crs = serializers.SerializerMethodField()
    survey_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Project
        fields = ["id", "name", "crs", "survey_count", "created_at"]

    def get_crs(self, obj):
        return {"code": obj.crs.code, "label_key": obj.crs.label_key}
