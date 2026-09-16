"""Settings de teste: SQLite em arquivo, independentes do banco de dev (Supabase).

Garante suíte rápida/offline mesmo com DATABASE_URL apontando para Postgres.
Uso: DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test apps [--keepdb]
"""

import os

from .base import BASE_DIR  # noqa: F401
from .dev import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Permitir testserver do Django test client
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1", "0.0.0.0"]

# Suíte hermética: usa o Asaas como provider, mas com chave de fixture (não
# dispara o check payments.E001 e não faz chamadas reais — o AsaasApi é mockado
# nos testes). Testes que exercitam o Asaas usam `override_settings`/mock.
PAYMENT_PROVIDER = "asaas"  # noqa: F405
ASAAS_API_KEY = "test-fixture-key"  # noqa: F405

# Desabilita migrações para testes unitários puros (opcional via env)
# DJANGO_TEST_SKIP_MIGRATIONS=1
if os.environ.get("DJANGO_TEST_SKIP_MIGRATIONS") == "1":

    class DisableMigrations:
        def __contains__(self, item):
            return True

        def __getitem__(self, item):
            return None

    MIGRATION_MODULES = DisableMigrations()  # noqa: F405
