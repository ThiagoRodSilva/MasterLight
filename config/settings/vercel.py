"""Settings de producao para Vercel (serverless).

Herda de production.py (Secure, HSTS, email SMTP, LOGGING, static) e
sobrescreve o que e especifico da Vercel:
  - Banco: Postgres serverless via DATABASE_URL (Vercel Postgres/Neon).
  - Static: coletado no build e servido pelo CDN da Vercel.
  - Dominios: adiciona *.vercel.app
  - CRON_SECRET para /pagamentos/reconciliar
"""

from .base import env
from .production import *  # noqa: F401,F403

DEBUG = False  # noqa: F811

# Dominio publico + previews *.vercel.app.
# Garante que .vercel.app SEMPRE esteja presente (previews dinâmicos da Vercel),
# independentemente do valor de DJANGO_ALLOWED_HOSTS.
_raw_hosts = env.list("DJANGO_ALLOWED_HOSTS", default=[])
ALLOWED_HOSTS = list(dict.fromkeys(_raw_hosts + [
    "masterlightoficial.com.br",
    "www.masterlightoficial.com.br",
    ".vercel.app",
]))
CSRF_TRUSTED_ORIGINS = [
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
