"""002 US4 (FR-010): promote each pre-existing project's creator to owner.

``granted_by=NULL`` denotes "granted by the system". Idempotent via
get_or_create; projects that already have a membership for their creator are
left untouched. No reverse data migration: dropping the membership table
restores the pre-feature world (data-model.md migration plan).
"""

from django.db import migrations


def backfill(apps, schema_editor):
    Project = apps.get_model("projects", "Project")
    ProjectMembership = apps.get_model("projects", "ProjectMembership")
    for project in Project.objects.select_related("created_by").iterator():
        ProjectMembership.objects.get_or_create(
            project=project,
            user=project.created_by,
            defaults={"role": "owner", "granted_by": None},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0002_projectmembership"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
