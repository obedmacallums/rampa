"""Survey ingest entities. See specs/001-survey-ingest/data-model.md.

Immutability is structural: DerivedArtifact rows are written only for fully
materialized, checksummed outputs, and every run writes exclusively inside its
own object-storage prefix.
"""

import uuid

from django.conf import settings
from django.db import models


class UploadSession(models.Model):
    class State(models.TextChoices):
        ACTIVE = "active"
        COMPLETED = "completed"
        EXPIRED = "expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # tusd S3-store IDs embed the base64 multipart upload id and easily exceed
    # 128 chars
    tus_upload_id = models.CharField(max_length=512, unique=True, null=True, blank=True)
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="upload_sessions"
    )
    declared_filename = models.CharField(max_length=255)
    declared_size_bytes = models.BigIntegerField()
    capture_date = models.DateField()
    survey_name = models.CharField(max_length=120)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    state = models.CharField(max_length=16, choices=State.choices, default=State.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    # Effective selection (server-completed closure incl. required), always
    # computed from the registry by the initiation view — never defaulted
    # here, so this schema carries no catalog knowledge (data-model.md).
    selected_options = models.JSONField(default=list, blank=True)


class Survey(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued"
        PROCESSING = "processing"
        COMPLETED = "completed"
        FAILED = "failed"

    class SourceFormat(models.TextChoices):
        LAS = "las"
        LAZ = "laz"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="surveys"
    )
    name = models.CharField(max_length=120)
    capture_date = models.DateField()
    source_format = models.CharField(
        max_length=8, choices=SourceFormat.choices, null=True, blank=True
    )
    source_size_bytes = models.BigIntegerField()
    source_key = models.CharField(max_length=512)
    source_sha256 = models.CharField(max_length=64, null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    # Registry input-type id (FR-013); `point_cloud` is the only entry today.
    input_type = models.CharField(max_length=32, default="point_cloud")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    # Soft delete (005): same semantics as Project.deleted_at/deleted_by.
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    # True only while cascade-deleted alongside its project (R2); always
    # False for an independent survey deletion. Governs whether a
    # project-level delete/restore touches this survey.
    deleted_via_project_cascade = models.BooleanField(default=False)

    class Meta:
        ordering = ["capture_date", "created_at"]


class ProcessingRun(models.Model):
    class Stage(models.TextChoices):
        VALIDATION = "validation"
        REPROJECTION = "reprojection"
        SURFACE_GENERATION = "surface_generation"

    class State(models.TextChoices):
        QUEUED = "queued"
        RUNNING = "running"
        COMPLETED = "completed"
        FAILED = "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="runs")
    number = models.PositiveIntegerField()
    stage = models.CharField(max_length=32, choices=Stage.choices, default=Stage.VALIDATION)
    state = models.CharField(max_length=16, choices=State.choices, default=State.QUEUED)
    # Copied from the survey at enqueue time (FR-013).
    input_type = models.CharField(max_length=32, default="point_cloud")
    failure_code = models.CharField(max_length=64, null=True, blank=True)
    failure_message_key = models.CharField(max_length=100, null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["survey", "number"], name="run_number_unique")
        ]
        ordering = ["number"]


class RunOption(models.Model):
    """One row per option in a run's effective selection: unit of selection
    persistence, progress, publication and failure attribution (FR-004/FR-009/
    FR-010, data-model.md)."""

    class State(models.TextChoices):
        PENDING = "pending"
        RUNNING = "running"
        COMPLETED = "completed"
        FAILED = "failed"
        SKIPPED = "skipped"
        REUSED = "reused"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(ProcessingRun, on_delete=models.CASCADE, related_name="options")
    option_id = models.CharField(max_length=64)
    state = models.CharField(max_length=16, choices=State.choices, default=State.PENDING)
    # Producing run when state=reused; already resolved transitively at
    # creation time, so it never points at another `reused` row (R5).
    reused_from = models.ForeignKey(
        ProcessingRun, on_delete=models.SET_NULL, null=True, blank=True, related_name="reused_by"
    )
    failure_code = models.CharField(max_length=64, null=True, blank=True)
    failure_message_key = models.CharField(max_length=100, null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["run", "option_id"], name="run_option_unique")
        ]
        ordering = ["option_id"]


class DerivedArtifact(models.Model):
    class Kind(models.TextChoices):
        DEM = "dem"
        HILLSHADE = "hillshade"
        COPC = "copc"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(ProcessingRun, on_delete=models.CASCADE, related_name="artifacts")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    # Registry option id attribution (FR-005); enforced NOT NULL by the
    # database — every row is attributed, backfilled (T007) before this was
    # promoted (T033).
    option_id = models.CharField(max_length=64)
    storage_key = models.CharField(max_length=512)
    size_bytes = models.BigIntegerField()
    sha256 = models.CharField(max_length=64)
    resolution_m = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["run", "kind"], name="artifact_kind_per_run_unique")
        ]
