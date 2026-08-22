# Generated migration for CustomUser BaseModel fields (dual PK approach)

import uuid
from django.db import migrations, models
from django.utils import timezone


def backfill_uuids(apps, schema_editor):
    """Backfill UUIDs for existing users."""
    CustomUser = apps.get_model("accounts", "CustomUser")
    for user in CustomUser.objects.filter(uuid__isnull=True):
        user.uuid = uuid.uuid4()
        user.save(update_fields=["uuid"])


def backfill_timestamps(apps, schema_editor):
    """Backfill created_at/updated_at for existing users."""
    CustomUser = apps.get_model("accounts", "CustomUser")
    now = timezone.now()
    CustomUser.objects.filter(created_at__isnull=True).update(
        created_at=now,
        updated_at=now,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_remove_bio_fields"),
    ]

    operations = [
        # Add uuid field nullable, without unique constraint initially
        migrations.AddField(
            model_name="customuser",
            name="uuid",
            field=models.UUIDField(
                db_index=True,
                editable=False,
                null=True,
            ),
        ),
        # Add created_at nullable
        migrations.AddField(
            model_name="customuser",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True,
                null=True,
            ),
        ),
        # Add updated_at nullable
        migrations.AddField(
            model_name="customuser",
            name="updated_at",
            field=models.DateTimeField(
                auto_now=True,
                null=True,
            ),
        ),
        # Add is_active with default True
        migrations.AddField(
            model_name="customuser",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        # Backfill UUIDs for existing rows
        migrations.RunPython(backfill_uuids, migrations.RunPython.noop),
        # Backfill timestamps for existing rows
        migrations.RunPython(backfill_timestamps, migrations.RunPython.noop),
        # Now make uuid non-null with unique constraint
        migrations.AlterField(
            model_name="customuser",
            name="uuid",
            field=models.UUIDField(
                default=uuid.uuid4,
                unique=True,
                db_index=True,
                editable=False,
            ),
        ),
        # Make timestamps non-null
        migrations.AlterField(
            model_name="customuser",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AlterField(
            model_name="customuser",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
    ]