# AGENTS.md

Django 5 "Master Light" (codename PlataformaVendas) — loja + serviços + afiliados. Ignore `venv/` (uses Python 3.13, not the 3.12 in Docker/CI).

## Commands
- Dev server: `python manage.py runserver` (defaults to `config.settings.dev` set in `manage.py`).
- Tests: `pytest` (config in `pyproject.toml`, settings = `config.settings.dev`). Root `conftest.py` has shared factories (`UserFactory`, `ProductFactory`, `AffiliateProfileFactory`) + `create_order()` helper; per-app `tests/` dirs.
- Lint: `ruff check .` (ruff config in `pyproject.toml`, line-length 100). CI runs `ruff check .` → `makemigrations --check --dry-run` → `manage.py check`.
- `cp .env.example .env` before first run; env vars are read by django-environ in `config/settings/base.py`.

## Architecture
- Settings split into `config/settings/{base,dev,prod}.py`. Add new settings (env-backed) to `base.py`.
- Custom user: `apps.accounts.CustomUser`, `USERNAME_FIELD = "email"`. **Roles are compared as raw strings** (`"prestador"`, `"afiliado"`, `"cliente"`, `"admin"`) via mixins in `apps/core/mixins.py` — not the `Role` enum members.
- `apps.core.models.BaseModel`: UUID `id`, `created_at`/`updated_at`, `is_active`. All domain models inherit it → **UUID PKs, `<uuid:pk>` in URLs**. Always filter `is_active=True` in read/list querysets.
- `Cart` in `apps/checkout` is a **session-based Python class, not a model** — keep it that way.
- Money is `Decimal`; `Cart` floats stored deliberately for display only.
- URL names are manually prefixed (e.g. `checkout-*`, `services-*`), no `app_name` namespaces. Use `reverse_lazy("...")` with these names.
- Templates: per-app `apps/<app>/templates/<app>/`; global `templates/` has `base.html` + `partials/`. Use crispy-forms bootstrap5 for forms.

## Payments & affiliate (design that matters)
- Gateway abstraction: `PaymentGateway` in `apps/payments/services.py` with `charge`/`refund`/`webhook` + `ChargeResult` dataclass. **To add a provider**: subclass it, register in `_REGISTRY`, set `PAYMENT_PROVIDER` env. `"manual"` (dev, default) e `"asaas"` (Pix/cartão real) estão registrados.
- `AsaasGateway` usa `requests` (endpoints `/api/v3`), valida webhook por `x-webhook-token` contra `ASAAS_WEBHOOK_TOKEN` e guarda o id Asaas em `Transaction.external_id`; `CustomUser.asaas_customer_id` cacheia o customer. Em dev, sem `ASAAS_API_KEY`, use `PAYMENT_PROVIDER=manual`.
- `charge_order(order, billing_type="PIX")` repassa o billing apenas ao Asaas; `CheckoutView.post` lê `payment_method` do form.
- Business logic lives in `services.py` (only `apps/payments/services.py` and `apps/affiliate/services.py` do this). Views are thin wrappers; services raise `ValueError` for domain errors and use `transaction.atomic()`.
- Signals: payments signals are imported in `PaymentsConfig.ready()`. **`accounts` signals are wired in `apps/core/apps.py` `ready()`, not `accounts/apps.py`** — keep importing signals in `apps.py` to avoid circular imports. `Transaction` `post_save` (when `status == "paid"`) calls `approve_referral` in `apps/affiliate/services.py`. `complete_service_request_on_paid` (post_save `Order`) é importado em `ServicesConfig.ready()` e marca a `ServiceRequest` como approved quando a `Order` vira `PAID`.
- Affiliate flow: `?ref=CODE` cookie → `Referral` at checkout → approved on paid transaction. Landing pública em `/afiliados/` (`affiliate-landing`); dashboard em `/afiliados/painel/` (`affiliate-dashboard`).
- Circular-import workaround pattern: `django.apps.get_model("shop", "Product")` in `apps/checkout/views.py`.

## Services (fluxo)
- Catálogo público em `services-list`/`services-detail` (somente `is_active=True`); cliente solicita orçamento em `services-request` escolhendo **um prestador** (`ServiceRequest.prestador`, configurado pelo provider via self-service).
- Prestador é self-service: `ServiceCreateView` (ProviderRequiredMixin) adiciona o user a `Service.providers` ao criar. O dono gerencia em `services-my` (create/update/delete com `OwnerRequiredMixin` + `created_by`).
- Providers veem solicitações em `services-provider-requests` e enviam orçamento (`ServiceQuoteView`, só status `pending` → `quoted`).
- Cliente aprova o orçamento em `services-request-approve`: cria `Order(kind=SERVICE)` + `OrderItem(service=..., unit_price=final_price)`, roda `recompute_total()` e chama `charge_order(order, "PIX")` (Asaas no ambiente). A `ServiceRequest` vira `approved` pelo signal quando o pagamento confirma. Cancelamento em `services-request-cancel`.
- `ServiceRequest.order` é OneToOne com `checkout.Order`; `Service.created_by` e `ServiceRequest.prestador` (FK `CustomUser`, `SET_NULL`) existem. Mock do Asaas (`FakeAsaasApi`, fixtures `asaas`/`activation`) mora no **conftest raiz** (`conftest.py`), compartilhado entre `payments` e `services`.

## Conventions
- Code comments, model `verbose_name`, messages, and templates are **pt-BR** — write in Portuguese.
- Use `select_related`/`prefetch_related` in lists/detail; `paginate_by` on public lists (12) and affiliate dashboard (20).
- Role mixins: `OwnerRequiredMixin`, `ProviderRequiredMixin` (prestador/admin), `AffiliateRequiredMixin`, `ClienteRequiredMixin`.
- Admin: full registration with `list_display`, `list_filter`, inlines, `prepopulated_fields = {"slug": ("name",)}` — no bare `admin.site.register`.

## Deploy
- Prod = Hostinger, MySQL via `DATABASE_URL`. PyMySQL is installed as MySQLdb drop-in (no build tools needed). Docker uses gunicorn on `config.settings.prod`; `collectstatic --noinput` at build.