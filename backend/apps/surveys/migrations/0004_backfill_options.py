"""T007: backfill per-option attribution/history for pre-004 rows (FR-012, R6).

Survey/ProcessingRun.input_type already default to 'point_cloud' via 0003's
AddField. This migration backfills: DerivedArtifact.option_id from kind,
RunOption rows for every existing run's then-standard selection, and
UploadSession.selected_options for historical sessions.
"""

from django.db import migrations

STANDARD_OPTIONS = ["elevation", "hillshade", "point_cloud_3d"]
OPTION_TO_KIND = {"elevation": "dem", "hillshade": "hillshade", "point_cloud_3d": "copc"}
KIND_TO_OPTION = {v: k for k, v in OPTION_TO_KIND.items()}


def backfill(apps, schema_editor):
    DerivedArtifact = apps.get_model("surveys", "DerivedArtifact")
    ProcessingRun = apps.get_model("surveys", "ProcessingRun")
    RunOption = apps.get_model("surveys", "RunOption")
    UploadSession = apps.get_model("surveys", "UploadSession")

    for artifact in DerivedArtifact.objects.filter(option_id__isnull=True):
        option_id = KIND_TO_OPTION.get(artifact.kind)
        if option_id:
            artifact.option_id = option_id
            artifact.save(update_fields=["option_id"])

    for run in ProcessingRun.objects.all():
        existing = set(run.options.values_list("option_id", flat=True))
        missing = [option_id for option_id in STANDARD_OPTIONS if option_id not in existing]
        if not missing:
            continue

        artifact_kinds = set(run.artifacts.values_list("kind", flat=True))
        # A pre-004 run publishes all three artifacts or none (surface
        # generation uploaded atomically) — so at most one of the missing
        # standard options can be the run's actual failure; the rest are its
        # consequence.
        marked_failed = False
        for option_id in missing:
            kind = OPTION_TO_KIND[option_id]
            if kind in artifact_kinds:
                state = "completed"
            elif run.state == "failed":
                state = "failed" if not marked_failed else "skipped"
                marked_failed = True
            elif run.state in ("queued", "running"):
                state = "pending"
            else:
                state = "skipped"
            RunOption.objects.create(
                run=run,
                option_id=option_id,
                state=state,
                failure_code=run.failure_code if state == "failed" else None,
                failure_message_key=run.failure_message_key if state == "failed" else None,
            )

    UploadSession.objects.filter(selected_options=[]).update(selected_options=STANDARD_OPTIONS)


def unbackfill(apps, schema_editor):
    RunOption = apps.get_model("surveys", "RunOption")
    RunOption.objects.all().delete()
    DerivedArtifact = apps.get_model("surveys", "DerivedArtifact")
    DerivedArtifact.objects.update(option_id=None)


class Migration(migrations.Migration):

    dependencies = [
        ("surveys", "0003_derivedartifact_option_id_processingrun_input_type_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill, unbackfill),
    ]
