"""Cria a linha default das configurações do site (singleton pk=1)."""
from django.db import migrations


def seed_site_settings(apps, schema_editor):
    SiteSettings = apps.get_model("core", "SiteSettings")
    SiteSettings.objects.get_or_create(
        pk=1,
        defaults={
            "store_enabled": True,
            "services_enabled": True,
            "affiliates_enabled": True,
        },
    )


def unseed_site_settings(apps, schema_editor):
    SiteSettings = apps.get_model("core", "SiteSettings")
    SiteSettings.objects.filter(pk=1).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_site_settings, unseed_site_settings),
    ]