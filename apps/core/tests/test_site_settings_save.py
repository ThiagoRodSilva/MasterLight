"""Testes do SiteSettings.save() respeitando update_fields (evita clobber)."""

from django.test import TestCase

from apps.core.models import SiteSettings


class TestSiteSettingsSaveUpdateFields(TestCase):
    def test_update_fields_respected_no_clobber(self):
        """Instância stale não sobrescreve campos não incluídos em update_fields."""
        # Cria configuração inicial com tudo True
        obj = SiteSettings.load()
        obj.services_enabled = True
        obj.affiliates_enabled = True
        obj.maintenance_enabled = True
        obj.provider_registration_enabled = True
        obj.save()

        # Simula instância A (stale) que só quer desligar services_enabled
        stale_a = SiteSettings.load()
        stale_a.services_enabled = False
        stale_a.save(update_fields=["services_enabled"])

        # Verifica que services_enabled foi desligado
        reloaded = SiteSettings.load()
        self.assertFalse(reloaded.services_enabled)
        self.assertTrue(reloaded.affiliates_enabled)
        self.assertTrue(reloaded.maintenance_enabled)
        self.assertTrue(reloaded.provider_registration_enabled)

        # Simula instância B (stale, ainda tem services_enabled=True em memória)
        # que só quer desligar affiliates_enabled
        stale_b = SiteSettings.load()  # carrega do banco (services_enabled=False)
        # Mas vamos simular o bug: instância B não recarregou services_enabled
        # (em memória ainda está True do estado anterior)
        stale_b.affiliates_enabled = False
        stale_b.services_enabled = True  # valor stale em memória!
        stale_b.save(update_fields=["affiliates_enabled"])

        # Verifica que services_enabled PERMANECE False (não foi clobberado de volta para True)
        reloaded = SiteSettings.load()
        self.assertFalse(reloaded.affiliates_enabled)
        self.assertFalse(
            reloaded.services_enabled, "services_enabled foi clobberado de volta para True!"
        )

    def test_update_fields_none_updates_all_flags(self):
        """update_fields=None atualiza todas as flags."""
        obj = SiteSettings.load()
        obj.services_enabled = False
        obj.affiliates_enabled = False
        obj.maintenance_enabled = False
        obj.provider_registration_enabled = False
        obj.save()  # sem update_fields

        reloaded = SiteSettings.load()
        self.assertFalse(reloaded.services_enabled)
        self.assertFalse(reloaded.affiliates_enabled)
        self.assertFalse(reloaded.maintenance_enabled)
        self.assertFalse(reloaded.provider_registration_enabled)

    def test_updated_at_updated_on_partial_save(self):
        """updated_at é atualizado mesmo com update_fields parcial."""
        obj = SiteSettings.load()
        old_updated = obj.updated_at
        obj.services_enabled = False
        obj.save(update_fields=["services_enabled"])
        reloaded = SiteSettings.load()
        self.assertGreater(reloaded.updated_at, old_updated)
