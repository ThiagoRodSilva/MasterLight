"""Settings base de produção (comum a Vercel, VPS, etc.).

Herda de base.py e adiciona hardening de segurança, logging, email SMTP,
static files via whitenoise. Ambientes específicos (vercel.py) herdam deste.
"""

import os

from .base import *  # noqa: F401,F403

DEBUG = False  # noqa: F811

# Domínios permitidos — defina via DJANGO_ALLOWED_HOSTS no .env
ALLOWED_HOSTS = env.list(  # noqa: F405
    "DJANGO_ALLOWED_HOSTS",
    default=["masterlightoficial.com.br", "www.masterlightoficial.com.br"],
)
CSRF_TRUSTED_ORIGINS = [f"https://{host}" for host in ALLOWED_HOSTS if host != "*"]

# Sentry / logs
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}

# TLS / Segurança
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000  # 1 ano
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Email SMTP
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("DJANGO_EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("DJANGO_EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("DJANGO_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("DJANGO_EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = os.getenv("DJANGO_DEFAULT_FROM_EMAIL", "no-reply@dominio.com")

# Static files via whitenoise (collectstatic obrigatório)
STORAGES["staticfiles"] = {  # noqa: F405 (definido em .base)
    "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
}

# Media é só links URLField (sem uploads); não servir do filesystem
SERVE_MEDIA = False  # noqa: F405
