"""Settings de producao para Vercel (serverless).

Herda de prod.py (Secure, HSTS, email SMTP, LOGGING) e sobrescreve o que e
especifico da Vercel:
  - Banco: Postgres serverless via DATABASE_URL (Vercel Postgres/Neon).
  - Static: coletado no build e servido pelo CDN da Vercel.
"""

from .base import env
from .prod import *  # noqa: F401,F403

DEBUG = False  # noqa: F811

# Dominio publico + previews *.vercel.app.
ALLOWED_HOSTS = env.list(  # noqa: F405
    "DJANGO_ALLOWED_HOSTS",
    default=[
        "masterlightoficial.com.br",
        "www.masterlightoficial.com.br",
        ".vercel.app",
    ],
)
CSRF_TRUSTED_ORIGINS = [  # noqa: F405
    "https://masterlightoficial.com.br",
    "https://www.masterlightoficial.com.br",
    "https://*.vercel.app",
]

# Vercel termina TLS no edge e repassa o esquema via X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Static fica no CDN (collectstatic automatico da Vercel).
STORAGES = {  # noqa: F405
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Filesystem efemero na Vercel: nada de media gravada em disco.
SERVE_MEDIA = False  # noqa: F405

# Token do Vercel Cron (Autorizacao de /pagamentos/reconciliar).
CRON_SECRET = env("CRON_SECRET", default="")
