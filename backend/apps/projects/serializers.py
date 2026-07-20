import datetime

from django.conf import settings
from rest_framework import serializers

from . import access
from .models import CrsCatalogEntry, Project, ProjectMembership


class CrsCatalogSerializer(serializers.ModelSerializer):
    class Meta:
        model = CrsCatalogEntry
        fields = ["id", "code", "label_key"]


class ProjectSummarySerializer(serializers.ModelSerializer):
    crs = serializers.SerializerMethodField()
    survey_count = serializers.IntegerField(read_only=True)
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = ["id", "name", "crs", "survey_count", "created_at", "is_owner"]

    def get_crs(self, obj):
        return {"code": obj.crs.code, "label_key": obj.crs.label_key}

    def get_is_owner(self, obj):
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return False
        return access.is_owner(request.user, obj)


class DeletedProjectSerializer(serializers.ModelSerializer):
    """GET /deleted entry (005 US3): purge_at spares the frontend from
    hardcoding the recovery window."""

    crs = serializers.SerializerMethodField()
    survey_count = serializers.IntegerField(read_only=True)
    purge_at = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = ["id", "name", "crs", "survey_count", "deleted_at", "purge_at"]

    def get_crs(self, obj):
        return {"code": obj.crs.code, "label_key": obj.crs.label_key}

    def get_purge_at(self, obj):
        return obj.deleted_at + datetime.timedelta(days=settings.DELETE_RECOVERY_DAYS)


class ProjectMembershipSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    granted_by = serializers.SerializerMethodField()

    class Meta:
        model = ProjectMembership
        fields = ["username", "role", "granted_by", "granted_at"]

    def get_granted_by(self, obj):
        # NULL = granted by the system (002 backfill); the UI renders "system".
        return obj.granted_by.username if obj.granted_by else None
