# AGENTS.md

Django 5 "MasterLight" (codename PlataformaVendas) — empresa de **Elétrica** (serviços + loja + afiliados). Ignore `venv/` (Python 3.13; CI/Docker usa 3.12). Marca: amarelo `#FFC107` / preto `#111` / branco.

## Commands
- Use o venv explicitamente (`python`/`ruff`/`pytest` não estão no PATH do shell): `venv/bin/python`, `venv/bin/ruff`, `venv/bin/pytest`.
- Dev server: `venv/bin/python manage.py runserver` (defaults para `config.settings.dev`, setado no `manage.py`).
- Tests: `venv/bin/pytest` (config em `pyproject.toml`, settings = `config.settings.dev`, CI exige `--cov-fail-under=70`). Root `conftest.py` tem factories compartilhadas (`UserFactory`, `ProductFactory`, `AffiliateProfileFactory`) + `create_order()` + mocks `FakeAsaasApi`/`asaas`/`activation`; testes por app em `apps/**/tests/`.
- Lint: `venv/bin/ruff check .` (line-length 100). Ordem do CI: `ruff check .` → `makemigrations --check --dry-run` → `manage.py check` → `pytest --cov=apps --cov-fail-under=70`.
- Primeira execução: `cp .env.example .env`; env vars lidas por django-environ em `config/settings/base.py`.
- Social login (allauth Google/Facebook/Apple): `venv/bin/python manage.py bootstrap_social` sincroniza `Site` + `SocialApp` a partir do `.env`. Necessário porque `ACCOUNT_EMAIL_VERIFICATION="mandatory"` e o signup social espera o app registrado.

## Branding & estáticos (não óbvio)
- **Nenhum CDN**: Bootstrap 5.3.3 é self-hosted em `static/vendor/bootstrap/`; CSS da marca em `static/css/styles.css`; logos em `static/img/{logo,favicon}.svg`. `base.html` faz `{% load static %}` + bloco `:root` inline injetando a paleta de `{{ BRAND_PALETTE }}`.
- Nome, tagline e paleta vivem em `apps/core/context_processors.py` (`branding()`: `BRAND_NAME=MasterLight`, `BRAND_TAGLINE`, `BRAND_PALETTE`) — mudar identidade é em 2 lugares: context processor + `--brand-*` de `static/css/styles.css`.
- Classes do tema: `.btn-brand`/`.btn-outline-brand`, `.bg-brand`, `.auth-panel` (480px), `.form-panel--narrow/--medium`, `.qty-input`, `.qr-img`, `.stat-card--brand`, `.toast-stack`, `.card-hover`. Prefira-as a estilos inline novos.
- Partials incluídos NÃO herdam o `{% load static %}` do `base.html` — adicione o load em cada partial que use `{% static %}`.

## Architecture
- Settings split: `config/settings/{base,dev,prod}.py`. Envs de domínio em `base.py`.
- **Seções públicas ligadas/desligadas por flag no DB**: `SiteSettings` (singleton, pk=1, editável no Admin) controla `store_enabled`/`services_enabled`/`affiliates_enabled`/`maintenance_enabled`/`provider_registration_enabled` → quando off, a view devolve 404 (visto em `apps/shop/tests` e `apps/core/tests/test_sections.py`). `provider_registration_enabled` também some com a opção "Prestador (aprovado pelo admin)" do signup (`apps/accounts/forms.py`). Se uma rota pública aparecer 404 "do nada", cheque `SiteSettings` primeiro — não é env var.
- Custom user: `apps.accounts.CustomUser`, `USERNAME_FIELD = "email"`. **Roles comparadas como strings cruas** (`"prestador"`, `"afiliado"`, `"cliente"`, `"admin"`) via mixins em `apps/core/mixins.py` — não os membros do enum.
- `apps.core.models.BaseModel`: UUID `id`, `created_at`/`updated_at`, `is_active`. Todos os modelos de domínio herdam → **PKs UUID, `<uuid:pk>` em URLs**. Filtre `is_active=True` em querysets de leitura/listagem.
- `Cart` em `apps/checkout` é **classe Python por sessão, não um model** — manter assim.
- Dinheiro é `Decimal`; floats do `Cart` são propositais, só para display.
- URL names são manualmente prefixados (ex.: `checkout-*`, `services-*`), sem namespaces `app_name`. Use `reverse_lazy("...")` com esses nomes.
- Templates por app em `apps/<app>/templates/<app>/`; `templates/` global tem `base.html` + `partials/`. Forms com crispy-forms bootstrap5.

## Pagamentos, signals & afiliados
- Abstração de gateway: `PaymentGateway` em `apps/payments/services.py` com `charge`/`refund`/`webhook`/`subscribe`/`tokenize_credit_card` + dataclass `ChargeResult`. **Para adicionar provider**: subclassifique, registre no `_REGISTRY`, set `PAYMENT_PROVIDER` no env. Registrados: `"manual"` (dev, default) e `"asaas"` (Pix/cartão real).
- `AsaasGateway` usa `requests` (`/api/v3`), valida webhook por `x-webhook-token` contra `ASAAS_WEBHOOK_TOKEN` e guarda o id Asaas em `Transaction.external_id`; `CustomUser.asaas_customer_id` cacheia o customer. Em dev, sem `ASAAS_API_KEY`, use `PAYMENT_PROVIDER=manual`.
- `charge_order(order, billing_type="PIX")` repassa o billing apenas ao Asaas; `CheckoutView.post` lê `payment_method` do form.
- Business logic só em `services.py` (os `services.py` de `apps/payments` e `apps/affiliate`). Views são wrappers; services levantam `ValueError` para erros de domínio e usam `transaction.atomic()`.
- Signals: payments imports em `PaymentsConfig.ready()`; **signals de `accounts` são ligados em `apps/core/apps.py`, não `accounts/apps.py`** — mantenha imports de signals no `apps.py` para evitar imports circulares. `Transaction` `post_save` (quando `status == "paid"`) chama `approve_referral` em `apps/affiliate/services.py`. `complete_service_request_on_paid` (post_save `Order`) é importado em `ServicesConfig.ready()` e marca a `ServiceRequest` como approved quando a `Order` vira `PAID`.
- Fluxo afiliado: `?ref=CODE` cookie (`AffiliateReferralMiddleware`) → `Referral` no checkout → approved na transação paga. Landing pública em `/afiliados/` (`affiliate-landing`); dashboard em `/afiliados/painel/` (`affiliate-dashboard`). Cookie `ref` = `AFFILIATE_COOKIE_NAME`. O afiliado cadastra a chave Pix no painel (`AffiliateProfile.pix_key`, form no dashboard) e o saque é bloqueado sem ela.
- Workaround de import circular: `django.apps.get_model("shop", "Product")` em `apps/checkout/views.py`.

## Services (fluxo)
- Catálogo público `services-list`/`services-detail` (só `is_active=True`); cliente solicita orçamento em `services-request` escolhendo **um prestador** (`ServiceRequest.prestador`, setado pelo provider via self-service).
- Prestador self-service: `ServiceCreateView` (ProviderRequiredMixin) adiciona o user a `Service.providers` ao criar. Owner gerencia em `services-my` (create/update/delete com `OwnerRequiredMixin` + `created_by`).
- Providers veem solicitações em `services-provider-requests` e enviam orçamento (`ServiceQuoteView`, só `pending` → `quoted`).
- Cliente aprova em `services-request-approve`: cria `Order(kind=SERVICE)` + `OrderItem(service=..., unit_price=final_price)`, roda `recompute_total()` e chama `charge_order(order, "PIX")`. A `ServiceRequest` vira `approved` pelo signal quando o pagamento confirma. Cancelamento em `services-request-cancel`.
- `ServiceRequest.order` é OneToOne com `checkout.Order`; `Service.created_by` e `ServiceRequest.prestador` (FK `CustomUser`, `SET_NULL`). Mock Asaas compartilhado mora no conftest raiz.

## Assinatura de manutenção (fluxo)
- Pública em `services-plan-list` (`/servicos/planos/`, flag `SiteSettings.maintenance_enabled`); cliente assina em `services-plan-subscribe` (`MaintenancePlanCreateView`, `ClienteRequiredMixin`): cria `Order(kind=SUBSCRIPTION, subscription=True)` + `OrderItem(plan=..., unit_price=valor)`, roda `recompute_total()` e chama `subscribe_plan(plan, "PIX")` (`apps/payments/services.py`).
- Gateway: `subscribe()` no `PaymentGateway` (novo método, além de `charge`/`refund`/`webhook`); `ManualGateway.subscribe()` cria a `Transaction` PENDING e redireciona para `payments-manual-confirm`; `AsaasGateway.subscribe()` cria a subscription `/api/v3/subscriptions` (ciclo `MONTHLY/QUARTERLY/YEARLY` pelo `plan_type`), salva o id em `plan.asaas_subscription_id` e aponta o webhook para o **id do primeiro payment** (`Transaction.external_id`).
- Signal `schedule_first_maintenance_visit` (post_save `Transaction`, importado em `ServicesConfig.ready()`): quando a `Transaction` vira `paid`, agenda a 1ª `MaintenanceVisit` (na data do `next_due_date`, se não houver visita nessa data) e avança `next_due_date` em `plan.cycle_days()` (30/90/365).
- `MaintenancePlan` (`plan_type` `mensal/trimestral/anual`, `value` Decimal, `next_due_date`, `order` 1:1 `checkout.Order`, `client`, `prestador`, `asaas_subscription_id`; `cycle_days()` retorna o intervalo em dias). `MaintenanceVisit` (`plan`, `scheduled_at`, `completed_at` null, `notes`; `is_pending` = sem `completed_at`). Dashboard do prestador: `services-visits` (lista) + `services-visit-complete` (seta `completed_at`).

## Conventions
- Comentários, `verbose_name`, mensagens e templates são **pt-BR** — escreva em português.
- `select_related`/`prefetch_related` em listas/detalhe; `paginate_by` 12 em listas públicas (shop/services/portfolio) e 20 no dashboard de afiliado + listas do provider.
- Role mixins: `OwnerRequiredMixin`, `ProviderRequiredMixin` (prestador/admin), `AffiliateRequiredMixin`, `ClienteRequiredMixin`.
- Admin: registro completo com `list_display`, `list_filter`, inlines, `prepopulated_fields = {"slug": ("name",)}` — sem `admin.site.register` pelado.

## Deploy
- Prod = Hostinger via Passenger, MySQL por `DATABASE_URL`. PyMySQL instalado como drop-in MySQLdb (sem build tools). Docker: gunicorn em `config.settings.prod` + `collectstatic --noinput` no build.