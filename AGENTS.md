# AGENTS.md

MasterLight — Django 5.0.7 / Python 3.12 / PostgreSQL (Supabase) platform for electric services, affiliates, and maintenance subscriptions. Brand: yellow `#FFC107` / black `#111` / white. Venv: `.venv` (3.12).

## Quick Commands

```bash
# Activate venv (Windows)
.venv\Scripts\activate
# Activate venv (Linux/macOS)
source .venv/bin/activate

# Dev server (defaults to config.settings.dev via manage.py)
python manage.py runserver

# Tests — unit tests (Django TestCase, SQLite in-memory, offline)
manage.py test apps
coverage run manage.py test apps
coverage report --fail-under=70

# E2E tests (requires live server at localhost:8000)
pytest tests/e2e/

# Lint
ruff check .
ruff format --check .

# Migrations check
python manage.py makemigrations --check --dry-run

# Django system checks
python manage.py check

# After pulling: sync site/social config for allauth
python manage.py bootstrap_social
```

**manage.py auto-selects `config.settings.test`** when args include `test` or `coverage` — no env var needed for unit tests.

## CI Order (GitHub Actions, branch `Master`)

```
ruff check .
→ manage.py makemigrations --check --dry-run (env: DJANGO_SECRET_KEY=ci-secret)
→ manage.py check (DJANGO_SETTINGS_MODULE=config.settings.dev)
→ manage.py check (DJANGO_SETTINGS_MODULE=config.settings.vercel)
→ coverage run manage.py test apps
→ coverage report --fail-under=70
```

## Architecture

- **Settings split**: `config/settings/{base, dev, production, test, vercel}.py`
  - `manage.py` defaults to `dev`, or `test` when running tests
  - `wsgi.py` defaults to `vercel`, falls back to `production`
- **All models inherit `apps.core.models.BaseModel`** — UUID PK, `created_at`/`updated_at`, `is_active`. Public querysets always filter `is_active=True`.
- **`CustomUser` uses `USERNAME_FIELD="email"`** — roles are compared as raw strings (`"prestador"`, `"afiliado"`, `"cliente"`, `"admin"`) via `RoleRequiredMixin` subclasses in `apps/core/mixins.py`, not enum members.
- **Business logic lives in `services.py` per app.** Views are thin wrappers; services raise `ValueError` for domain errors and use `transaction.atomic()`.
- **Gateway abstraction**: `PaymentGateway` base in `apps/payments/gateways/base.py`; providers registered in `_REGISTRY`, selected by `PAYMENT_PROVIDER` env var. Providers: `"manual"` (dev) and `"asaas"` (real: Pix / card only — boleto was removed).
- **URLs use manual name prefixes** (`checkout-*`, `services-*`) — no `app_name` namespaces. Use `reverse()` / `reverse_lazy()` with those names.
- **Templates live entirely at root `templates/`** (subdirectories per app: `templates/<app>/`, `templates/partials/`). No templates inside apps.
- **Static files**: CSS puro, sem Tailwind. Design tokens em `static/css/variables.css` (dark `#121212` + accent `#FFC107`, inclui `@font-face` da Inter), reset em `base.css`, sidebar de 250px (drawer mobile) em `layout.css`, componentes em `components.css`, específicos de projeto (auth-panel, stat-card, chips, avatares) em `styles.css`. Bootstrap Icons self-hosted em `static/vendor/bootstrap-icons/`; fontes Inter self-hosted. Navegação: `templates/partials/layout/sidebar.html` (substitui a antiga navbar top, removida).
- **No media upload** — images are `URLField` with `validate_image_url` validation. `SERVE_MEDIA=False` on Vercel (ephemeral filesystem).

## Key Gotchas

- **`ASAAS_API_KEY` starts with `$`** — django-environ treats `$x` as a variable reference, so the key is read raw via `os.getenv` in `config/settings/env_helpers.py` (`asaas_api_key()`). A system check (`payments.E001`) fails if `PAYMENT_PROVIDER=asaas` without a key.
- **SiteSettings section flags** (`services_enabled`, `affiliates_enabled`, `maintenance_enabled`, `provider_registration_enabled`) are in the DB (`SiteSettings`, singleton pk=1). When off, the view returns 404. If a public route appears broken, check the Admin's SiteSettings first.
- **Slugs are random and auto-generated** (`RandomSlugMixin` + `random_slug()` hex) — `Service.slug`, `ServiceCategory.slug` are `editable=False`, never user-provided, and preserved on update.
- **Boleto support was removed** (commit `97400c8`). Only Pix and card are supported via Asaas gateway.
- **`tests/e2e/` uses pytest-playwright** and requires a live dev server — separate from the unit test suite in `apps/**/tests/`.
- **Signals**: `accounts` signals connect in `apps/accounts/apps.py` (post_save for profile creation); `payments` and `affiliate` signals are imported in their respective `apps.py` `ready()` methods.

## Payment Flows

- **Checkout hosted (default with Asaas)**: `create_checkout()` redirects to Asaas payment page. Webhook `CHECKOUT_PAID`/`CHECKOUT_EXPIRED` confirms/expires; `_link_checkout_subscription` captures subscription ID for renewals.
- **Payment link**: `create_payment_link()` opens Asaas hosted page in new tab; webhook `payment.paymentLink` reconciles (creates Order + Transaction, approves ServiceRequest).
- **Webhook validation**: Asaas uses `asaas-access-token` header (legacy `x-webhook-token` also accepted). Unknown events return 200 (not 404) to avoid blocking the Asaas queue.
- **`sync_payments` command** ignores checkout transactions (reconciliation is webhook-only).

## Test Helpers (`apps/tests/helpers.py`)

- `make_user(role=, email=, cpf=, telefone=, address=)` — creates user with valid CPF/phone
- `make_service(...)`, `make_service_category(...)`, `make_affiliate(user=)`
- `create_order(user=, with_referral=, service=, qty=)` — minimal Order + OrderItem + Transaction (manual provider)
- `FakeAsaasApi` — full mock of Asaas v3 API
- `AsaasMockMixin` — TestCase mixin that installs `FakeAsaasApi` in `self.asaas`
- `mock_asaas()` — context manager version
- `FakeResponse` — lightweight mock HTTP response

## Deploy (Vercel)

- Runtime: Python 3.12 pinned in `.python-version`; WSGI entrypoint `config/wsgi.py`
- Build command (`build.py`): `check` → `migrate` → `bootstrap_social` (all idempotent)
- Cron: `0 * * * *` on `/pagamentos/reconciliar`, auth via `Authorization: Bearer <CRON_SECRET>`
- DB: Supabase Postgres, session mode (port 5432) — required for `migrate` and prepared statements
- `DJANGO_SETTINGS_MODULE=config.settings.vercel` must be set in the Vercel project env
- Migration from MySQL (legacy Hostinger): `deploy/migrate_to_vercel.sh` (dumpdata/loaddata)
