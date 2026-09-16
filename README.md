# MasterLight

Plataforma de **serviços elétricos + afiliados** com assinatura de manutenção recorrente, autenticação social (Google/Facebook/Apple) e pagamentos Pix/cartão via Asaas.

![CI](https://github.com/ThiagoRodSilva/MasterLight/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-5.0-092E20?logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?logo=postgresql&logoColor=white)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-7952B3?logo=bootstrap&logoColor=white)

> Paleta da marca: amarelo `#FFC107` · preto `#111` · branco.

---

## Sumário

- [Visão geral](#visão-geral)
- [Stack](#stack)
- [Funcionalidades](#funcionalidades)
- [Arquitetura](#arquitetura)
- [Modelo de dados](#modelo-de-dados)
- [Variáveis de ambiente](#variáveis-de-ambiente)
- [Quickstart (dev)](#quickstart-dev)
- [Pagamentos — Asaas](#pagamentos--asaas)
- [Fluxos de negócio](#fluxos-de-negócio)
- [Testes e qualidade](#testes-e-qualidade)
- [Deploy](#deploy)
- [Segurança](#segurança)
- [FAQ / Troubleshooting](#faq--troubleshooting)
- [Roadmap](#roadmap)

---

## Visão geral

A MasterLight une três negócios em uma única plataforma Django:

1. **Serviços de elétrica** — prestadores se cadastram via self-service, clientes solicitam orçamento, aprovam com pagamento online e acompanham o status.
2. **Afiliados** — divulgação com link `?ref=CODE`, comissão por venda e saque via Pix.
3. **Assinatura de manutenção** — planos mensal/trimestral/anual com cobrança recorrente e agenda de visitas para o prestador.

O público pode navegar em `/servicos/` e `/afiliados/`. Seções são ligadas/desligadas por flags no banco (`SiteSettings`, editável no Admin).

## Stack

| Camada | Tecnologia |
|---|---|
| Runtime | Python 3.12 (`.python-version`) · Django 5.0.7 |
| Banco | PostgreSQL (Supabase) via `DATABASE_URL` — `psycopg[binary]` |
| Auth | django-allauth (Google / Facebook / Apple) + login email/username |
| Frontend | Bootstrap 5.3.3 self-hosted · django-crispy-forms · widget-tweaks |
| Pagamentos | `PaymentGateway` abstrato — `ManualGateway` (dev) e `AsaasGateway` (Pix/cartão) |
| Estáticos | Whitenoise (collectstatic no build) |
| Testes | runner nativo Django + coverage (SQLite em memória) |
| CI | GitHub Actions (ruff, migrations, check, testes) |

## Funcionalidades

- **Serviços**: `Service` + `ServiceCategory`, self-service de prestador (`services-my`), solicitação de orçamento (`services-request`), orçamento (`ServiceQuoteView`), aprovação que cria `Order` e cobra (`ServiceRequestApproveView`), link de pagamento avulso com reconciliação (`ServiceRequestPayLinkView`), cancelamento.
- **Assinatura de manutenção**: `MaintenancePlan` (mensal/trimestral/anual), cobrança recorrente via `subscribe()` ou Checkout hosted `RECURRENT`, `MaintenanceVisit` pendentes/concluídas no dashboard do prestador.
- **Afiliados**: landing pública (`affiliate-landing`), painel (`affiliate-dashboard`), cadastro de chave Pix, `Referral` por `?ref=` cookie, `PayoutRequest`.
- **Checkout**: `Order`/`OrderItem`/`Address`, recompute de total.
- **Pagamentos**: `Transaction` com `external_id` (id Asaas) e `raw_payload` (ex.: `pix` do QR Code); webhook valida `x-webhook-token`.
- **Admin**: registro completo com `list_display`/`list_filter`/inlines + `SiteSettings` (flags de seção) e `ProviderApplication` (aprovação de prestador).

## Arquitetura

```
config/
├── settings/
│   ├── base.py      # compartilhado (DB, auth, pagamentos, afiliados)
│   ├── dev.py       # DEBUG + email console
│   ├── test.py      # testes: SQLite em memória (offline)
│   ├── prod.py      # Hostinger legado (HTTPS/HSTS, SMTP)
│   └── vercel.py    # produção Vercel (serverless)
└── urls.py          # montagem dos apps

apps/
├── core/        # BaseModel, mixins, SiteSettings, context processors, social_bootstrap
├── accounts/    # CustomUser (roles), perfis, ProviderApplication, signup social
├── portfolio/   # Portfólio do prestador
├── services/    # Serviços, orçamentos, planos de manutenção
├── affiliate/   # Landing, painel, Referral, PayoutRequest
├── checkout/    # Order, OrderItem, Address
├── payments/    # Transaction, PaymentGateway, webhook, reconciliação
└── tests/       # helpers/factories compartilhados
```

### Apps (visão por responsabilidade)

| App | Responsabilidade |
|---|---|
| `apps.core` | `BaseModel` (UUID PK, timestamps, `is_active`), `SiteSettings`, mixins de role, branding, `bootstrap_social` |
| `apps.accounts` | `CustomUser` (roles), `PublicProfile`, `ProviderApplication`, signals de perfil |
| `apps.portfolio` | CRUD do portfólio do prestador (imagem por URL) |
| `apps.services` | Categorias/serviços, orçamentos, self-service de prestador, planos de manutenção e visitas |
| `apps.affiliate` | Landing pública, painel, `Referral`, `PayoutRequest` |
| `apps.checkout` | `Order`, `OrderItem`, `Address` |
| `apps.payments` | `Transaction`, `ManualGateway`/`AsaasGateway`, webhook, reconciliação |

### Pontos-chave

- **PKs UUID**: todos os modelos de domínio herdam `BaseModel` — URLs de detalhe/edição usam `<uuid:pk>`. Listagens públicas de `services` usam `<slug:slug>` (slugs aleatórios auto-gerados por `RandomSlugMixin`).
- **Roles** (`CustomUser.Role`): `cliente`, `prestador`, `afiliado`, `admin` — comparadas como strings cruas nos mixins (`ProviderRequiredMixin`, `AffiliateRequiredMixin`, `ClienteRequiredMixin`, `OwnerRequiredMixin`) e no `SectionEnabledMixin` (404 quando a seção está off).
- **Business logic** mora em `services.py` (camada de aplicação); views são wrappers. Services levantam `ValueError` para erros de domínio e usam `transaction.atomic()`.
- **Gateway abstrato**: `PaymentGateway` em `apps/payments/services.py` com `charge`/`refund`/`webhook`/`subscribe`/`tokenize_credit_card` + `create_payment_link`; providers registrados em `_REGISTRY` e selecionados por `PAYMENT_PROVIDER`.

### Mapa de URLs (raiz)

| Prefixo | App | Público |
|---|---|---|
| `/` | `home` |  |
| `/admin/` | Django Admin | ❌ |
| `/accounts/` | accounts (`me`, `u/<username>`) | parcial |
| `/portfolio/` | portfolio | parcial |
| `/servicos/` | services (catálogo de serviços, planos, visitas) | parcial |
| `/afiliados/` | affiliate (landing + painel) | parcial |
| `/carrinho/` | checkout | ❌ |
| `/pagamentos/` | payments (webhook, confirmações, status) | parcial |
| `/social/` | allauth (login social) |  |

> Cada app declara `urls.py` próprio (raiz `home` em `config/urls.py`) com **nomes de URL manualmente prefixados** (ex.: `checkout-*`, `services-*`), sem `app_name`. Use `reverse("...")`/`reverse_lazy("...")` com esses nomes.

## Modelo de dados

| App | Modelo | Destaques |
|---|---|---|
| core | `SiteSettings` | singleton (pk=1), flags `services_enabled`/`affiliates_enabled`/`maintenance_enabled`/`provider_registration_enabled` |
| accounts | `CustomUser` | `USERNAME_FIELD="email"`, `role`, `asaas_customer_id`, avatar (URL) |
| accounts | `PublicProfile` / `ProviderApplication` | 1:1 user; aplicação de prestador com status |
| portfolio | `PortfolioItem` | `image` (URL), `created_by` |
| services | `ServiceCategory` / `Service` | `providers` M2M `CustomUser`, `created_by`; `image` (URL) |
| services | `ServiceRequest` | `cliente`, `prestador`, `service`, `order` 1:1 `checkout.Order`, status `pending→quoted→approved→concluded/canceled` |
| services | `MaintenancePlan` | `plan_type` (mensal/trimestral/anual), `value`, `next_due_date`, `order` 1:1, `asaas_subscription_id`, `cycle_days()` |
| services | `MaintenanceVisit` | `plan`, `scheduled_at`, `completed_at`, `is_pending` |
| affiliate | `AffiliateProfile` | `code` (p/ `?ref=`), `pix_key`, `commission_rate`, `balance` |
| affiliate | `Referral` / `PayoutRequest` | status pending/approved/rejected/paid/canceled; saque via Pix |
| checkout | `Order` / `OrderItem` / `Address` | status, `kind` (product/service/subscription), `recompute_total()`/`decrement_stock()` |
| payments | `Transaction` | `provider`, `external_id`, `status`, `raw_payload` |

## Variáveis de ambiente

Todas lidas por `django-environ` de `.env` (gitignored) ou do ambiente. Veja `.env.example`.

| Variável | Obrigatória | Descrição |
|---|---|---|
| `DJANGO_SECRET_KEY` |  prod | Secret do Django |
| `DJANGO_DEBUG` | — | `True` em dev (default `False`) |
| `DJANGO_ALLOWED_HOSTS` |  prod | Hosts permitidos (vírgula separado) |
| `DATABASE_URL` |  | Postgres do Supabase em **session mode (porta 5432)** |
| `DJANGO_CONN_MAX_AGE` | — | Idade máxima da conexão (default `60`) |
| `DJANGO_SITE_DOMAIN` / `DJANGO_SITE_NAME` |  | Domínio/nome para `django.contrib.sites` + allauth |
| `DJANGO_LANGUAGE_CODE` / `DJANGO_TIME_ZONE` | — | `pt-br` / `America/Sao_Paulo` |
| `PAYMENT_PROVIDER` | — | `manual` (dev) ou `asaas` |
| `ASAAS_API_KEY` / `ASAAS_SANDBOX` / `ASAAS_WEBHOOK_TOKEN` | se `asaas` | Credenciais Asaas |
| `MANUAL_WEBHOOK_TOKEN` | se `manual` | Token do webhook manual |
| `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` | p/ social | Google OAuth |
| `FACEBOOK_CLIENT_ID`/`FACEBOOK_CLIENT_SECRET` | p/ social | Facebook OAuth |
| `APPLE_CLIENT_ID`/`APPLE_TEAM_ID`/`APPLE_KEY_ID`/`APPLE_PRIVATE_KEY` | p/ social | Sign in with Apple |
| `DJANGO_EMAIL_HOST`/`DJANGO_EMAIL_PORT`/`DJANGO_EMAIL_HOST_USER`/`DJANGO_EMAIL_HOST_PASSWORD`/`DJANGO_DEFAULT_FROM_EMAIL` | p/ prod | SMTP |
| `CRON_SECRET` | na Vercel | Autoriza `/pagamentos/reconciliar` (cron) |

### Sobre a `DATABASE_URL` do Supabase

Use a string **session mode (porta 5432)** do Supavisor — necessária para `migrate` e prepared statements no build da Vercel:

```
postgresql://postgres.<ref>:<password>@aws-<region>.pooler.supabase.com:5432/postgres
```

Transaction mode (porta 6543) é recomendado apenas p/ serverless high-scale e exigiria `migrate` via 5432. Em `base.py`, quando o ENGINE é postgres, `DISABLE_SERVER_SIDE_CURSORS=True` é forçado automaticamente.

## Quickstart (dev)

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # edite DATABASE_URL, chaves sociais etc.
python manage.py migrate
python manage.py bootstrap_social   # sincroniza Site + SocialApp (allauth)
python manage.py createsuperuser
python manage.py runserver
```

- O `manage.py` usa `config.settings.dev` por padrão.
- **Testes não usam o banco de dev**: `config.settings.test` força SQLite em memória (ver [Testes](#testes-e-qualidade)).

## Pagamentos — Asaas

1. Crie uma conta no Asaas (sandbox para testes).
2. Em `.env`:
   - `PAYMENT_PROVIDER=asaas`
   - `ASAAS_API_KEY=<access_token de integração>`
   - `ASAAS_SANDBOX=True` (ou `False` em produção)
   - `ASAAS_WEBHOOK_TOKEN=<token do webhook no Asaas>`
3. No painel do Asaas, cadastre a URL do webhook: `https://SEUDOMINIO/pagamentos/webhook/`.
4. A cobrança cria um `Transaction` pendente; o webhook mapeia eventos (`PAYMENT_CONFIRMED` → pago, `PAYMENT_OVERDUE` → falha) e o signal aprova a referência/credita comissão.

Fluxos suportados pelo `AsaasGateway`:

| Tipo | Como | Confirmação |
|---|---|---|
| Pix | cobrança `PIX` | `payments-pix-confirm` (QR code) |
| Cartão | tokenização via `tokenize_credit_card` | `payments-card-confirm` |
| Checkout hosted | `create_checkout()` (`POST /checkouts`, página do Asaas) — **fluxo padrão com provider `asaas`** (orçamento e assinatura), webhook `CHECKOUT_PAID`/`CHECKOUT_EXPIRED` | redireciona para a URL do Asaas; callback `payments-checkout-callback` |
| Link avulso | `create_payment_link()` (`POST /paymentLinks`, tela hospedada) | nova aba; pago, o webhook `payment.paymentLink` **reconcilia**: cria `Order`+`Transaction` e aprova a `ServiceRequest` |

> Em desenvolvimento, deixe `PAYMENT_PROVIDER=manual` — nenhuma API real é chamada, apenas transações marcadas.

## Fluxos de negócio

### Serviços (orçamento)

1. **Prestador (self-service)**: cria o serviço em `/servicos/meus-servicos/` (`services-my`) e vira provider daquele serviço automaticamente (`ServiceCreateView`).
2. **Cliente**: navega em `/servicos/`, vê o detalhe e escolhe **um prestador** ao solicitar orçamento (`services-request`).
3. Prestador recebe a solicitação (`pending`) em `/servicos/prestador/solicitacoes/` (`services-provider-requests`) e envia orçamento (`final_price`) via `services-request-quote`.
4. Cliente **aprova** o orçamento (`services-request-approve`): cria `Order(kind=SERVICE)` + `OrderItem(unit_price=final_price)`, roda `recompute_total()` e chama `checkout_or_charge` — com provider `asaas`, redireciona para o Checkout hosted; senão, para o checkout embutido.
5. Webhook confirma o pagamento → signal `complete_service_request_on_paid` marca a `ServiceRequest` como `approved`.
6. Cliente acompanha em `/servicos/minhas-solicitacoes/` (`services-my-requests`) e pode cancelar enquanto pendente (`services-request-cancel`).

### Assinatura de manutenção

1. Cliente assina em `/servicos/planos/` (`services-plan-list` → `services-plan-subscribe`): cria `Order(kind=SUBSCRIPTION, subscription=True)` + `OrderItem(plan=...)`.
2. Com `PAYMENT_PROVIDER=asaas`, redireciona para o Checkout hosted `RECURRENT` (`create_checkout()`, `subscription.cycle` pelo `plan_type`) e o id da assinatura é capturado no webhook `CHECKOUT_PAID` (`_link_checkout_subscription`); com provider manual, `subscribe_plan(plan, "PIX")` cria `Transaction` PENDING e redireciona para `payments-manual-confirm`.
3. Quando a `Transaction` vira `paid`, o signal `schedule_first_maintenance_visit` agenda a 1ª `MaintenanceVisit` (no `next_due_date`) e avança `next_due_date` por `plan.cycle_days()` (30/90/365).
4. Prestador gerencia visitas em `/servicos/visitas/` (`services-visits`) e conclui com `services-visit-complete`.

### Afiliados

1. Visitante chega com `?ref=CODE` → cookie de 30 dias (`AffiliateReferralMiddleware`).
2. Checkout lê o cookie, cria `Referral` ligado ao afiliado.
3. Pagamento aprovado → signal `approve_referral` credita comissão no `AffiliateProfile.balance`.
4. Afiliado cadastra a chave Pix no painel (`affiliate-pix-key`) — saque é bloqueado sem ela — e solicita saque em `affiliate-payout` (`PayoutRequest`). Admin aprova/efetua.

## Testes e qualidade

```bash
# Lint (line-length 100)
venv/bin/ruff check .

# Migrations sem diff
venv/bin/python manage.py makemigrations --check --dry-run

# Django check
venv/bin/python manage.py check

# Testes (SQLite em memória, offline)
DJANGO_SETTINGS_MODULE=config.settings.test venv/bin/python manage.py test apps

# Cobertura (mínimo 70%; hoje ~95%)
DJANGO_SETTINGS_MODULE=config.settings.test venv/bin/coverage run manage.py test apps
venv/bin/coverage report --fail-under=70
```

- Helpers compartilhados em `apps/tests/helpers.py`: `make_user`/`make_service`/`make_service_category`/`make_affiliate`, `create_order()` e o mock `FakeAsaasApi` (`AsaasMockMixin` ou `mock_asaas()`).
- Testes por app em `apps/**/tests/`.
- CI (`.github/workflows/ci.yml`, Python 3.12): ruff → `makemigrations --check` → `manage.py check` (dev e vercel) → testes + cobertura.

## Deploy

### Vercel (padrão atual)

- Runtime **Python 3.12** pinned em `.python-version` (paridade com CI).
- Entrypoint WSGI `config/wsgi.py`; settings `config.settings.vercel` via env `DJANGO_SETTINGS_MODULE` (obrigatória).
- Build command `python build.py` (em `[tool.vercel.scripts]`): roda `migrate` + `bootstrap_social` em todo deploy (idempotentes). A Vercel roda `collectstatic` e serve estáticos do CDN.
- `vercel.json`: `maxDuration=60` + `excludeFiles` para a function `config/wsgi.py`; cron `0 * * * *` em `/pagamentos/reconciliar` (autenticado por `Authorization: Bearer <CRON_SECRET>`).

**Configuração no dashboard (uma vez):**

1. Importe o repositório; conecte o projeto ao repositório Git.
2. Env vars (obrigatória: `DJANGO_SETTINGS_MODULE=config.settings.vercel`):
   `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS=masterlightoficial.com.br,www.masterlightoficial.com.br,.vercel.app`,
   `DJANGO_SITE_DOMAIN`, `DJANGO_SITE_NAME`, `DATABASE_URL` (Supabase session mode),
   `PAYMENT_PROVIDER`, `ASAAS_*`, `MANUAL_WEBHOOK_TOKEN`, sociais e SMTP, `CRON_SECRET`.
3. Domínio: apex + `www` para a Vercel.
4. No Asaas, atualize o webhook para `https://SEUDOMINIO/pagamentos/webhook/`.
5. Suba os dados após o primeiro build (ou carregue no Supabase diretamente).

> **Media**: não há upload. Imagens (produtos, serviços, portfólio, avatar) são **links** (`URLField` com `validate_image_url`) — sem bucket, sem `django-storages`. `SERVE_MEDIA=False` na Vercel (filesystem efêmero).

### Migração de dados MySQL → Postgres

`deploy/migrate_to_vercel.sh` faz dumpdata/loaddata do MySQL (Hostinger) para o Postgres (Supabase).

## Segurança

- Produção roda com `SECURE_SSL_REDIRECT=True` e HSTS de 1 ano (`SECURE_HSTS_SECONDS`).
- Secrets (chaves, senhas, tokens) vivem em `.env`/env vars — `.env` e `.env.local` são gitignored. Nunca commite chaves.
- `SECRET_KEY` de produção deve ser único e nunca reutilizado entre ambientes.
- Webhooks de pagamento validam token (`x-webhook-token`).

## FAQ / Troubleshooting

**Uma rota pública voltou 404 "do nada".** Cheque o `SiteSettings` no Admin (`pk=1`) — cada seção tem uma flag (`services_enabled`, `affiliates_enabled`, ...). Quando off, a view devolve 404. Não é env var.

**Login do admin falha na produção.** Confirme que a `DATABASE_URL` da Vercel aponta para o Supabase onde o usuário foi criado (session mode 5432).

**Testes falham conectando no Postgres.** Use `DJANGO_SETTINGS_MODULE=config.settings.test` — os testes rodam em SQLite em memória e não tocam o banco de dev.

**Conexão com o Supabase recusada.** Projetos free pausam após ~7 dias de inatividade — retome pelo dashboard. Se estiver usando transaction mode (6543), volte para 5432 (migrate/prepared statements).

**Imagem não aparece.** As imagens são URLs externas (`URLField`). Valide a extensão (jpg/jpeg/png/gif/webp/avif/svg) e a acessibilidade da URL.

## Roadmap

- [x] Asaas Checkout hosted (página de pagamento do Asaas) substituindo o checkout embutido em orçamento e assinatura.
- [x] Reconciliação automática de `paymentLink` (link avulso agora cria `Order`+`Transaction` e aprova a solicitação no webhook).
- [ ] Parcelamento (installments) no cartão.
- [ ] `GET /checkouts/{id}` na reconciliação ativa (`sync_payments`) — hoje os checkouts são reconciliados apenas por webhook.
- [ ] Expandir cobertura de testes além de 95% (meta mínima 70% no CI).

---

## Plano de layout (UI)

> Estado: aprovado/planejado — pronto para execução.
> Escopo: home, listagens, detalhes, navbar/footer, painéis, checkout/pagamento.
> Direção visual: **moderno e confiável**. Paleta mantida: amarelo `#FFC107` / preto `#111` / branco.

### Diagnóstico atual

- **Navbar**: preta, sticky — funcional mas "crua" (sem contador de carrinho, sem CTA, mobile básico).
- **Home**: hero centrado simples + 3 cards + 4 passos + 3 destaques + faixa escura. Sem prova social, sem destaques de produtos/serviços, sem "por que confiar".
- **Listagens** (serviços/portfólio): topo título+busca + chips + grid uniforme de cards. Sem card em destaque, sem contexto/suporte.
- **Detalhes** (produto/serviço): 2 colunas básicas, sem galeria clicável, sem stock/garantia, sem relacionados.
- **Painéis** (afiliado/prestador/me): stat-cards + tabelas direto, sem cabeçalho de página, sem consistência entre páginas.
- **Checkout/pagamento**: estrutura 2-col boa; stepper frágil (3 badges soltos), confirmações ok.
- **Footer**: 3 colunas sem contato/newsletter.

### Direção visual (padrão Feature-Rich Showcase, mantendo paleta)

- Tipografia display forte (Inter já carregada), espaçamento generoso (`--space-16/20`).
- Hierarquia clara: **eyebrow → título → sub → CTA** em todos os cabeçalhos de seção.
- Prova social (stats/trust badges) no hero e antes do CTA final.
- Cards com hover lift, imagem com zoom, foco visível, `prefers-reduced-motion` preservado.

### Fase 1 — Fundação: novos componentes CSS

`static/css/components.css` (adicionar; tokens/styles.css ficam como base):

1. `.page-header` — padrão de topo para listagens/painéis: eyebrow + título + descrição + ações à direita.
2. `.hero` — evoluir: lado esquerdo texto/CTA + **stats strip** (`hero-stats`) e badge de credibilidade.
3. `.step-timeline` — passos numerados com linha conectora (home + planos).
4. `.featured-card` / `.card-media` — card destaque com imagem em zoom no hover.
5. `.gallery-thumb` — miniaturas clicáveis no detalhe do produto.
6. `.trust-row` — badges de confiança (pagamento seguro, garantia, atendimento) reutilizável.
7. `.stepper` — fluxo carrinho/pagamento/confirmação com círculos numerados + linha.
8. `.panel-header`, `.stat-card__icon` — cabeçalhos e stat-cards melhorados p/ painéis.
9. `.newsletter`, `.footer-contact` — footer rico.
10. `.related-row` — produtos/serviços relacionados.
11. Responsividade 375/768/1024/1440 + `prefers-reduced-motion`.

### Fase 2 — Home (`templates/home.html` + `apps/core/views.py`)

- **Hero**: eyebrow ("Elétrica residencial e comercial"), título display, sub, CTAs duplos, **stats strip** (ex.: "500+ projetos · 4,9/5 satisfação · resposta em 24h" — valores estáticos de marketing no template, sem model), trust badges.
- **"O que oferece"**: cards enriquecidos (ícone em tile colorido, título, descrição, CTA-link "Ver serviços →").
- **Nova seção "Destaques"**: grid de **produtos `featured=True`** (o campo já existe) e/ou serviços — exige passar queryset na `home_view` (hoje passa `{}`).
- **"Como funciona"**: timeline horizontal numerada com linha.
- **Manutenção**: manter faixa escura, refinar CTA.

Pendência de decisão: usar estatísticas reais ou placeholders de marketing?

### Fase 3 — Listagens (serviços/portfólio)

- Topo vira `.page-header` (eyebrow + título + descrição + busca).
- Chips de categoria mantidos (podem virar "filtros em linha com contagem" se quiser).
- **1º card em destaque** (span maior, `featured`) quando houver itens em destaque; demais em grid uniforme `col-lg-3`.
- Card: imagem zoom no hover, chip de categoria, preço `badge-brand`, CTA "Ver detalhes →".
- Portfolio: manter grid, adicionar imagem cover com overlay de título.

### Fase 4 — Detalhes (serviço)

- **Serviço**: preço "A partir de", nº de profissionais, CTA "Pedir orçamento", **serviços relacionados**.
- Portfólio: detalhe maior com descrição completa + CTA "Pedir serviço" quando prestador ativo.

### Fase 5 — Navbar & Footer

- **Navbar**: CTA "Entrar" mais proeminente, item "Manutenção" já existe. Manter busca e dropdown.
- **Footer**: 4 colunas — marca+social (mantém) + **contato** (telefone/e-mail placeholders ou do `SiteSettings` se houver) + navegação (mantém) + **newsletter** (form estático visual, sem backend) + linha de copyright com links (Privacidade/Termos).

### Fase 6 — Painéis (afiliado/prestador/me)

- Padrão `.page-header` em todos (título + descrição + ação primária).
- **Affiliate**: manter stat-cards (refinar com ícone), melhorar card de link (copiar com feedback), tabelas com `.table-brand` (mantém), separar "Indicações" e "Saques" com sub-cabeçalhos.
- **Prestador**: `my_services` grid mantém; `provider_requests`/`visits`/`my_requests` ganham header padrão + contagem de pendências.
- **Me**: perfil header + stat-cards + lista de pedidos (mantém), refinar cards.

### Fase 7 — Checkout & pagamento

- **Checkout**: stepper novo (círculos numerados conectados), cards de pagamento mantêm (`form-check-input-card` com `:has()`), resumo do pedido sticky mantém, trust-row abaixo do botão.
- **Confirmações** (pix/card): manter card `auth-panel`, refinar ícone + copy; `checkout_callback` ok.

### Fase 8 — Verificação

- `ruff check .`, `manage.py check`, `makemigrations --check`, testes `apps` (smoke render com test client nas rotas-chave).
- **Atenção**: a suíte tem 1 falha + 9 erros no estado atual (ex.: `test_affiliate_withdrawal_success`). Confirmar se são pré-existentes ou causados pela mudança de marca antes de atribuir — entra como primeira sub-etapa da execução.

### Decisões pendentes

1. Stats/trust no hero e "prova social": valores **estáticos de marketing** no template (recomendado) ou sem números inventados.
2. Footer/newsletter: form **visual sem backend** (recomendado: omitir para evitar UX falsa) ou incluir.
3. Destaques na home/listagens: usar o campo `featured` existente (sem migração) — ok? Mostrar também **portfólio recente** na home?
4. 1 falha + 9 erros de teste atuais: investigar/corrigir como parte da tarefa ou apenas isolar para não mascarar o resultado do layout.

---

Projeto baseado no plano de `PLANO.md`.