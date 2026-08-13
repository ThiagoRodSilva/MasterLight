"""Valida que config.settings.vercel e coerente com o deploy serverless."""

import importlib
import os
from unittest import mock

from django.test import SimpleTestCase


class VercelSettingsTests(SimpleTestCase):
    VERIFY = {
        "DJANGO_DEBUG": "False",
        "DJANGO_SECRET_KEY": "test-secret",
        "DJANGO_ALLOWED_HOSTS": "masterlightoficial.com.br,www.masterlightoficial.com.br,.vercel.app",
        "R2_ACCESS_KEY_ID": "test-id",
        "R2_SECRET_ACCESS_KEY": "test-secret-key",
        "R2_BUCKET_NAME": "test-bucket",
        "R2_ENDPOINT_URL": "https://acct.r2.cloudflarestorage.com",
        "R2_PUBLIC_DOMAIN": "media.example.com",
    }

    def _settings(self):
        with mock.patch.dict(os.environ, self.VERIFY, clear=False):
            return importlib.import_module("config.settings.vercel")

    def test_debug_desligado(self):
        self.assertFalse(self._settings().DEBUG)

    def test_media_nao_servido_pelo_django(self):
        self.assertFalse(self._settings().SERVE_MEDIA)

    def test_storage_default_usa_r2(self):
        self.assertEqual(
            self._settings().STORAGES["default"]["BACKEND"],
            "storages.backends.s3.S3Boto3Storage",
        )

    def test_static_permanece_no_cdn(self):
        self.assertEqual(
            self._settings().STORAGES["staticfiles"]["BACKEND"],
            "whitenoise.storage.CompressedManifestStaticFilesStorage",
        )

    def test_allowed_hosts_inclui_vercel_app(self):
        self.assertIn(".vercel.app", self._settings().ALLOWED_HOSTS)

    def test_media_url_usa_dominio_publico(self):
        self.assertEqual(self._settings().MEDIA_URL, "https://media.example.com/")

    def test_proxy_ssl_header_configurado(self):
        self.assertEqual(
            self._settings().SECURE_PROXY_SSL_HEADER, ("HTTP_X_FORWARDED_PROTO", "https")
        )
