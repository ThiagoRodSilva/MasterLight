"""Settings de teste: SQLite em memória, independentes do banco de dev (Supabase).

Garante suíte rápida/offline mesmo com DATABASE_URL apontando para Postgres.
Uso: DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test apps
"""

from .dev import *  # noqa: F401,F403

DATABASES = {  # noqa: F405
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Suíte hermética: não depende do .env de dev (que pode apontar para o Asaas
# sandbox). Testes que exercitam o Asaas usam `override_settings`/mock.
PAYMENT_PROVIDER = "manual"  # noqa: F405
ASAAS_API_KEY = ""  # noqa: F405
