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
