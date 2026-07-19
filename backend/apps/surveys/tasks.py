"""Celery orchestration of the ingest pipeline (R8).

Chain: relocate_source → run_validation → run_reprojection → run_surfaces.
Each stage re-downloads its input from object storage so the chain is safe
across workers; every stage transition is persisted so progress survives
browser and worker restarts (FR-006/FR-007). Failures map stage errors to
failure codes and never publish partial artifacts (edge case: mid-pipeline
failure).
"""

import logging
import shutil
import uuid
from pathlib import Path

from celery import chain, shared_task
from django.utils import timezone

from pipeline import storage
from pipeline.errors import StageError
from pipeline.stages.reproject import reproject
from pipeline.stages.surfaces import generate_surfaces
from pipeline.stages.validate import validate_file

from .models import DerivedArtifact, ProcessingRun, Survey

logger = logging.getLogger(__name__)

REPROJECTED_NAME = "intermediate/reprojected.copc-input.laz"


def enqueue_run(survey: Survey) -> ProcessingRun:
    last = survey.runs.order_by("-number").first()
    run = ProcessingRun.objects.create(survey=survey, number=(last.number + 1) if last else 1)
    survey.status = Survey.Status.QUEUED
    survey.save(update_fields=["status"])
    chain(
        relocate_source.si(str(run.id)),
        run_validation.si(str(run.id)),
        run_reprojection.si(str(run.id)),
        run_surfaces.si(str(run.id)),
    ).apply_async()
    return run


def _start_stage(run_id: str, stage: str) -> ProcessingRun:
    run = ProcessingRun.objects.select_related("survey", "survey__project").get(id=run_id)
    run.stage = stage
    run.state = ProcessingRun.State.RUNNING
    if run.started_at is None:
        run.started_at = timezone.now()
    run.save(update_fields=["stage", "state", "started_at"])
    survey = run.survey
    if survey.status != Survey.Status.PROCESSING:
        survey.status = Survey.Status.PROCESSING
        survey.save(update_fields=["status"])
    logger.info("run=%s survey=%s stage=%s started", run.id, survey.id, stage)
    return run


def _fail_run(run: ProcessingRun, code: str, message_key: str | None = None) -> None:
    run.state = ProcessingRun.State.FAILED
    run.failure_code = code
    run.failure_message_key = message_key or f"errors.{code}"
    run.finished_at = timezone.now()
    run.save(update_fields=["state", "failure_code", "failure_message_key", "finished_at"])
    run.survey.status = Survey.Status.FAILED
    run.survey.save(update_fields=["status"])
    logger.warning("run=%s survey=%s failed code=%s", run.id, run.survey.id, code)


def _workdir(run: ProcessingRun) -> Path:
    return storage.scratch_dir() / f"run-{run.id}"


class _AbortChain(Exception):
    """Raised after a run is marked failed to stop the remaining chain links."""


def _stage_task(stage_name):
    def decorator(fn):
        def wrapper(run_id: str):
            run = _start_stage(run_id, stage_name)
            try:
                fn(run)
            except StageError as exc:
                _fail_run(run, exc.code, exc.message_key)
                raise _AbortChain from exc
            except Exception as exc:  # crash tolerance: never leave a run running
                _fail_run(run, "internal_error")
                raise _AbortChain from exc

        wrapper.__name__ = fn.__name__
        return wrapper

    return decorator


@shared_task(name="apps.surveys.tasks.relocate_source", throws=(_AbortChain,))
@_stage_task(ProcessingRun.Stage.VALIDATION)
def relocate_source(run):
    """First async step (Principle III): move the upload out of tusd staging."""
    survey = run.survey
    if survey.source_key.startswith("tus-staging/"):
        filename = Path(survey.name).name or "source.laz"
        session = survey.project.upload_sessions.filter(survey_name=survey.name).first()
        if session:
            filename = session.declared_filename
        dest = storage.source_key(survey.project_id, survey.id, filename)
        storage.assert_key_within_survey(dest, survey.project_id, survey.id)
        storage.copy_object(survey.source_key, dest)
        storage.delete_object(survey.source_key)
        survey.source_key = dest
        survey.save(update_fields=["source_key"])
        logger.info("run=%s source relocated to %s", run.id, dest)


@shared_task(name="apps.surveys.tasks.run_validation", throws=(_AbortChain,))
@_stage_task(ProcessingRun.Stage.VALIDATION)
def run_validation(run):
    survey = run.survey
    workdir = _workdir(run)
    local = storage.download_to(survey.source_key, workdir / "source.laz")
    result = validate_file(local)
    survey.source_format = result.source_format
    survey.source_sha256 = result.sha256
    survey.save(update_fields=["source_format", "source_sha256"])


@shared_task(name="apps.surveys.tasks.run_reprojection", throws=(_AbortChain,))
@_stage_task(ProcessingRun.Stage.REPROJECTION)
def run_reprojection(run):
    survey = run.survey
    workdir = _workdir(run)
    local = workdir / "source.laz"
    if not local.exists():
        storage.download_to(survey.source_key, local)
    output = reproject(local, survey.project.crs.code, workdir / "reprojected.laz")
    key = storage.run_key(survey.project_id, survey.id, run.id, REPROJECTED_NAME)
    storage.assert_key_within_survey(key, survey.project_id, survey.id)
    storage.upload_file(output, key)


@shared_task(name="apps.surveys.tasks.run_surfaces", throws=(_AbortChain,))
@_stage_task(ProcessingRun.Stage.SURFACE_GENERATION)
def run_surfaces(run):
    from django.conf import settings

    survey = run.survey
    workdir = _workdir(run)
    reprojected = workdir / "reprojected.laz"
    if not reprojected.exists():
        key = storage.run_key(survey.project_id, survey.id, run.id, REPROJECTED_NAME)
        storage.download_to(key, reprojected)

    artifacts = generate_surfaces(reprojected, workdir / "out", settings.DEM_RESOLUTION_M)

    # Publish only fully materialized, checksummed outputs — all or nothing.
    for artifact in artifacts:
        key = storage.run_key(survey.project_id, survey.id, run.id, artifact.path.name)
        storage.assert_key_within_survey(key, survey.project_id, survey.id)
        storage.upload_file(artifact.path, key)
    for artifact in artifacts:
        DerivedArtifact.objects.create(
            run=run,
            kind=artifact.kind,
            storage_key=storage.run_key(survey.project_id, survey.id, run.id, artifact.path.name),
            size_bytes=artifact.size_bytes,
            sha256=artifact.sha256,
            resolution_m=artifact.resolution_m,
        )

    run.state = ProcessingRun.State.COMPLETED
    run.finished_at = timezone.now()
    run.save(update_fields=["state", "finished_at"])
    survey.status = Survey.Status.COMPLETED
    survey.save(update_fields=["status"])
    shutil.rmtree(workdir, ignore_errors=True)
    logger.info("run=%s survey=%s completed", run.id, survey.id)
