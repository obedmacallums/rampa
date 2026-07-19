from rest_framework import serializers

from .models import CrsCatalogEntry, Project, ProjectMembership


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


class ProjectMembershipSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    granted_by = serializers.SerializerMethodField()

    class Meta:
        model = ProjectMembership
        fields = ["username", "role", "granted_by", "granted_at"]

    def get_granted_by(self, obj):
        # NULL = granted by the system (002 backfill); the UI renders "system".
        return obj.granted_by.username if obj.granted_by else None
