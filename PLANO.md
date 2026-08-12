# Plano de Engenharia — PlataformaVendas (Conclusão)

Stack oficial: **Python 3.12 · Django 5.0 · Docker · HTML/CSS/Bootstrap 5 · SQLite (dev) / MySQL (Hostinger) · django-allauth · GitHub → Hostinger**
Paleta: Amarelo (#FFC107 / #FFD600) · Preto (#111) · Branco (#FFF)
Gateway de pagamento neste ciclo: **Manual** (interface abstrata pronta para Asaas/Mercado Pago depois)

---

## 0. Decisões alinhadas com o usuário

- **Objetivo**: Concluir features + adicionar cobertura de testes (robustez e produto completo).
- **Provedor de pagamento**: Apenas `ManualGateway` neste ciclo; plugar Asaas/Mercado Pago depois via interface `PaymentGateway`.
- **Prioridade inicial**: Features front-end (templates/views navegáveis).
- **Critério de aceitação**: pytest verde com ≥70% cobertura; fluxo manual navegável ponta a ponta; ruff limpo; `makemigrations --check` sem diff; deploy Hostinger documentado.

---

## 1. Relatório de Análise — Estado Atual

**Resumo executivo:**

- **Arquitetura sólida**: 8 apps Django modulares (core / accounts / portfolio / services / shop / affiliate / checkout / payments), settings split dev/prod, interface `PaymentGateway` abstraída, mixins reutilizáveis (OwnerRequiredMixin / ProviderRequiredMixin / AffiliateRequiredMixin), BaseModel compartilhado.
- **Migrations em dia**: 7 `0001_initial.py` aplicadas; `db.sqlite3` contém todas as ~28 tabelas das apps.
- **CI parcial**: roda `ruff check`, `makemigrations --check --dry-run`, `manage.py check` — **não executa testes**.

**Diagnóstico por severidade:**

| Prioridade | Item | Local |
|---|---|---|
| 🔴 Crítico | Cobertura de testes 0% (pytest-django instalado, nenhum `test_*.py`). | `apps/**`, `.github/workflows/ci.yml` |
| 🔴 Crítico | `ManualGateway.webhook` não implementado (`pragma: no cover`); `WebhookView` aceita payload sem validar. | `apps/payments/services.py:32`, `apps/payments/views.py:14` |
| 🟠 Importante | `CheckoutView.post` importa `apps.shop.models.Product` dentro da função (binding tardio / cheiro de dependência circular). | `apps/checkout/views.py:26,52` |
| 🟠 Importante | Templates/views faltantes para fluxo navegável ponta a ponta (`me.html`, `portfolio/form.html`, `shop/list.html` com paginação/filtro/busca, etc.). | `apps/**/templates/` |
| 🟠 Importante | Signal `post_save` em `Transaction` ausente: pagamento aprovado não atualiza `Order.status` nem credita comissão no `AffiliateProfile.balance`. | `apps/payments/` |
| 🟡 Melhoria | Admin apenas com `admin.site.register` básico; faltam `list_display` / `list_filter` / `inlines`. | `apps/*/admin.py` |
| 🟡 Melhoria | `pyproject.toml` sem config de coverage; `.ruff_cache/` não ignorado. | `pyproject.toml`, `.gitignore` |

---

## 2. Design Proposto (mantém arquitetura atual, feature-based)

```
apps/<app>/
├── models.py
├── services.py          # regras de negócio (camada de aplicação)
├── views.py
├── repositories.py      # (lazy) extrair queries reutilizáveis
├── admin.py             # com list_display / list_filter / inlines
├── migrations/
├── templates/<app>/
└── tests/
    ├── factories.py
    ├── test_models.py
    ├── test_services.py
    └── test_views.py
```

**Decisões de design:**

- **Service layer preservada e ampliada**: `payments.charge_order` existe; criar `affiliate.process_referral_approval` e `affiliate.create_payout_request` — SRP e testabilidade.
- **Tests pytest-django** (já configurado em `pyproject.toml`) com estrutura `tests/` por app + `conftest.py` raiz + `factory-boy`.
- **Webhook Manual**: implementar parse JSON + validação mínima (raise em payload inválido) para fechar o contrato da interface sem gateway externo (YAGNI).
- **CI**: adicionar step `pytest --cov=apps --cov-fail-under=70` ao workflow existente.
- **Princípios**: SOLID · DRY · KISS · YAGNI aplicados visivelmente.

---

## 3. Pitágoras — Sprints de Implementação

> Ordem de entrega por módulo: **interfaces → testes → implementação**. Entregamos módulo a módulo, validando antes de avançar.

### Sprint 1 — Front-end features (prioridade) Concluido!

1. **Templates faltantes**: `accounts/me.html` (dashboard do usuário), `portfolio/form.html`, `portfolio/list.html`, `portfolio/detail.html`, revisar `shop/list.html` (paginação + filtro de categoria + busca `?q=`) e `shop/detail.html`, `services/request_form.html` com crispy-forms.
2. **Views/URLs faltantes**: confirmar que todas as apps registram `urls.py`; adicionar `shop/category/<slug>` e parâmetro `q` de busca; `services/request_form` valida que apenas prestadores solicitam orçamento.
3. **Navbar / links / mensagens**: revisar `templates/partials/navbar.html` apontando todas as rotas; `partials/messages.html` converte níveis do Django messages para classes Bootstrap.
4. **`Cart` / import circular**: mover `from apps.shop.models import Product` para o topo de `apps/checkout/views.py` (ou injetar `get_product`) para resolver binding tardio.

### Sprint 2 — Camada de negócio / fechamento do fluxo Concluido!

5. **`ManualGateway.webhook`** (`apps/payments/services.py:32`): parse JSON, retorna `(Transaction, status)`, invalida payload inválido com `raise ValueError`.
6. **Signal `post_save` em `Transaction`**: quando status passa a `APPROVED` → atualizar `Order.status=PAID`; atualizar `Referral.status=APPROVED`; creditar `commission_rate * order.total` em `AffiliateProfile.balance`. Extrair `apps/affiliate/services.py::approve_referral(transaction)` (testável).
7. **`request_payout` refactor**: extrair `apps/affiliate/services.py::create_payout_request(profile)` — transação atômica, validação `balance > 0`, criar `PayoutRequest` e zerar `balance`. A view apenas delega.
8. **Signup com role**: custom `SignupForm` adiciona campo `role` limitado a `cliente` / `afiliado` (prestador exige aprovação admin).

### Sprint 3 — Admin polido Concluido!

9. `list_display`, `list_filter`, `search_fields`, `date_hierarchy` em todos os `admin.py`.
10. Inlines: `ProductVariantInline` / `ProductImageInline` em `ProductAdmin`; `ReferralInline` em `AffiliateProfileAdmin`; `OrderItemInline` em `OrderAdmin`.
11. `PayoutRequestAdmin.actions` para aprovar / efetuar saque (chama o service).

### Sprint 4 — Testes automatizados (a cada módulo) Concluido!

12. **Base**: `conftest.py` na raiz + `tests/factories.py` com `UserFactory`, `AffiliateProfileFactory`, `ProductFactory`, `OrderFactory`.
13. **accounts**: `test_create_affiliate_profile_signal`, `test_is_prestador`, `test_public_profile_created_no_prestador`.
14. **payments**: `test_manual_gateway_charge_creates_transaction_pending`, `test_get_gateway_factory`, `test_webhook_invalid_payload_raises`.
15. **checkout**: `test_cart_add_qty_positive`, `test_cart_empty_redirects`, `test_checkout_creates_order_with_items`, `test_checkout_moves_balance_to_referral`, `test_owner_required`.
16. **affiliate**: `test_referral_status_approved_on_payment_signal`, `test_payout_request_insufficient_balance_blocked`, `test_payout_zeroes_balance_atomic`.
17. **shop / services / portfolio**: smoke tests de views GET 200, `template_used`, filtros de categoria e busca.

### Sprint 5 — CI / Qualidade Concluido!

18. `.github/workflows/ci.yml`: adicionar `pip install pytest-cov` e step `pytest --cov=apps --cov-fail-under=70`. ✅
19. `pyproject.toml`: `[tool.coverage.run] source = ["apps"]`; `.gitignore` ignora `.ruff_cache/` e `htmlcov/`. ✅
20. `pre-commit` configurado com ruff + ruff-format. ✅

### Sprint 6 — Deploy Hostinger / Hardening Concluido!

21. `settings/prod.py`: `DEBUG=False`, `SECURE_*`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`. ✅
22. `Dockerfile` / `gunicorn.conf.py`: revisar `workers` e `bind` para Passenger; confirmar `whitenoise` (run via collectstatic no Dockerfile). ✅
23. `README.md`: revisar checklist de deploy (git pull → `migrate` + `collectstatic`). ✅

---

## 4. Critérios de Aceitação

- [x] `pytest` verde com cobertura ≥70% (CI falha abaixo disso).
- [x] CI passa em push para `main`: ruff limpo, `makemigrations --check --dry-run` sem diff, `manage.py check` ok, pytest ok.
- [x] Fluxo manual navegável ponta a ponta: (validações em Sprints 1–4 e seção 6)
- [x] `ruff check .` limpo.
- [x] Deploy Hostinger documentado no README (git pull + migrate + collectstatic).

---

## 5. Ordem de Entrega (incremental e validada)

1. Sprint 1 (front-end) — revisar com você antes de avançar.
2. Sprints 2 + 3 (negócio + admin).
3. Sprint 4 (testes por app, já com `conftest` e factories).
4. Sprint 5 (CI/qualidade) rodando verde.
5. Sprint 6 (deploy Hostinger hardening).

---

## 6. Auditoria de Bugs — Debug Completo (08/ago)

> Estado base: 135 testes verdes, coverage geral 92%, ruff/check/migrations ok. A auditoria semântica (regras de negócio, segurança, lógica de pagamento) encontrou **7 bugs reais** não cobertos pelos testes e 3 riscos.

### 🟢 Bugs confirmados

**P1 — Críticos (quebram fluxo real de pagamento)**

1. **`_ensure_customer` sem CPF → 500 no checkout** (`apps/payments/services.py:207-223`)
   - O Asaas real rejeita 400 "CPF ou CNPJ necessário" sem `user.cpf` (confirmado via smoke real). O signup de `cliente` não coleta CPF (só prestador). `CheckoutView.post` não trata `ValueError` → HTTP 500.
   - Fix: coletar/exigir CPF no cadastro ou checkout; try/except `ValueError` em `CheckoutView.post`, `ServiceRequestApproveView.post`, `MaintenancePlanCreateView.form_valid` → cancelar order/plan + `messages.error` amigável.

2. **Cartão tokeniza via `AsaasGateway()` incondicional** (`apps/checkout/views.py`, `apps/services/views.py`)
   - Com `PAYMENT_PROVIDER=manual` (dev/default), escolher CREDIT_CARD chama `AsaasGateway().tokenize_credit_card()` de verdade → sem `ASAAS_API_KEY` levanta `ValueError` → 500; com key gera lixo/custo no sandbox. Viola a abstração de `PaymentGateway`.
   - Fix: expor `tokenize_credit_card` na interface `PaymentGateway` (no-op/`NotImplementedError` no `ManualGateway`), usar via `get_gateway()`, e só mostrar o radio cartão quando `settings.PAYMENT_PROVIDER == "asaas"`.

3. **Cobrança no cartão redireciona para página de Pix** (`apps/payments/services.py:261-268` em `AsaasGateway.charge`)
   - `charge()` sempre retorna `payments-pix-confirm`, mesmo para CREDIT_CARD; essa página espera QR (`pix` vazio → "QR Code indisponível"). `subscribe()` já trata bem (cartão → `payments-manual-confirm`).
   - Fix: `redirect = payments-pix-confirm` só para PIX; `payments-manual-confirm` para CREDIT_CARD.

**P2 — Médios**

4. **`next_due_date` sempre +30 dias** (`MaintenancePlanCreateView.form_valid`)
   - `timezone.localdate() + timedelta(days=30)` fixo, ignorando QUARTERLY=90 / ANNUAL=365.
   - Fix: `next_due = localdate() + timedelta(days=plan.cycle_days())`.

5. **`_fetch_pix` antes do primeiro pagamento existir** (`apps/payments/services.py:subscribe`)
   - Se `subscriptions/{id}/payments` responder vazio, `external_payment_id` cai para `subscription_id` e `_fetch_pix` faz GET em endpoint errado → `ValueError`. Tratar lista vazia com fallback seguro.

6. **Prestador sem criar o serviço não vê solicitações** (`ProviderServiceRequestListView` / `ServiceQuoteView`)
   - Filtram por `service__created_by`, mas o form atribui qualquer `service.providers`. Provider membro sem ser `created_by` não visualiza a solicitação a ele atribuída.
   - Fix: filtrar por `service__providers` (membros) em vez de `created_by`.

7. **Campos de cartão sem `required`/validação mínima** (`checkout.html`, `plan_form.html`)
   - Envio vazio → tokenize falha → 500 (agrava itens 1–2). Adicionar `required` e validação de datas (MM/AAAA).

### 🟡 Riscos/observações

- **CPF com máscara vs dígitos**: o smoke usou CPF só dígitos; sanitar máscara no cadastro para `_ensure_customer`.
- **Duplicidade de `Order`/`plan` em falha de gateway** qdo `subscribe_plan` quebra após `Order.objects.create` dentro de `transaction.atomic()` — o try/except do item 1 deve distribuir rollback.

### 🔧 Plano de reparo

1. Gateway: mover `tokenize_credit_card` para a base `PaymentGateway`; `ManualGateway` levanta `ValueError("Cartão requer provider asaas")`. Templates só mostram radio cartão quando `PAYMENT_PROVIDER == "asaas"`. ✅
2. Redirect por billing em `charge()`: PIX → `payments-pix-confirm`; CREDIT_CARD → `payments-manual-confirm`. ✅
3. try/except `ValueError` nos três fluxos de cobrança (`CheckoutView.post`, `ServiceRequestApproveView.post`, `MaintenancePlanCreateView.form_valid`) com cancelamento de `Order`/`plan`. ✅
4. CPF do cliente: coletar no signup (todos os roles) e sanitizar; ou exigir no checkout. Impacta allauth/migração — decidir execução. ✅
5. `next_due` por `cycle_days()`. ✅
6. `ProviderServiceRequestListView`/`ServiceQuoteView` filtrar por `service__providers`. ✅
7. Campos card `required` + validação mínima de data. ✅
8. Testes para os itens 1–7 (mantendo `--cov-fail-under=70`). ✅

> ✅ Executado em 08/ago. Suíte completa: **145 testes verdes**, coverage **92%** (meta 70%), `ruff check .` limpo, `makemigrations --check` sem diff, `manage.py check` ok.

---

## Refatoração — Fases A/B/C

> Plano aprovado em 11/ago. Estado base: 223 testes verdes, coverage 95%, `ruff` limpo. Trabalho atual não commitado (~1.052 linhas) pode ser tocado. Zero mudança de schema esperada.

### Princípios-guia
- Lógica de negócio só em `services.py`; views finas (AGENTS.md).
- Pipeline do repo como critério de verde: `venv/bin/ruff check .` → `makemigrations --check --dry-run` → `manage.py check` → `coverage run manage.py test apps` (fail-under 70).
- Commit por fase (somente se solicitado).

### Fase A — DRY: orquestração "pedido + cobrança"
- **Problema**: bloco "montar cartão → tokenizar → charge → cancelar em erro" duplicado em `checkout/views.py:132-153`, `services/views.py:224-251`, `services/views.py:386-440`.
- **Novo em `apps/payments/services.py`**:
  - `BillingParams` (dataclass): `billing_type`, `credit_card_token`, `remote_ip`.
  - `resolve_billing(request, user, address=None) -> BillingParams` — lê `payment_method` do POST; se `CREDIT_CARD`, roda `prepare_card_payload` + tokenize.
  - `charge_with_rollback(order, request, params, *, subscription_plan=None) -> ChargeResult | None` — chama `subscribe_plan`/`charge_order`; em **erro cancela a Order** e registra `messages.error`; `None` em falha.
- Views refatoradas mantêm criação de Order/items/Referral/plan; só o fluxo de pagamento/cancelamento é unificado.
- **Testes**: unit tests do service (card ok, card vencido, gateway raise, `ok=False` cancela Order). Suíte existente verde **sem alterar asserts**.

### Fase B — Split de `apps/payments/services.py` (914 linhas → pacote `gateways/`)
- Estrutura: `gateways/__init__.py` (re-exports + `_REGISTRY` + `get_gateway`), `base.py` (interface + dataclasses + `WebhookAuthError`), `manual.py`, `asaas_client.py` (HTTP/retry `_api`), `asaas.py`.
- `services.py` mantém orquestração (`charge_order`, `subscribe_plan`, `create_payment_link`, `webhook_handler`, `prepare_card_payload`, novos services) **+ re-exports** (`AsaasGateway`, `ManualGateway`, ...) para não quebrar ~10 pontos de import (testes, admin, `sync_payments`).
- **Correção estrutural**: unificar assinatura `charge(order, billing_type="PIX", credit_card_token="", remote_ip="")` e `subscribe(...)` na base + Manual + Asaas; remover `if gateway.name == "asaas"` de `charge_order`/`subscribe_plan`.
- **Testes**: suíte completa verde; atualizar só imports se re-export não cobrir.

### Fase C — Qualidade e CI
1. Mockar `time.sleep` no teste de retry (patch em `apps.payments.gateways.asaas_client.time.sleep`) — zerar `time.sleep` real (`services.py:299,304`); medir antes/depois.
2. Propriedade `CustomUser.is_admin`; trocar `if not self.request.user.role == "admin"` em `services/views.py:153,168,454,465`.
3. `MaintenancePlanListView` → `TemplateView` (sem `get_queryset` retornando `[]`).
4. Mover `_descriptions` (`services/views.py:324`) para constante de classe em `MaintenancePlan`.
5. Remover `from datetime import date` local em `prepare_card_payload` (`payments/services.py:823`).
6. **Opcional**: consolidar registro de signals de `Transaction` (`payments/signals.py` + `services/signals.py`).

### Ordem de execução & rollback
1. A → suíte + novos testes.
2. C-fáceis (2–5) → `ruff` + suíte.
3. B por último → suíte completa + grep de imports órfãos (`payments.services`).

Risco baixo: cada fase começa/termina verde; regressão isola via `git stash` por arquivos.

> ✅ Executado em 11/ago. Fases A, B e C (itens 1–5) concluídas; item 6 (signals) não executado por opção. Suíte completa: **229 testes verdes**, coverage **95%** (meta 70%), `ruff check .` limpo, `makemigrations --check` sem diff, `manage.py check` ok. Fase B criou o pacote `apps/payments/gateways/` (`base.py`, `manual.py`, `asaas_client.py`, `asaas.py`) com re-exports em `services.py`; assinatura `charge`/`subscribe` unificada (sem `if gateway.name`). Fase A adicionou `resolve_billing`/`charge_with_rollback`/`BillingParams` e eliminou a triplicação de cobrança em `CheckoutView`/`ServiceRequestApproveView`/`MaintenancePlanCreateView`.

---

_Última atualização: Todos os Sprints 1–6 e plano de reparo da seção 6 executados (08/ago); refatoração A/B/C executada em 11/ago (229 testes verdes, coverage 95%)._
