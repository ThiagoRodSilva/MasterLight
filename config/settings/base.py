"""Settings base compartilhados entre dev e prod."""

from decimal import Decimal
from pathlib import Path

import environ

from .env_helpers import asaas_api_key

# Permite usar PyMySQL como driver MySQL drop-in (instalado sem build tools)
try:
    import pymysql  # noqa: F401

    pymysql.install_as_MySQLdb()
except ImportError:  # pragma: no cover
    pass

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, []),
)
# Valores que comecam com '$' sao tratados como proxy de outra env var; habilitar
# o escape '\$' para permitir chaves como a do Asaas sandbox ('$aact_...').
env.escape_proxy = True
environ.Env.read_env(BASE_DIR / ".env", overwrite=False)

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-insecure-change-me")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env(
    "DJANGO_ALLOWED_HOSTS",
    default=["localhost", "127.0.0.1", "0.0.0.0"],
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    # Third-party
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "crispy_forms",
    "crispy_bootstrap5",
    "widget_tweaks",
    # Local apps
    "apps.core",
    "apps.accounts",
    "apps.portfolio",
    "apps.services",
    "apps.shop",
    "apps.affiliate",
    "apps.checkout",
    "apps.payments",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "apps.affiliate.middleware.AffiliateReferralMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.branding",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": env.db_url(
        "DATABASE_URL",
        default="sqlite:///db.sqlite3",
    )
}

# Supabase (Postgres): em transaction mode do pooler, cursores server-side e
# prepared statements não são suportados — desligamos para o driver psycopg.
if DATABASES["default"]["ENGINE"].endswith("postgresql"):
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True
    # Serverless (Vercel) não mantém conexão ociosa; dev/backend longo pode reusar.
    DATABASES["default"]["CONN_MAX_AGE"] = env.int("DJANGO_CONN_MAX_AGE", default=60)

AUTH_USER_MODEL = "accounts.CustomUser"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = env("DJANGO_LANGUAGE_CODE", default="pt-br")
TIME_ZONE = env("DJANGO_TIME_ZONE", default="America/Sao_Paulo")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if not DEBUG
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
# Hospedagem compartilhada (Hostinger/Passenger) não expõe alias de servidor
# para `media/` fora de public_html; o Django serve os uploads via rota própria.
SERVE_MEDIA = env.bool("DJANGO_SERVE_MEDIA", default=True)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# django-allauth
SITE_ID = 1
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_LOGIN_METHODS = {"email", "username"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
ACCOUNT_SIGNUP_FORM_CLASS = "apps.accounts.forms.CustomSignupForm"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 7
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_STORE_TOKENS = False

# Chave privada do "Sign in with Apple" (arquivo .p8). Aceita o PEM direto em
# APPLE_PRIVATE_KEY ou um caminho em APPLE_PRIVATE_KEY_PATH.
APPLE_PRIVATE_KEY = env("APPLE_PRIVATE_KEY", default="")
if not APPLE_PRIVATE_KEY:
    _apple_key_path_value = env("APPLE_PRIVATE_KEY_PATH", default="").strip()
    if _apple_key_path_value:
        _apple_key_path = Path(_apple_key_path_value)
        if _apple_key_path.exists():
            APPLE_PRIVATE_KEY = _apple_key_path.read_text()

SOCIALACCOUNT_PROVIDERS = {
    "google": {"SCOPE": ["email", "profile"], "AUTH_PARAMS": {"access_type": "online"}},
    "facebook": {"SCOPE": ["email"], "FIELDS": ["email", "name"]},
    "apple": {
        "SCOPE": ["email", "name"],
        "APPS": [
            {
                "name": "Apple",
                # Services ID (ex.: com.masterlight.app) usado como client_id
                "client_id": env("APPLE_CLIENT_ID", default=""),
                "secret": env("APPLE_KEY_ID", default=""),
                "key": env("APPLE_TEAM_ID", default=""),
                "settings": {"certificate_key": APPLE_PRIVATE_KEY},
            }
        ],
    },
}

# crispy forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Pagamentos (app payments)
PAYMENT_PROVIDER = env("PAYMENT_PROVIDER", default="manual")
# Chave do Asaas lida crua via helper (ver env_helpers.py): sem o proxy de '$'
# do django-environ, que zeraria chaves '$aact_...' em ambientes como a Vercel.
ASAAS_API_KEY = asaas_api_key()
ASAAS_SANDBOX = env.bool("ASAAS_SANDBOX", default=True)
ASAAS_WEBHOOK_TOKEN = env("ASAAS_WEBHOOK_TOKEN", default="")
MANUAL_WEBHOOK_TOKEN = env("MANUAL_WEBHOOK_TOKEN", default="")

# Afiliados
AFFILIATE_COOKIE_NAME = "ref"
AFFILIATE_COOKIE_MAX_AGE = 30 * 24 * 60 * 60  # 30 dias
AFFILIATE_DEFAULT_COMMISSION_RATE = 0.10  # 10%

# Manutenção elétrica (planos de assinatura recorrente)
MAINTENANCE_PLAN_PRICES = {
    "mensal": Decimal("79.90"),
    "trimestral": Decimal("219.90"),
    "anual": Decimal("799.90"),
}

LOGIN_REDIRECT_URL = "/"
ACCOUNT_LOGOUT_REDIRECT_URL = "/"
