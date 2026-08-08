"""Settings de desenvolvimento."""
from .base import *  # noqa: F401,F403

DEBUG = True

INTERNAL_IPS = ["127.0.0.1"]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Django-allauth em dev usa clientes sociais de teste configurados via .env
