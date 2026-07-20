# T033: promote DerivedArtifact.option_id to NOT NULL — safe because 0004
# backfilled every existing row (FR-012/FR-005).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('surveys', '0004_backfill_options'),
    ]

    operations = [
        migrations.AlterField(
            model_name='derivedartifact',
            name='option_id',
            field=models.CharField(max_length=64),
        ),
    ]
