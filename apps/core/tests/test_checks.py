"""Testes do system check core.E001 (SECRET_KEY insegura)."""

from django.core.checks import run_checks
from django.test import TestCase, override_settings


class TestSecretKeyCheck(TestCase):
    def test_weak_secret_key_returns_error_when_debug_false(self):
        """DEBUG=False + SECRET_KEY fraca -> erro core.E001."""
        with override_settings(DEBUG=False, SECRET_KEY="dev-insecure-change-me"):
            errors = run_checks()
            core_errors = [e for e in errors if e.id == "core.E001"]
            self.assertEqual(len(core_errors), 1)
            self.assertIn("SECRET_KEY insegura", core_errors[0].msg)

    def test_weak_secret_key_change_me_in_production_returns_error(self):
        """DEBUG=False + SECRET_KEY='change-me-in-production' -> erro core.E001."""
        with override_settings(DEBUG=False, SECRET_KEY="change-me-in-production"):
            errors = run_checks()
            core_errors = [e for e in errors if e.id == "core.E001"]
            self.assertEqual(len(core_errors), 1)

    def test_empty_secret_key_returns_error_when_debug_false(self):
        """DEBUG=False + SECRET_KEY='' -> erro core.E001."""
        with override_settings(DEBUG=False, SECRET_KEY=""):
            errors = run_checks()
            core_errors = [e for e in errors if e.id == "core.E001"]
            self.assertEqual(len(core_errors), 1)

    def test_strong_secret_key_no_error_when_debug_false(self):
        """DEBUG=False + SECRET_KEY forte -> sem erros core.E001."""
        with override_settings(
            DEBUG=False, SECRET_KEY="django-insecure-abcdefghijklmnopqrstuvwxyz1234567890"
        ):
            errors = run_checks()
            core_errors = [e for e in errors if e.id == "core.E001"]
            self.assertEqual(len(core_errors), 0)

    def test_weak_secret_key_no_error_when_debug_true(self):
        """DEBUG=True + SECRET_KEY fraca -> sem erros (dev allowed)."""
        with override_settings(DEBUG=True, SECRET_KEY="dev-insecure-change-me"):
            errors = run_checks()
            core_errors = [e for e in errors if e.id == "core.E001"]
            self.assertEqual(len(core_errors), 0)
