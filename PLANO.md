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

### Sprint 4 — Testes automatizados (a cada módulo)

12. **Base**: `conftest.py` na raiz + `tests/factories.py` com `UserFactory`, `AffiliateProfileFactory`, `ProductFactory`, `OrderFactory`.
13. **accounts**: `test_create_affiliate_profile_signal`, `test_is_prestador`, `test_public_profile_created_no_prestador`.
14. **payments**: `test_manual_gateway_charge_creates_transaction_pending`, `test_get_gateway_factory`, `test_webhook_invalid_payload_raises`.
15. **checkout**: `test_cart_add_qty_positive`, `test_cart_empty_redirects`, `test_checkout_creates_order_with_items`, `test_checkout_moves_balance_to_referral`, `test_owner_required`.
16. **affiliate**: `test_referral_status_approved_on_payment_signal`, `test_payout_request_insufficient_balance_blocked`, `test_payout_zeroes_balance_atomic`.
17. **shop / services / portfolio**: smoke tests de views GET 200, `template_used`, filtros de categoria e busca.

### Sprint 5 — CI / Qualidade

18. `.github/workflows/ci.yml`: adicionar `pip install pytest-cov` e step `pytest --cov=apps --cov-fail-under=70`.
19. `pyproject.toml`: adicionar `[tool.coverage.run] source = ["apps"]`; `.gitignore` ignora `.ruff_cache/` e `htmlcov/`.
20. `pre-commit` configurado com ruff + ruff-format (deps já em `requirements.txt`).

### Sprint 6 — Deploy Hostinger / Hardening

21. `settings/prod.py`: `DEBUG=False`, `SECURE_*`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`.
22. `Dockerfile` / `gunicorn.conf.py`: revisar `workers` e `bind` para Passenger; confirmar `whitenoise` com `runserver_nostatic`.
23. `README.md`: revisar checklist de deploy (git pull → `migrate` + `collectstatic`).

---

## 4. Critérios de Aceitação

- [ ] `pytest` verde com cobertura ≥70% (CI falha abaixo disso).
- [ ] CI passa em push para `main`: ruff limpo, `makemigrations --check --dry-run` sem diff, `manage.py check` ok, pytest ok.
- [ ] Fluxo manual navegável ponta a ponta:
  1. Signup escolhendo role `afiliado` → ganha `AffiliateProfile` com `code`.
  2. Afiliado copia link `?ref=CODE`.
  3. Novo usuário signup com `?ref=CODE` → cookie 30 dias.
  4. Comprar produto → carrinho → checkout → `charge_order` (ManualGateway) → `Transaction PENDING`.
  5. Disparar webhook manual → `Transaction APPROVED` → `Order PAID` → `Referral APPROVED` → saldo afiliado credita.
  6. Afiliado solicita saque → admin aprova/efetua via action do admin.
- [ ] `ruff check .` limpo.
- [ ] Deploy Hostinger documentado no README (git pull + migrate + collectstatic).

---

## 5. Ordem de Entrega (incremental e validada)

1. Sprint 1 (front-end) — revisar com você antes de avançar.
2. Sprints 2 + 3 (negócio + admin).
3. Sprint 4 (testes por app, já com `conftest` e factories).
4. Sprint 5 (CI/qualidade) rodando verde.
5. Sprint 6 (deploy Hostinger hardening).

---

_Última atualização: gerado a partir da análise do código existente em 04/ago. Próximo passo sugerido: iniciar Sprint 1._
