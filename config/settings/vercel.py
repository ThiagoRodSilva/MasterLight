"""Settings de producao para Vercel (serverless).

Herda de prod.py (Secure, HSTS, email SMTP, LOGGING) e sobrescreve o que e
especifico da Vercel:
  - Banco: Postgres serverless via DATABASE_URL (Vercel Postgres/Neon).
  - Media: Cloudflare R2 (S3-compatible) via django-storages; sem filesystem.
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

# Storage de uploads: Cloudflare R2 (bucket publico).
AWS_ACCESS_KEY_ID = env("R2_ACCESS_KEY_ID", default="")
AWS_SECRET_ACCESS_KEY = env("R2_SECRET_ACCESS_KEY", default="")
AWS_STORAGE_BUCKET_NAME = env("R2_BUCKET_NAME", default="")
AWS_S3_ENDPOINT_URL = env("R2_ENDPOINT_URL", default="")
AWS_S3_REGION_NAME = env("R2_REGION_NAME", default="auto")
AWS_S3_CUSTOM_DOMAIN = env("R2_PUBLIC_DOMAIN", default="")
AWS_QUERYSTRING_AUTH = False
AWS_DEFAULT_ACL = "public-read"
AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}

STORAGES = {  # noqa: F405
    "default": {"BACKEND": "storages.backends.s3.S3Boto3Storage"},
    # Static fica no CDN (collectstatic automatico da Vercel).
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

MEDIA_URL = (  # noqa: F405
    f"https://{AWS_S3_CUSTOM_DOMAIN}/"
    if AWS_S3_CUSTOM_DOMAIN
    else f"{AWS_S3_ENDPOINT_URL}/{AWS_STORAGE_BUCKET_NAME}/"
)

# Filesystem efemero na Vercel: nunca servir media via Django.
SERVE_MEDIA = False  # noqa: F405

# Token do Vercel Cron (Autorizacao de /pagamentos/reconciliar).
CRON_SECRET = env("CRON_SECRET", default="")
