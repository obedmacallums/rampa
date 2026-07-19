"""Generic, domain-neutral entities (constitution Principle X)."""

import uuid

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower


class CrsCatalogEntry(models.Model):
    """Curated working-CRS list (research R6).

    Seeded with WGS84/UTM zones covering Chile. SIRGAS-Chile realizations are
    added once their EPSG codes are verified against the PROJ database shipped
    in the worker image (per T012); codes are never guessed.
    """

    code = models.CharField(max_length=32, unique=True)
    label_key = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.code


class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    crs = models.ForeignKey(CrsCatalogEntry, on_delete=models.PROTECT, related_name="projects")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="projects"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("name"), name="project_name_ci_unique")
        ]

    def __str__(self):
        return self.name


class ProjectMembership(models.Model):
    """User↔project association; the sole source of project visibility (002).

    Authorization derives from these rows, never from ``Project.created_by``
    (which stays as an audit field only). ``granted_by=NULL`` means "granted
    by the system" (the 002 backfill migration).
    """

    class Role(models.TextChoices):
        OWNER = "owner"
        MEMBER = "member"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="project_memberships"
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["project", "user"], name="membership_unique")
        ]
        indexes = [
            models.Index(fields=["user", "project"], name="membership_user_project_idx")
        ]

    def __str__(self):
        return f"{self.user}:{self.project}:{self.role}"
