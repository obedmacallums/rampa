"""Celery orchestration of the ingest pipeline (R3/R8).

Chain: relocate_source → run_validation → run_reprojection → one run_option
task per selected option (topo order) → finalize_run. Prep failures abort the
chain via `_AbortChain` (nothing can proceed); option failures never abort
it — each run_option marks its own RunOption row and cascades a `skipped`
state to its dependents, so independent options keep publishing their own
artifacts (per-option publication, FR-009). Retry/reprocessing creates a new
run whose already-completed options are recorded as `reused` and never
re-executed (FR-004/R5).
"""

import logging
import shutil
from pathlib import Path

from celery import chain, shared_task
from django.utils import timezone

from pipeline import options as registry
from pipeline import storage
from pipeline.errors import StageError
from pipeline.stages.context import RunContext
from pipeline.stages.reproject import reproject
from pipeline.stages.validate import validate_file

from .models import DerivedArtifact, ProcessingRun, RunOption, Survey

logger = logging.getLogger(__name__)

REPROJECTED_NAME = "intermediate/reprojected.copc-input.laz"


def _resolve_reused_from(survey: Survey, option_id: str) -> ProcessingRun | None:
    """Latest run whose RunOption(option_id) is completed; `reused` rows were
    already resolved transitively when they were created (R5), so this never
    needs to chain through more than one hop."""
    for run in survey.runs.order_by("-number").prefetch_related("options"):
        for run_opt in run.options.all():
            if run_opt.option_id != option_id:
                continue
            if run_opt.state == RunOption.State.COMPLETED:
                return run
            if run_opt.state == RunOption.State.REUSED:
                return run_opt.reused_from
    return None


def enqueue_run(survey: Survey, selection: list[str] | None = None) -> ProcessingRun:
    """Append a new run.

    - `selection=None` (retry): the previous run's exact option set is
      reused verbatim — even an option the registry has since deactivated
      stays retriable, since deactivation only blocks *new* selections
      (FR-008).
    - `selection` given but the survey has a previous run (US3 "process more
      options"): only the ids not already part of the previous run's
      selection are validated + closed against the live, active registry;
      the previous run's full set is carried forward untouched and unioned
      in. This is what lets a request for one more option leave everything
      already selected exactly as it was, deactivated or not.
    - `selection` given and there is no previous run (first run of a
      survey): validated + closed against the live registry as usual.

    Either way, options already completed in an earlier run are recorded as
    `reused` and skipped from the chain entirely (R5)."""
    input_type = survey.input_type
    last = survey.runs.order_by("-number").first()
    previous_ids = set(last.options.values_list("option_id", flat=True)) if last else set()

    if selection is not None:
        new_ids = [option_id for option_id in selection if option_id not in previous_ids]
        new_closure = set(registry.effective_selection(input_type, new_ids)) if new_ids else set()
        effective = registry.topo_order(previous_ids | new_closure)
    elif previous_ids:
        effective = registry.topo_order(previous_ids)
    else:
        effective = registry.effective_selection(
            input_type, [o.id for o in registry.options_for(input_type) if o.default_selected]
        )
    run = ProcessingRun.objects.create(
        survey=survey,
        number=(last.number + 1) if last else 1,
        input_type=input_type,
    )

    # Mandatory prep chain (per input type — the only one today is
    # point_cloud; a second input type would branch here).
    sigs = [
        relocate_source.si(str(run.id)),
        run_validation.si(str(run.id)),
        run_reprojection.si(str(run.id)),
    ]
    for option_id in registry.topo_order(effective):
        reused_from = _resolve_reused_from(survey, option_id)
        if reused_from is not None:
            RunOption.objects.create(
                run=run,
                option_id=option_id,
                state=RunOption.State.REUSED,
                reused_from=reused_from,
            )
        else:
            RunOption.objects.create(run=run, option_id=option_id, state=RunOption.State.PENDING)
            sigs.append(run_option.si(str(run.id), option_id))
    sigs.append(finalize_run.si(str(run.id)))

    survey.status = Survey.Status.QUEUED
    survey.save(update_fields=["status"])
    chain(*sigs).apply_async()
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


def _input_laz_path(run: ProcessingRun) -> Path:
    workdir = _workdir(run)
    local = workdir / "reprojected.laz"
    if not local.exists():
        survey = run.survey
        key = storage.run_key(survey.project_id, survey.id, run.id, REPROJECTED_NAME)
        storage.download_to(key, local)
    return local


def _local_artifact_path(run: ProcessingRun, option_id: str, workdir: Path) -> Path:
    """Local copy of an option's published artifact — from this run, or, if
    this run's RunOption is `reused`, from the run it was reused from — for a
    downstream option that declares it as a prerequisite (R4)."""
    run_opt = run.options.get(option_id=option_id)
    source_run = run_opt.reused_from if run_opt.state == RunOption.State.REUSED else run
    artifact = source_run.artifacts.get(option_id=option_id)
    local = workdir / Path(artifact.storage_key).name
    if not local.exists():
        storage.download_to(artifact.storage_key, local)
    return local


def _fail_option(
    run: ProcessingRun, run_opt: RunOption, code: str, message_key: str | None = None
) -> None:
    run_opt.state = RunOption.State.FAILED
    run_opt.failure_code = code
    run_opt.failure_message_key = message_key or f"errors.{code}"
    run_opt.finished_at = timezone.now()
    run_opt.save(update_fields=["state", "failure_code", "failure_message_key", "finished_at"])
    logger.warning("run=%s option=%s failed code=%s", run.id, run_opt.option_id, code)
    _skip_dependents(run, run_opt.option_id)


def _skip_dependents(run: ProcessingRun, blocked_option_id: str) -> None:
    """Mark every option still pending in this run that (transitively)
    depends on `blocked_option_id` as skipped, so the chain's remaining
    run_option tasks no-op instead of running (R3)."""
    all_options = {o.option_id: o for o in run.options.all()}
    blocked = {blocked_option_id}
    changed = True
    while changed:
        changed = False
        for option_id, run_opt in all_options.items():
            if run_opt.state != RunOption.State.PENDING:
                continue
            spec = registry.get_option(option_id)
            if spec and set(spec.prerequisites) & blocked:
                run_opt.state = RunOption.State.SKIPPED
                run_opt.save(update_fields=["state"])
                blocked.add(option_id)
                changed = True


@shared_task(name="apps.surveys.tasks.run_option")
def run_option(run_id: str, option_id: str):
    from django.conf import settings

    run = ProcessingRun.objects.select_related("survey", "survey__project").get(id=run_id)
    survey = run.survey
    run_opt = run.options.get(option_id=option_id)
    if run_opt.state != RunOption.State.PENDING:
        # Already skipped (a prerequisite failed) or fulfilled as a sibling of
        # a producer call that covers several options (FR-015).
        return

    if run.stage != ProcessingRun.Stage.SURFACE_GENERATION:
        run.stage = ProcessingRun.Stage.SURFACE_GENERATION
        run.save(update_fields=["stage"])
    if survey.status != Survey.Status.PROCESSING:
        survey.status = Survey.Status.PROCESSING
        survey.save(update_fields=["status"])

    run_opt.state = RunOption.State.RUNNING
    run_opt.started_at = timezone.now()
    run_opt.save(update_fields=["state", "started_at"])

    spec = registry.get_option(option_id)
    workdir = _workdir(run)
    try:
        prereq_paths = {
            p: _local_artifact_path(run, p, workdir / "inputs") for p in spec.prerequisites
        }
        ctx = RunContext(
            workdir=workdir / "out" / option_id,
            input_laz=_input_laz_path(run),
            resolution_m=settings.DEM_RESOLUTION_M,
            artifacts=prereq_paths,
        )
        produced = spec.producer(ctx)
    except StageError as exc:
        _fail_option(run, run_opt, exc.code, exc.message_key)
        return
    except Exception:
        _fail_option(run, run_opt, "internal_error")
        return

    # Publish only fully materialized, checksummed outputs — all or nothing
    # per option (FR-009). A single producer call may fulfill more than one
    # selected option (FR-015); publish every one it touches that isn't
    # already terminal — the primary option_id is `running` (set above), a
    # sibling fulfilled by the same producer call is still `pending`.
    all_options = {o.option_id: o for o in run.options.all()}
    for produced_id, artifact in produced.items():
        sibling = all_options.get(produced_id)
        if sibling is None or sibling.state not in (
            RunOption.State.PENDING,
            RunOption.State.RUNNING,
        ):
            continue
        key = storage.run_key(survey.project_id, survey.id, run.id, artifact.path.name)
        storage.assert_key_within_survey(key, survey.project_id, survey.id)
        storage.upload_file(artifact.path, key)
        DerivedArtifact.objects.create(
            run=run,
            option_id=produced_id,
            kind=artifact.kind,
            storage_key=key,
            size_bytes=artifact.size_bytes,
            sha256=artifact.sha256,
            resolution_m=artifact.resolution_m,
        )
        sibling.state = RunOption.State.COMPLETED
        sibling.finished_at = timezone.now()
        sibling.save(update_fields=["state", "finished_at"])
        logger.info("run=%s option=%s completed", run.id, produced_id)


@shared_task(name="apps.surveys.tasks.finalize_run")
def finalize_run(run_id: str):
    run = ProcessingRun.objects.select_related("survey").get(id=run_id)
    survey = run.survey
    states = set(run.options.values_list("state", flat=True))
    ok = states <= {RunOption.State.COMPLETED, RunOption.State.REUSED}

    run.state = ProcessingRun.State.COMPLETED if ok else ProcessingRun.State.FAILED
    run.finished_at = timezone.now()
    update_fields = ["state", "finished_at"]
    if not ok and run.failure_code is None:
        failed = run.options.filter(state=RunOption.State.FAILED).first()
        if failed:
            run.failure_code = failed.failure_code
            run.failure_message_key = failed.failure_message_key
            update_fields += ["failure_code", "failure_message_key"]
    run.save(update_fields=update_fields)

    survey.status = Survey.Status.COMPLETED if ok else Survey.Status.FAILED
    survey.save(update_fields=["status"])
    shutil.rmtree(_workdir(run), ignore_errors=True)
    logger.info("run=%s survey=%s finalized ok=%s", run.id, survey.id, ok)
