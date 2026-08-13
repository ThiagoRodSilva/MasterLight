"""Settings de produção (Hostinger)."""

import os

from .base import *  # noqa: F401,F403

DEBUG = False  # noqa: F811

# Domínios de produção (sobrescrevem o default de base.py). Defina via
# DJANGO_ALLOWED_HOSTS no .env da Hostinger quando necessário.
ALLOWED_HOSTS = env.list(  # noqa: F405 (definido em .base)
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

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
# HSTS: apenas depois de validar que HTTPS está 100% no domínio (www + apex).
# Preload (SECURE_HSTS_PRELOAD=True) tem efeito permanente e pode ser adicionado
# depois de testes; recomendado para este domínio quando estiver estável.
SECURE_HSTS_SECONDS = 31536000  # 1 ano
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("DJANGO_EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("DJANGO_EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("DJANGO_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("DJANGO_EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = os.getenv("DJANGO_DEFAULT_FROM_EMAIL", "no-reply@dominio.com")

# Hostinger roda via Passenger; collectstatic obrigatório.
STORAGES["staticfiles"] = {  # noqa: F405 (definido em .base)
    "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
}
