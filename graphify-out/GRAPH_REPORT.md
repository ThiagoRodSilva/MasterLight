# Graph Report - MasterLight  (2026-09-15)

## Corpus Check
- 295 files · ~64,040 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 9 file(s) not represented in the graph (top: (none) 2, .css 2, .woff2 2)

## Summary
- 2288 nodes · 4793 edges · 178 communities (100 shown, 43 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 522 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Checkout Views Tests
- Accounts Migrations
- Core Mixins & Services
- Payment Gateways
- Affiliate & Checkout Models
- CI/CD Pipeline
- Role Separation Tests
- Affiliate Middleware Tests
- Services Maintenance
- Accounts & Affiliate Services
- Asaas Charge Tests
- Services Idempotency Tests
- Services Views Tests
- Home Page Tests
- Asaas Checkout Tests
- Affiliate Referral Integration
- Affiliate Templates
- Core Models & Shop Admin
- Payments Config & Checks
- Payments Exceptions
- Payments Views Tests
- Accounts Admin
- Checkout Forms & Cart
- Accounts Migrations & Validators
- Social Signup Complete Tests
- Accounts Forms
- Provider Services
- Payments Admin & Transactions
- Bootstrap Social Command
- Asaas Gateway Core
- Portfolio Admin & Forms
- Custom User Model
- Payments Env Helpers Tests
- Payments URLs & Views
- E2E Checkout Flow Tests
- Social Signup Middleware
- Services Admin
- Service Request Integration
- Shop Checkout Integration
- Affiliate Config & Services
- Core Context Processors
- Subscription Integration
- Domain Concepts
- Services Flow Tests
- Portfolio Views Tests
- Profile Tests
- Affiliate Profile & Utils
- Test Helpers
- Affiliate URLs & Views
- Social Account Adapters
- Profile PII Tests
- Asaas API Client
- User Profile Creation
- Affiliate Admin
- Affiliate Pix Key Forms
- Core Checks Tests
- Asaas Webhook Handlers
- Payment Orchestration
- Social Login Integration
- Social Signup Form
- Social Adapter Tests
- Gateway Selector
- Payment Signals
- Payment Confirmation Tests
- Social Signup Flow Tests
- Signup Form Validation
- Referral Service Tests
- Core View Mixins
- Cron Reconciliation Tests
- Service Quote Forms
- Provider Approval Tests
- Referral Dashboard
- Affiliate Payout Requests
- Shop Section Mixin
- Services Config & Signals
- Static JS Modules
- Affiliate Referral Middleware
- Affiliate View Base
- Vercel Settings Tests
- Email Login Tests
- Core App Config
- Model Managers
- Payment Link Tests
- Payment Integration Tests
- Payment Routes & Templates
- Account Adapters
- Core Admin
- Service Forms
- Service Request Create View
- Accounts App Config
- Accounts UUID Migrations
- Affiliate Payout Service Tests
- Sync Payments Command
- Hosted Checkout Gateway Tests
- Account Email Templates
- Auth Partial Templates
- Vercel Deploy Config
- Social Login Section Toggle
- E2E Conftest
- Layout Partials
- Affiliate Manager Queries
- Site Settings Migration
- Asaas Subscription Linking
- Transaction Kind Migration
- Service Plan Templates Migration
- Account Templates
- Checkout App Config
- Portfolio App Config
- Shop App Config
- Build Script
- Manage Script
- OpenCode Plugin
- OpenCode Graphify Plugin
- Portfolio Templates
- Payment Gateway Base
- Credit Card Tokenization
- Integration Tests Init
- WSGI Config
- Vercel Migration Script
- Home Route
- Email Signup Subject
- Form Checkbox & Field
- Form Radio & Select
- Featured & Product Cards
- Page Header & Section Head
- Social Login Templates
- MasterLight Package
- Service Request Flow
- Favicon
- Logo
- Google SVG
- Email Confirmation Subject
- Logout Template
- Pagination Partial
- Avatar UI
- Chip UI
- Empty State UI
- Gallery Thumbs UI
- Stat Card UI
- Stepper UI
- Trust Row UI
- Shop Detail Template
- Shop List Template

## God Nodes (most connected - your core abstractions)
1. `make_user()` - 253 edges
2. `AsaasGateway` - 143 edges
3. `CustomUser` - 130 edges
4. `create_order()` - 101 edges
5. `Order` - 83 edges
6. `Transaction` - 59 edges
7. `SiteSettings` - 52 edges
8. `Service` - 50 edges
9. `ServiceRequest` - 44 edges
10. `Address` - 42 edges

## Surprising Connections (you probably didn't know these)
- `CI pipeline` --semantically_similar_to--> `Pre-commit hooks config`  [INFERRED] [semantically similar]
  .github/workflows/ci.yml → .pre-commit-config.yaml
- `Ruff pre-commit hooks` --semantically_similar_to--> `Ruff check`  [INFERRED] [semantically similar]
  .pre-commit-config.yaml → .github/workflows/ci.yml
- `django-migrations-check` --semantically_similar_to--> `Missing migrations`  [INFERRED] [semantically similar]
  .pre-commit-config.yaml → .github/workflows/ci.yml
- `Testes e qualidade (SQLite em memória, coverage ≥70%)` --semantically_similar_to--> `django-migrations-check`  [INFERRED] [semantically similar]
  README.md → .pre-commit-config.yaml
- `AsaasGateway (Pix/cartão/boleto)` --references--> `requests (HTTP client p/ gateways)`  [INFERRED]
  README.md → requirements.txt

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Quality gates (lint → migrations → check → tests)** — _github_workflows_ci_ruff_check, _github_workflows_ci_missing_migrations, _github_workflows_ci_django_check, _github_workflows_ci_vercel_settings_check, _github_workflows_ci_tests, _pre-commit-config_ruff_pre_commit, _pre-commit-config_black, _pre-commit-config_pyupgrade, _pre-commit-config_django_upgrade, _pre-commit-config_django_migrations_check [EXTRACTED 1.00]
- **Abstração de gateway de pagamento (PaymentGateway + providers)** — readme_payment_gateway, readme_manual_gateway, readme_asaas_gateway, readme_asaas_checkout_hosted, readme_transaction, requirements_requests [INFERRED 0.85]
- **Fluxos de negócio da plataforma** — readme_services_flow, readme_maintenance_subscription_flow, readme_affiliate_flow, readme_webhook, readme_asaas_checkout_hosted [EXTRACTED 1.00]
- **Email Confirmation Flow** — templates_account_email_email_confirmation_message_html, templates_account_email_email_confirmation_message_txt, templates_account_email_confirm_html [EXTRACTED 0.95]
- **Allauth Account Authentication Templates** — templates_account_login_html, templates_account_signup_html, templates_account_logout_html, templates_account_email_confirm_html [EXTRACTED 0.95]
- **User Profile Management Templates** — templates_accounts_me_html, templates_accounts_me_edit_html, templates_accounts_profile_html, templates_accounts_social_signup_complete_html [EXTRACTED 0.95]
- **Páginas do programa de afiliados** — templates_affiliate_dashboard, templates_affiliate_landing, templates_affiliate_partials_stats, templates_affiliate_partials_referral_table, templates_affiliate_partials_payout_table [EXTRACTED 1.00]
- **Fluxo de checkout (carrinho -> pagamento)** — templates_checkout_cart, templates_checkout_checkout, templates_checkout_address_form, templates_url_checkout, templates_url_checkout_cart_remove [EXTRACTED 1.00]
- **Biblioteca de partials de UI de hero/seções** — templates_home, templates_affiliate_landing, templates_partials_ui_stat_card, templates_partials_ui_avatar, templates_partials_ui_section_head, templates_partials_ui_card_featured [INFERRED 0.85]
- **Auth Panel Composition Flow** — templates_partials_auth__auth_panel_html, templates_partials_auth__social_buttons_html, templates_partials_forms__submit_html [EXTRACTED 1.00]
- **Reusable Form Component System** — templates_partials_forms__field_html, templates_partials_forms__checkbox_html, templates_partials_forms__radio_html, templates_partials_forms__select_html, templates_partials_forms__submit_html [INFERRED 0.95]
- **Page Layout Skeleton Partials** — templates_partials_layout_navbar_html, templates_partials_layout_footer_html, templates_partials_layout_messages_html, templates_partials_layout_pagination_html [INFERRED 0.95]
- **Reusable UI Partial Library** — templates_partials_ui__avatar, templates_partials_ui__breadcrumb, templates_partials_ui__card_featured, templates_partials_ui__card_product, templates_partials_ui__chip, templates_partials_ui__empty_state, templates_partials_ui__gallery_thumbs, templates_partials_ui__page_header, templates_partials_ui__section_head, templates_partials_ui__stat_card, templates_partials_ui__stepper, templates_partials_ui__trust_row [INFERRED 0.95]
- **Payment Confirmation Flow** — templates_payments__status_poll, templates_payments_card_confirm, templates_payments_pix_confirm, templates_payments_manual_confirm, templates_payments_checkout_callback [INFERRED 0.85]
- **Brand-Surfaced Card Components** — templates_partials_ui__card_featured, templates_partials_ui__card_product, templates_partials_ui__stat_card, templates_payments_card_confirm, templates_payments_pix_confirm, templates_payments_manual_confirm, templates_payments_checkout_callback [INFERRED 0.85]
- **Provider Self-Service Dashboard** — templates_services_my_services_html, templates_services_provider_requests_html, templates_services_visits_html, provider_role_dashboard_concept [INFERRED 0.85]
- **Maintenance Subscription Lifecycle** — templates_services_plan_list_html, templates_services_plan_form_html, templates_services_visits_html, maintenance_subscription_concept, maintenance_visit_cycle_concept [INFERRED 0.90]
- **Service Request Lifecycle (Client → Provider → Payment)** — templates_services_request_form_html, templates_services_my_requests_html, templates_services_provider_requests_html, templates_services_quote_form_html, templates_services_request_approve_html, services_quote_flow_concept, service_request_status_machine_concept [INFERRED 0.90]

## Communities (178 total, 43 thin omitted)

### Community 0 - "Checkout Views Tests"
Cohesion: 0.06
Nodes (21): override_settings, TestCase, Testes do carrinho/checkout., Checkout deve usar in_bulk() para buscar produtos (1 query para produtos)., TestCartAddView, TestCheckoutRoleSeparation, TestCheckoutView, TestReferralCreation (+13 more)

### Community 1 - "Accounts Migrations"
Cohesion: 0.03
Nodes (31): Migration, Migration, Migration, Migration, Migration, Migration, Migration, Migration (+23 more)

### Community 2 - "Core Mixins & Services"
Cohesion: 0.06
Nodes (30): ClienteRequiredMixin, ProviderRequiredMixin, Limita acesso a prestadores/admin., Limita acesso a clientes/admin (ex.: solicitar orçamento de serviço)., MaintenancePlanCreateView, MaintenancePlanListView, MaintenanceVisitCompleteView, MaintenanceVisitListView (+22 more)

### Community 3 - "Payment Gateways"
Cohesion: 0.08
Nodes (29): Gateway real via API v3 do Asaas (Pix, cartão e assinaturas)., can_transition(), ChargeResult, CheckoutResult, BasePaymentGateway, Gateway base com funcionalidades comuns compartilhadas., Valida token de webhook; levanta WebhookAuthError se inválido., Classe base com utilitários comuns para gateways de pagamento. Extrai lógica… (+21 more)

### Community 4 - "Affiliate & Checkout Models"
Cohesion: 0.07
Nodes (29): Testes de accounts (signals de perfil)., Modelos do programa de afiliados., AddressAdmin, OrderAdmin, OrderItemInline, register, Address, Kind (+21 more)

### Community 5 - "CI/CD Pipeline"
Cohesion: 0.06
Nodes (48): CI pipeline, CI Workflow, Django check, config.settings.test, Install deps, Missing migrations, Python 3.12, Ruff check (+40 more)

### Community 6 - "Role Separation Tests"
Cohesion: 0.06
Nodes (15): TestCase, TestMeViewRequiresLogin, TestRoleProperties, TestRoleStaffSync, TestCase, TestCustomUser, TestSignals, Duas chamadas concorrentes de approve_referral creditam comissao so uma vez. (+7 more)

### Community 7 - "Affiliate Middleware Tests"
Cohesion: 0.06
Nodes (20): override_settings, TestCase, Testes do middleware de afiliado (cookie secure)., Com DEBUG=False, cookie 'ref' deve ter secure=True., Com DEBUG=True, cookie 'ref' pode ter secure=False (dev)., TestAffiliateMiddlewareSecureCookie, Aprovar orcamento de servico cria referral com comissao sobre order.total., Assinar plano cria referral com comissao sobre 1a parcela (order.total). (+12 more)

### Community 8 - "Services Maintenance"
Cohesion: 0.10
Nodes (16): MaintenanceVisit, _make_cliente(), _make_plan(), _make_prestador(), override_settings, TestCase, Testes do fluxo de manutenção elétrica (planos recorrentes)., Hosted RECURRENT: CHECKOUT_PAID nao agenda; PAYMENT_CONFIRMED agenda 1x. (+8 more)

### Community 9 - "Accounts & Affiliate Services"
Cohesion: 0.09
Nodes (28): CustomUser e perfis de role., TestCase, Testes do programa de afiliados (middleware + services)., Testes de referral em aprovacao de orcamento de servico., Testes de referral em link de pagamento avulso (webhook)., Testes de referral em checkout de produtos (loja). O checkout de produtos ja…, TestCheckoutProductReferral, TestPaymentLinkReferral (+20 more)

### Community 10 - "Asaas Charge Tests"
Cohesion: 0.10
Nodes (8): AsaasGateway, Consulta a cobrança atual no Asaas (reconciliação)., Gateway real via API v3 do Asaas (Pix e Cartão). - `charge` cria cobrança e…, TestAsaasCharge, TestAsaasCheckout, TestAsaasWebhook, create_order(), Cria Order mínima com 1 item (produto) — útil para testes de pagamento.

### Community 11 - "Services Idempotency Tests"
Cohesion: 0.06
Nodes (25): override_settings, TestCase, Testes de idempotencia e validacoes extras para Services., Testes para final_price = 0 na aprovacao., Aprovar orçamento com final_price=0 deve criar OrderItem com unit_price=0., Cancelar request com Order AWAITING_PAYMENT deve cancelar a Order., Cancelar request com Order AWAITING_PAYMENT deve setar Order.status = CANCELED., Testes de idempotencia: POST duplicado nao deve criar duplicatas. (+17 more)

### Community 12 - "Services Views Tests"
Cohesion: 0.06
Nodes (13): TestCase, ServiceListView deve usar select_related para category e prefetch para…, ServiceDetailView deve usar select_related para category/created_by e prefetch…, Testes de contagem de queries para views de prestador., ProviderServiceRequestListView deve usar select_related para service, cliente,…, Testes de contagem de queries para minhas solicitações., MyServiceRequestListView deve usar select_related para service, prestador., TestCatalogo (+5 more)

### Community 13 - "Home Page Tests"
Cohesion: 0.06
Nodes (12): TestCase, TestHomePage, TestCase, TestRoleMixinsAnonymous, TestRoleSeparation, TestCase, TestSiteSettingsSingleton, TestCase (+4 more)

### Community 14 - "Asaas Checkout Tests"
Cohesion: 0.09
Nodes (14): _make_plan(), override_settings, TestCase, Testes do AsaasGateway: cobrança Pix/cartão, refund e webhook., TestAsaasSubscription, TestAsaasWebhookTokenEnforced, TestCheckoutCallbackView, TestPixConfirmationView (+6 more)

### Community 15 - "Affiliate Referral Integration"
Cohesion: 0.07
Nodes (18): override_settings, TestCase, Múltiplos pedidos do mesmo cliente geram múltiplas comissões. Skipped in Asaas…, Teste de múltiplos pedidos com provider manual (evita idempotência do mock…, Múltiplos pedidos do mesmo cliente geram múltiplas comissões (provider manual)., Fluxo do dashboard do afiliado: visualizar comissões, cadastrar Pix, solicitar…, Fluxo completo: afiliado gera link -> cliente acessa -> compra -> comissão…, Dashboard mostra comissões pendentes e aprovadas. (+10 more)

### Community 16 - "Affiliate Templates"
Cohesion: 0.07
Nodes (36): Painel do Afiliado (dashboard.html), Landing de Afiliados (landing.html), Payout Table Partial (_payout_table.html), Referral Table Partial (_referral_table.html), Affiliate Stats Partial (_stats.html), Base Layout (base.html), Confirm Modal com <dialog> nativo, Tailwind via CDN (dev only) (+28 more)

### Community 17 - "Core Models & Shop Admin"
Cohesion: 0.10
Nodes (26): BaseModel, Meta, RandomSlugMixin, Modelo abstrato com campos de auditoria padronizados., Preenche o slug automático quando vazio. Requer que o modelo tenha um campo…, CategoryAdmin, ProductAdmin, ProductImageInline (+18 more)

### Community 18 - "Payments Config & Checks"
Cohesion: 0.10
Nodes (22): PaymentsConfig, AppConfig, asaas_api_key_check(), payment_provider_check(), register, System checks do app payments: configuracao do provedor de pagamento., Falha cedo quando PAYMENT_PROVIDER não está registrado (I1). Em dev…, Falha cedo no `manage.py check` quando o Asaas esta ativo sem chave. Sem isso a… (+14 more)

### Community 19 - "Payments Exceptions"
Cohesion: 0.09
Nodes (28): CardTokenizationError, CheckoutSessionError, GatewayNotConfiguredError, InsufficientStockError, InvalidStatusTransitionError, PaymentGatewayError, PaymentValidationError, ProfileIncompleteError (+20 more)

### Community 20 - "Payments Views Tests"
Cohesion: 0.09
Nodes (10): override_settings, TestCase, Testes do app de pagamentos (webhook + gateway manual)., TestAsaasWebhookView, TestManualConfirmationView, TestManualGatewayWebhook, TestOrderStatusView, TestPaymentConfirmationRoleSeparation (+2 more)

### Community 21 - "Accounts Admin"
Cohesion: 0.11
Nodes (21): CustomUserAdmin, ProviderApplicationAdmin, PublicProfileAdmin, action, register, Meta, ProviderApplication, PublicProfile (+13 more)

### Community 22 - "Checkout Forms & Cart"
Cohesion: 0.10
Nodes (17): AddressForm, Meta, Forms do app checkout., Form para criação/edição de endereço do usuário., Cart, Carrinho armazenado em `request.session` (camada python pura)., AddressCreateView, cart_add_view() (+9 more)

### Community 23 - "Accounts Migrations & Validators"
Cohesion: 0.09
Nodes (13): Migration, SimpleTestCase, Testes do validador de URL de imagem., TestImageURLValidator, ImageURLValidator, Validators de uso transversal., Valida URL HTTP/HTTPS apontando para uma imagem., validate_image_url() (+5 more)

### Community 24 - "Social Signup Complete Tests"
Cohesion: 0.08
Nodes (19): TestCase, Adiciona session e messages middleware mock ao request., Sem sociallogin na sessão -> redirect login., Form válido -> cria Address, conecta SocialAccount, loga usuário., Form inválido -> re-render com erros., SocialSignupCompleteViewTest, URLs de accounts: perfil publico e meus dados (allauth trata login)., me_view() (+11 more)

### Community 25 - "Accounts Forms"
Cohesion: 0.11
Nodes (17): _address_common_fields(), AddressFormMixin, BaseAccountFormMixin, _only_digits(), ProfileEditForm, Forms accounts: signup customizado com role e edição de dados., Completamento obrigatório após login social (Google)., Edição de dados pessoais e de pagamento do usuário. Atualiza nome, CPF,… (+9 more)

### Community 26 - "Provider Services"
Cohesion: 0.10
Nodes (19): demote_from_provider(), promote_to_provider(), Promove usuário a prestador (cria PublicProfile)., Rebaixa usuário de prestador para cliente (mantém PublicProfile ativo por…, Atualiza dados pessoais e endereço do usuário (upsert)., update_user_profile(), PromoteDemoteProviderServiceTest, TestCase (+11 more)

### Community 27 - "Payments Admin & Transactions"
Cohesion: 0.09
Nodes (19): action, register, TransactionAdmin, Kind, Meta, Status, Transaction, override_settings (+11 more)

### Community 28 - "Bootstrap Social Command"
Cohesion: 0.13
Nodes (14): Command, BaseCommand, Management command para bootstrap site + SocialApp a partir do .env., bootstrap_site(), bootstrap_social_apps(), Inicializacao de SocialApp para dev/prod a partir de variaveis de ambiente., Cria/atualiza SocialApp para Google/Facebook usando env se disponivel.…, Garante site id=1 com dominio configurado via env. (+6 more)

### Community 29 - "Asaas Gateway Core"
Cohesion: 0.11
Nodes (16): _run(), _run(), _run(), Exception, Monta o payload completo de criação de customer no Asaas (v3). A API v3 exige…, Executa `fn`; se falhar por customer inválido (cache obsoleto), limpa. O…, Reutiliza (e salva) o customer_id do Asaas no usuario. Busca por e-mail para…, Escolhe a página de confirmação conforme a forma de pagamento. (+8 more)

### Community 30 - "Portfolio Admin & Forms"
Cohesion: 0.13
Nodes (17): PortfolioItemAdmin, register, Meta, PortfolioItemForm, Forms do app portfolio., Form para itens do portfólio do prestador., Meta, PortfolioItem (+9 more)

### Community 31 - "Custom User Model"
Cohesion: 0.09
Nodes (11): AbstractUser, CustomUser, Retorna nome de exibição seguro (sem vazar email completo). Usa username se não…, Usuario customizado com role telefone avatar CPF. Roles: cliente -> consumidor…, Verifica se usuário tem CPF, telefone e endereço ativo para pagamentos., Role, Testes do middleware de completamento social., Testes de vazamento de PII no ProfileDetailView. (+3 more)

### Community 32 - "Payments Env Helpers Tests"
Cohesion: 0.11
Nodes (12): AsaasApiKeyTests, SimpleTestCase, Testes da leitura da chave do Asaas (env_helpers.py). Cobre o bug de…, Settings base compartilhados entre dev e prod., Settings de desenvolvimento., asaas_api_key(), Helpers de leitura de env vars que o django-environ processa de forma…, Le ASAAS_API_KEY crua, normalizando a forma escapada legada. (+4 more)

### Community 33 - "Payments URLs & Views"
Cohesion: 0.14
Nodes (18): CardConfirmationView, CheckoutCallbackView, ManualConfirmationView, OrderStatusView, PixConfirmationView, TemplateView, View, Views payments (webhook generico e confirmacao Pix). (+10 more)

### Community 34 - "E2E Checkout Flow Tests"
Cohesion: 0.10
Nodes (17): Page, E2E tests for checkout flow with Asaas hosted checkout., Home page carrega corretamente., Lista de produtos carrega., Lista de serviços carrega., Testes E2E do carrinho., Adiciona produto ao carrinho., Testes E2E de autenticação. (+9 more)

### Community 35 - "Social Signup Middleware"
Cohesion: 0.12
Nodes (12): Middleware para bloquear acesso se cadastro social incompleto., Redireciona usuário autenticado sem CPF/telefone/endereço para completamento.…, SocialSignupRequiredMiddleware, TestCase, URLs do admin são isentas., Cria usuário com SocialAccount (simula login social)., Usuário social com perfil completo acessa página normalmente., Usuário social sem CPF/telefone/endereço é redirecionado. (+4 more)

### Community 36 - "Services Admin"
Cohesion: 0.11
Nodes (16): Testes de referral em assinatura de plano de manutencao., TestSubscriptionReferral, MaintenancePlanAdmin, MaintenancePlanTemplateAdmin, MaintenanceVisitAdmin, MaintenanceVisitInline, register, ServiceAdmin (+8 more)

### Community 37 - "Service Request Integration"
Cohesion: 0.14
Nodes (11): override_settings, TestCase, Cliente cancela solicitação pendente., Prestador não pode orçar duas vezes., Orçamento só pode ser enviado em status PENDING., Fluxo com link de pagamento avulso (PaymentLink)., Fluxo: orçamento -> link de pagamento -> pagamento -> aprovado., Fluxo completo: cliente solicita -> prestador orça -> cliente aprova ->… (+3 more)

### Community 38 - "Shop Checkout Integration"
Cohesion: 0.13
Nodes (12): override_settings, TestCase, Checkout exige usuário logado., Carrinho vazio redireciona para loja., Valida estoque insuficiente no checkout., Fluxo checkout com cartão de crédito., Fluxo checkout com cartão -> webhook -> pedido pago., Fluxo completo: listar produto -> adicionar ao carrinho -> checkout ->… (+4 more)

### Community 39 - "Affiliate Config & Services"
Cohesion: 0.13
Nodes (16): AffiliateConfig, AppConfig, approve_referral(), calculate_commission(), create_referral(), Decimal, Servicos programa afiliados (camada de aplicacao)., Aprova referral pendente e credita a comissão no saldo do afiliado. Apenas a… (+8 more)

### Community 40 - "Core Context Processors"
Cohesion: 0.12
Nodes (13): branding(), cart_count(), Any, HttpRequest, Context processors globais., Conta total de itens no carrinho da sessão (badge do navbar)., Configuração global do site (linha única, editável no Admin). Controla a…, SiteSettings (+5 more)

### Community 41 - "Subscription Integration"
Cohesion: 0.12
Nodes (12): override_settings, TestCase, Apenas clientes podem assinar planos., Template inativo não pode ser assinado., Webhooks de renovações (PAYMENT_CONFIRMED) agendam visitas., Testes de listagem pública de planos., Lista pública mostra apenas templates ativos., Se manutenção desativada em SiteSettings, retorna 404. (+4 more)

### Community 42 - "Domain Concepts"
Cohesion: 0.13
Nodes (20): Hosted Checkout Payment, Maintenance Subscription Plan, Maintenance Visit Cycle, Asaas Payment Link, Provider Role Dashboard Pattern, Service Request Status Machine, Service Quote Flow, Service Detail Template (+12 more)

### Community 43 - "Services Flow Tests"
Cohesion: 0.19
Nodes (5): override_settings, TestCase, Pedido PAGO nao ressuscita ServiceRequest CANCELED. Aprovar request CANCELED…, TestApprovalCreatesOrderAndPays, TestApprovalPayLink

### Community 44 - "Portfolio Views Tests"
Cohesion: 0.14
Nodes (8): TestCase, Testes do portfolio (visibilidade)., Testes de contagem de queries para views do portfolio., PortfolioListView deve usar select_related para created_by., PortfolioDetailView deve usar select_related para created_by., TestPortfolioQueries, TestPortfolioUpdateRoleSeparation, TestPortfolioVisibility

### Community 45 - "Profile Tests"
Cohesion: 0.18
Nodes (6): TestCase, Testes do perfil: dados de pagamento no cadastro e edição de dados., TestCpfValidator, TestProfileEditView, Valida CPF brasileiro (11 dígitos e dígitos verificadores). Aceita valor…, validate_brazilian_cpf()

### Community 46 - "Affiliate Profile & Utils"
Cohesion: 0.18
Nodes (9): SimpleTestCase, Testes das utils transversais (generate_code, money_fmt)., TestGenerateCode, TestMoneyFmt, generate_code(), money_fmt(), Utils de uso transversal., Formata valor Decimal como moeda BR. (+1 more)

### Community 47 - "Test Helpers"
Cohesion: 0.14
Nodes (6): AsaasMockTestCase, FakeAsaasApi, FakeResponse, TestCase, Mock da API v3 do Asaas para testes unitários., Base que já instala o mock + settings Asaas.

### Community 48 - "Affiliate URLs & Views"
Cohesion: 0.17
Nodes (9): Views do app affiliate., AffiliateLandingView, TemplateView, View da landing page pública de afiliados., Landing pública explicando o programa de afiliados., PayoutRequestView, View, View de solicitação de saque. (+1 more)

### Community 49 - "Social Account Adapters"
Cohesion: 0.16
Nodes (11): CustomSocialAccountAdapter, Adapter para login social (Google)., Força tela de completamento — nunca auto-signup direto., Vincula conta existente por email ou prepara novo usuário., Cria usuário base (sem CPF/telefone/endereço/role — virão no completamento)., Redireciona para tela de completamento obrigatório., _build_social_login(), Monta um SocialLogin com usuário ainda não persistido (pk=None). (+3 more)

### Community 50 - "Profile PII Tests"
Cohesion: 0.13
Nodes (8): TestCase, Perfil de cliente (role=cliente) retorna 404., Prestador com public_profile ativo retorna 200., Afiliado com public_profile ativo retorna 200., HTML não contém email completo quando usuário não tem nome., Prestador sem public_profile ativo retorna 404., Usuário inativo retorna 404., TestProfileDetailViewPII

### Community 51 - "Asaas API Client"
Cohesion: 0.15
Nodes (7): AsaasApiClient, Cliente HTTP da API v3 do Asaas: retry, idempotência e formatação., Chama endpoints `/api/v3` do Asaas com retry por falha transitória. Conhece…, Chama a API do Asaas com retry por falha transitória e idempotência. - Retenta…, Remove máscara de CPF/CNPJ, mantendo apenas dígitos., Formata valor como string decimal fixa (evita precisão de float). Aceita…, Consulta a cobrança atual no Asaas (reconciliação).

### Community 52 - "User Profile Creation"
Cohesion: 0.18
Nodes (8): create_user_profile(), Cria perfil completo do usuário (CPF, telefone, endereço, role). Usado tanto no…, CreateUserProfileServiceTest, Testes para create_user_profile., Cria perfil de cliente com dados completos., Cria perfil de afiliado., Candidato a prestador mantém role=cliente e cria ProviderApplication., Se der erro na criação do endereço, usuário não é salvo.

### Community 53 - "Affiliate Admin"
Cohesion: 0.19
Nodes (10): AffiliateProfileAdmin, PayoutRequestAdmin, action, register, Admin programa afiliados., Marca saques pendentes como aprovados (status permanece PENDING neste fluxo…, Efetua saque: marca status PAID e registra paid_at atomicamente., Rejeita saques pendentes: devolve valor ao saldo do afiliado. (+2 more)

### Community 54 - "Affiliate Pix Key Forms"
Cohesion: 0.19
Nodes (8): Meta, PixKeyForm, Forms do programa de afiliados., Cadastro/atualização da chave Pix do afiliado (payout)., PixKeyUpdateView, FormView, View de cadastro/atualização da chave Pix., Cadastra/atualiza a chave Pix do afiliado para recebimento de saques.

### Community 55 - "Core Checks Tests"
Cohesion: 0.14
Nodes (8): TestCase, Testes do system check core.E001 (SECRET_KEY insegura)., DEBUG=False + SECRET_KEY='change-me-in-production' -> erro core.E001., DEBUG=False + SECRET_KEY='' -> erro core.E001., DEBUG=False + SECRET_KEY forte -> sem erros core.E001., DEBUG=True + SECRET_KEY fraca -> sem erros (dev allowed)., DEBUG=False + SECRET_KEY fraca -> erro core.E001., TestSecretKeyCheck

### Community 56 - "Asaas Webhook Handlers"
Cohesion: 0.14
Nodes (7): Processa webhook Asaas: autentica token e atualiza status., Resolve um `PAYMENT_*` redundante de Checkout hosted. O checkout DETACHED…, Cria Transaction para um pagamento vindo de paymentLink avulso. O…, Processa eventos de Checkout hosted (`CHECKOUT_*`). O payload traz `checkout`…, Captura o id da assinatura gerada por um checkout RECURRENT. O webhook…, Processa eventos de assinatura (`SUBSCRIPTION_*`). O payload traz…, Vincula o id da assinatura Asaas ao MaintenancePlan local. Busca primeiro por…

### Community 57 - "Payment Orchestration"
Cohesion: 0.22
Nodes (9): _cancel_order_if_pending(), checkout_or_charge(), Cancela a Order apenas se estiver em status pendente (OPEN/AWAITING_PAYMENT).…, Dispara Checkout hosted (Asaas). Usa Checkout hosted quando `PAYMENT_PROVIDER…, TestCase, Anexa session/messages ao request p/ `messages.error` do service., Pedido sem itens deve falhar ao criar checkout., TestCheckoutOrCharge (+1 more)

### Community 58 - "Social Login Integration"
Cohesion: 0.18
Nodes (9): complete_provider_callback(), override_settings, Callback social: novo usuário -> signup allauth; usuário existente -> login., Novo usuário Google é redirecionado para o signup do allauth e nada é criado…, Login Google em email existente vincula SocialAccount e loga direto., Login Facebook segue o mesmo fluxo de novo usuário (Google)., Login Apple (form_post) segue o mesmo fluxo de novo usuário., Dispara o callback OAuth do provider (state+code) e retorna a resposta. Mocks:… (+1 more)

### Community 59 - "Social Signup Form"
Cohesion: 0.22
Nodes (7): Atualiza usuário + cria Address + conecta SocialAccount., complete_social_signup(), Completa cadastro após login social: atualiza usuário, cria endereço, conecta…, CompleteSocialSignupServiceTest, Testes para complete_social_signup., Completa cadastro, cria endereço e conecta SocialAccount., Levanta ValueError se não houver sociallogin na sessão.

### Community 60 - "Social Adapter Tests"
Cohesion: 0.15
Nodes (7): CustomSocialAccountAdapterTest, TestCase, Nunca permite auto-signup direto., Usuário existente -> conecta SocialAccount., Novo usuário -> guarda na sessão., Cria usuário com role=cliente., Redireciona para completamento.

### Community 61 - "Gateway Selector"
Cohesion: 0.24
Nodes (7): get_gateway(), Processa webhook generico e retorna dicionario serializavel., webhook_handler(), override_settings, TestGetGateway, HttpRequest, HttpResponse

### Community 62 - "Payment Signals"
Cohesion: 0.21
Nodes (12): mark_order_paid(), Marca a Order como PAGO e baixa o estoque quando a transacao vira PAGA.…, Reverte um pedido pago quando a transacao vira REEMBOLSADA (C2). Seta a Order…, reverse_order_refund(), mark_order_paid_on_paid(), receiver, Signals payments: ordem paga/reembolsada + comissao de afiliado.…, Marca a Order como PAGO (com baixa de estoque) quando a tx vira PAGA. (+4 more)

### Community 63 - "Payment Confirmation Tests"
Cohesion: 0.22
Nodes (3): Pix confirmation deve usar select_related para order e user., TestCardConfirmationView, TestPixConfirmationView

### Community 64 - "Social Signup Flow Tests"
Cohesion: 0.21
Nodes (7): Callback + signup allauth + completamento obrigatório…, Executa callback -> signup allauth -> completamento e retorna a resposta final., Completamento cria usuário, Address, SocialAccount e loga., Sem role explícita, o padrão é cliente., Completamento permite escolher role prestador (se habilitado)., Completamento permite escolher role afiliado (se habilitado)., TestSocialSignupFlow

### Community 65 - "Signup Form Validation"
Cohesion: 0.30
Nodes (4): CustomSignupForm, Form de signup do allauth com role, CPF/telefone e endereço. allauth carrega…, TestCustomSignupFormRequiredData, TestCustomSignupFormProvider

### Community 66 - "Referral Service Tests"
Cohesion: 0.17
Nodes (7): Testes da funcao create_referral., Cria referral para pedido com codigo valido., Nao cria referral sem codigo., Nao cria referral com codigo invalido., Bloqueia auto-referral (afiliado comprando pelo proprio link)., Usa taxa do produto quando definida (override)., TestCreateReferral

### Community 67 - "Core View Mixins"
Cohesion: 0.24
Nodes (8): OwnerRequiredMixin, Any, LoginRequiredMixin, Mixins reutilizaveis para views., Base dos mixins de separação de contas. Permite apenas usuários cuja `role`…, Garante que o objeto pertence ao usuário autenticado. Admins/superusers (acesso…, RoleRequiredMixin, QuerySet

### Community 68 - "Cron Reconciliation Tests"
Cohesion: 0.17
Nodes (4): override_settings, TestCase, Testes do ReconcilePaymentsView (cron Vercel)., TestReconcilePaymentsView

### Community 69 - "Service Quote Forms"
Cohesion: 0.21
Nodes (8): Decimal, QuoteForm, Formulário para o prestador enviar o orçamento (preço final)., Testes de validacao do QuoteForm., QuoteForm deve rejeitar final_price negativo., QuoteForm deve aceitar final_price = 0 (orcamento gratis)., QuoteForm com final_price vazio deve ser valido (view preenche com base_price)., TestQuoteFormValidation

### Community 70 - "Provider Approval Tests"
Cohesion: 0.18
Nodes (6): ApproveRejectProviderApplicationServiceTest, Testes para approve_provider_application e reject_provider., Aprova solicitação, promove usuário e atualiza application., Aprovar solicitação não-pendente levanta ValueError., Recusa solicitação mantém usuário como cliente., Recusar solicitação não-pendente levanta ValueError.

### Community 71 - "Referral Dashboard"
Cohesion: 0.22
Nodes (7): Meta, Indicacao de um pedido a um afiliado (gera comissao quando pago)., Referral, AffiliateDashboardView, ListView, View do dashboard do afiliado., Dashboard do afiliado com indicações e saques.

### Community 72 - "Affiliate Payout Requests"
Cohesion: 0.24
Nodes (9): PayoutRequest, Solicitacao de saque do afiliado., Status, execute_payout_async(), process_pending_payouts(), Tasks assíncronas para o app affiliate., # TODO: Integração real com API bancária (Pix), Processa todos os payouts pendentes elegíveis para auto-payout. Pode ser… (+1 more)

### Community 73 - "Shop Section Mixin"
Cohesion: 0.27
Nodes (6): Bloqueia a view (404) quando a seção está desabilitada no Admin. Defina…, SectionEnabledMixin, ProductDetailView, ProductListView, DetailView, ListView

### Community 74 - "Services Config & Signals"
Cohesion: 0.20
Nodes (8): AppConfig, ServicesConfig, complete_service_request_on_paid(), receiver, Signals services: conclui a solicitacao quando o pedido e pago., Quando o Order de um servico e PAGO, aprova a solicitacao ligada., Quando a Transaction de assinatura e PAGA, agenda a 1ª visita. Usa o vencimento…, schedule_first_maintenance_visit()

### Community 75 - "Static JS Modules"
Cohesion: 0.22
Nodes (3): initConfirmationModal(), initPaylinkForm(), showToast()

### Community 76 - "Affiliate Referral Middleware"
Cohesion: 0.24
Nodes (5): AffiliateReferralMiddleware, Middleware que grava o cookie de afiliado a partir do parametro `?ref=`. Quando…, Le `?ref=CODE` e seta/renova o cookie `ref` so para codigos validos., AffiliateProfile, Perfil afiliado vinculado ao CustomUser (1:1). Cada usuario ganha perfil…

### Community 77 - "Affiliate View Base"
Cohesion: 0.24
Nodes (7): AffiliateBaseMixin, Mixin base para views de afiliado., Mixin base com funcionalidades comuns para views de afiliado., Retorna o AffiliateProfile do usuário atual ou 404., Gera URL de indicação com o código do afiliado., AffiliateRequiredMixin, Limita acesso a afiliados/admin.

### Community 78 - "Vercel Settings Tests"
Cohesion: 0.31
Nodes (3): SimpleTestCase, Valida que config.settings.vercel e coerente com o deploy serverless., VercelSettingsTests

### Community 79 - "Email Login Tests"
Cohesion: 0.22
Nodes (6): override_settings, TestCase, Teste: form de login usa email (allauth ACCOUNT_AUTHENTICATION_METHOD=email)., GET /social/login/ deve mostrar campo 'login' com label/placeholder de email., POST com email+senha autentica o usuário., TestLoginFormUsesEmail

### Community 80 - "Core App Config"
Cohesion: 0.22
Nodes (6): CoreConfig, AppConfig, check_secret_key(), register, System checks do app core., Valida SECRET_KEY em produção (DEBUG=False). Retorna erro se a chave for um…

### Community 81 - "Model Managers"
Cohesion: 0.25
Nodes (4): PayoutRequestManager, Manager customizado para PayoutRequest., Manager customizado para Referral., ReferralManager

### Community 82 - "Payment Link Tests"
Cohesion: 0.39
Nodes (3): create_payment_link(), Gera um link de pagamento avulso no gateway configurado., TestAsaasPaymentLink

### Community 83 - "Payment Integration Tests"
Cohesion: 0.29
Nodes (5): override_settings, TestCase, Integração ponta a ponta: compra -> PIX -> webhook -> comissão afiliado., Gera cobrança asaas e dispara webhook CONFIRMED., TestAsaasEndToEnd

### Community 84 - "Payment Routes & Templates"
Cohesion: 0.43
Nodes (7): accounts-me Route, payments-status Polling Route, Payment Status Poll UI Partial, Card Payment Confirmation Page, Asaas Checkout Callback Page, Manual Payment Confirmation Page, Pix Payment Confirmation Page

### Community 85 - "Account Adapters"
Cohesion: 0.29
Nodes (4): CustomAccountAdapter, Adapters customizados para django-allauth., Adapter para cadastro/login por email/senha., DefaultAccountAdapter

### Community 86 - "Core Admin"
Cohesion: 0.29
Nodes (4): register, Admin do app core (configurações do site)., Painel de configuração do site (singleton)., SiteSettingsAdmin

### Community 90 - "Accounts UUID Migrations"
Cohesion: 0.33
Nodes (5): backfill_timestamps(), backfill_uuids(), Migration, Backfill created_at/updated_at for existing users., Backfill UUIDs for existing users.

### Community 91 - "Affiliate Payout Service Tests"
Cohesion: 0.47
Nodes (3): create_payout_request(), Cria solicitação de saque atômica para o afiliado. Valida saldo > 0, cria…, TestCreatePayoutRequest

### Community 92 - "Sync Payments Command"
Cohesion: 0.33
Nodes (3): Command, BaseCommand, Sincroniza o status de transações Asaas pendentes com a API. Útil para…

### Community 93 - "Hosted Checkout Gateway Tests"
Cohesion: 0.47
Nodes (3): TestCase, Testes do gateway Asaas para checkout hospedado., TestAsaasGatewayHostedCheckout

### Community 94 - "Account Email Templates"
Cohesion: 0.33
Nodes (6): Email Confirmation Page, Email Confirmation Message (HTML), Email Confirmation Message (TXT), Signup email confirmation message (plain text), Login Page, Signup Page

### Community 95 - "Auth Partial Templates"
Cohesion: 0.33
Nodes (6): Auth Panel Partial, Auth Panel Component, Social Login Buttons Partial, Form Submit Button Partial, Toast Messages Partial, Toast Notification Pattern

### Community 96 - "Vercel Deploy Config"
Cohesion: 0.33
Nodes (5): excludeFiles, maxDuration, functions, config/wsgi.py, $schema

### Community 97 - "Social Login Section Toggle"
Cohesion: 0.40
Nodes (3): TestCase, Login social desativado por SiteSettings., TestSocialLoginSectionToggle

### Community 98 - "E2E Conftest"
Cohesion: 0.60
Nodes (4): fixture, base_url(), browser(), page()

### Community 99 - "Layout Partials"
Cohesion: 0.70
Nodes (5): Site Footer Partial, Feature-Flag-Gated Navigation, Navigation Bar Partial, Feature-Flag-Gated Navigation, Role-Based Navigation Pattern

### Community 103 - "Transaction Kind Migration"
Cohesion: 0.50
Nodes (3): backfill_kind(), Migration, Marca como `checkout` as transações de Checkout hosted já existentes. Antes do…

### Community 105 - "Account Templates"
Cohesion: 0.67
Nodes (4): User Profile Edit Page, User Dashboard (Me) Page, Public Profile Page, Social Signup Completion Page

### Community 113 - "Portfolio Templates"
Cohesion: 0.67
Nodes (3): Portfolio Detail Template, Portfolio Form Template, Portfolio List Template

## Knowledge Gaps
- **133 isolated node(s):** `$schema`, `plugin`, `Migration`, `Migration`, `Migration` (+128 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 876 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **43 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `CustomUser` connect `Custom User Model` to `Checkout Views Tests`, `Core Mixins & Services`, `Payment Gateways`, `Affiliate & Checkout Models`, `Role Separation Tests`, `Affiliate Middleware Tests`, `Services Maintenance`, `Accounts & Affiliate Services`, `Asaas Charge Tests`, `Services Idempotency Tests`, `Services Views Tests`, `Home Page Tests`, `Asaas Checkout Tests`, `Payments Views Tests`, `Accounts Admin`, `Social Signup Complete Tests`, `Accounts Forms`, `Provider Services`, `Payments Admin & Transactions`, `Portfolio Admin & Forms`, `Social Signup Middleware`, `Services Admin`, `Core Context Processors`, `Services Flow Tests`, `Portfolio Views Tests`, `Profile Tests`, `Social Account Adapters`, `Profile PII Tests`, `User Profile Creation`, `Payment Orchestration`, `Social Login Integration`, `Social Signup Form`, `Social Adapter Tests`, `Social Signup Flow Tests`, `Signup Form Validation`, `Core View Mixins`, `Service Quote Forms`, `Provider Approval Tests`, `Referral Dashboard`, `Affiliate Referral Middleware`, `Affiliate View Base`, `Service Forms`, `Accounts App Config`?**
  _High betweenness centrality (0.169) - this node is a cross-community bridge._
- **Why does `make_user()` connect `Role Separation Tests` to `Checkout Views Tests`, `Affiliate & Checkout Models`, `Affiliate Middleware Tests`, `Services Maintenance`, `Accounts & Affiliate Services`, `Asaas Charge Tests`, `Services Idempotency Tests`, `Services Views Tests`, `Home Page Tests`, `Asaas Checkout Tests`, `Affiliate Referral Integration`, `Payments Config & Checks`, `Payments Views Tests`, `Accounts Admin`, `Payments Admin & Transactions`, `Custom User Model`, `Service Request Integration`, `Shop Checkout Integration`, `Subscription Integration`, `Services Flow Tests`, `Portfolio Views Tests`, `Profile Tests`, `Profile PII Tests`, `Payment Orchestration`, `Social Login Integration`, `Payment Confirmation Tests`, `Referral Service Tests`, `Service Quote Forms`, `Email Login Tests`, `Payment Integration Tests`, `Hosted Checkout Gateway Tests`?**
  _High betweenness centrality (0.119) - this node is a cross-community bridge._
- **Why does `AsaasGateway` connect `Asaas Charge Tests` to `Checkout Views Tests`, `Payment Gateways`, `Affiliate & Checkout Models`, `Role Separation Tests`, `Services Maintenance`, `Accounts & Affiliate Services`, `Asaas Checkout Tests`, `Affiliate Referral Integration`, `Payments Config & Checks`, `Payments Admin & Transactions`, `Asaas Gateway Core`, `Services Admin`, `Service Request Integration`, `Shop Checkout Integration`, `Subscription Integration`, `Services Flow Tests`, `Asaas API Client`, `Asaas Webhook Handlers`, `Referral Dashboard`, `Affiliate Referral Middleware`, `Payment Integration Tests`, `Sync Payments Command`, `Hosted Checkout Gateway Tests`, `Asaas Subscription Linking`?**
  _High betweenness centrality (0.079) - this node is a cross-community bridge._
- **Are the 13 inferred relationships involving `AsaasGateway` (e.g. with `TestPaymentLinkReferral` and `AffiliateProfile`) actually correct?**
  _`AsaasGateway` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 78 inferred relationships involving `CustomUser` (e.g. with `AccountsConfig` and `CustomSignupForm`) actually correct?**
  _`CustomUser` has 78 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `create_order()` (e.g. with `Referral` and `Order`) actually correct?**
  _`create_order()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 47 inferred relationships involving `Order` (e.g. with `TestApproveReferral` and `TestServiceOrderReferral`) actually correct?**
  _`Order` has 47 INFERRED edges - model-reasoned connections that need verification._