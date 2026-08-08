"""Testes das configurações do site (singleton)."""

import pytest

from apps.core.models import SiteSettings

pytestmark = pytest.mark.django_db


class TestSiteSettingsSingleton:
    def test_load_creates_default_row(self):
        obj = SiteSettings.load()
        assert obj.pk == 1
        assert obj.store_enabled is True
        assert obj.services_enabled is True
        assert obj.affiliates_enabled is True

    def test_load_never_duplicates(self):
        SiteSettings.load()
        SiteSettings.load()
        assert SiteSettings.objects.count() == 1

    def test_save_forces_single_pk(self):
        obj = SiteSettings.objects.create(
            store_enabled=False, services_enabled=True, affiliates_enabled=True
        )
        assert obj.pk == 1
        assert SiteSettings.objects.count() == 1

    def test_toggle_persists(self):
        obj = SiteSettings.load()
        obj.store_enabled = False
        obj.save()
        reloaded = SiteSettings.load()
        assert reloaded.store_enabled is False
        assert SiteSettings.objects.count() == 1
