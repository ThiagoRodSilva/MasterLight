# MasterLight — Django

Plataforma de loja de produtos + serviços + programa de afiliados, com autenticação social (allauth) e pagamentos via Asaas (Pix/cartão).

## Stack
- Python 3.12 · Django 5.0 · django-allauth · django-crispy-forms (Bootstrap 5)
- DB: SQLite (dev) / MySQL (prod Hostinger) — via `DATABASE_URL`
- Pagamentos: interface `PaymentGateway` — `ManualGateway` (dev) e `AsaasGateway` (Pix/MultiCartão, prod/sandbox)
- Paleta: amarelo #FFC107 · preto #111 · branco

## Pagamentos — Asaas
1. Crie uma conta no Asaas (sandbox para testes).
2. Em `.env`, defina:
   - `PAYMENT_PROVIDER=asaas`
   - `ASAAS_API_KEY=<access_token de integração>`
   - `ASAAS_SANDBOX=True` (ou `False` em produção)
   - `ASAAS_WEBHOOK_TOKEN=<token do webhook no Asaas>`
3. No painel do Asaas, cadastre a URL do webhook: `https://SEUDOMINIO/pagamentos/webhook/`.
4. A cobrança cria um `Transaction` pendente; o webhook mapeia eventos (`PAYMENT_CONFIRMED` → pago, `PAYMENT_OVERDUE` → falha) e o signal aprova referência/credita comissão.

> Em desenvolvimento, deixe `PAYMENT_PROVIDER=manual` para simular sem API real.

## Apps
| App | Responsabilidade |
|-----|------------------|
| `apps.core` | BaseModel, mixins, utils, context processors (branding MasterLight) |
| `apps.accounts` | `CustomUser` (role), perfis, signals -> cria `AffiliateProfile` |
| `apps.portfolio` | CRUD de portfólio do prestador |
| `apps.services` | Categorias/Serviços, self-service de prestadores e solicitação de orçamento |
| `apps.shop` | Produtos, variantes, imagens, listagem/detalhe/busca |
| `apps.affiliate` | Landing pública + dashboard, `Referral`, `PayoutRequest` |
| `apps.checkout` | Carrinho (session), `Order`, `OrderItem`, `Address` |
| `apps.payments` | `Transaction`, `ManualGateway`/`AsaasGateway`, webhook |

## Fluxo afiliado (resumo)
1. Visitante chega com `?ref=CODE` -> cookie 30 dias.
2. Checkout lê cookie `ref`, cria `Referral` ligado ao afiliado.
3. Pagamento aprovado -> signal atualiza saldo e status da referência.
4. Afiliado solicita saque via painel; admin aprova/efetua.

## Fluxo de serviços
1. **Prestador (self-service)**: cria o serviço em `/servicos/meus/` e vira provider daquele serviço automaticamente.
2. **Cliente**: navega em `/servicos/`, vê o detalhe e escolhe **um prestador** ao solicitar orçamento.
3. Prestador recebe a solicitação (status `pending`) em `/servicos/solicitacoes/` e envia orçamento (`final_price`).
4. Cliente **aprova** o orçamento: o sistema cria `Order(kind=SERVICE)` + `OrderItem` e cobra via Asaas (Pix).
5. Webhook confirma o pagamento -> signal marca a `ServiceRequest` como `approved` (a Order vira `PAID`).
6. Cliente acompanha o status em `/servicos/minhas-solicitacoes/` e pode cancelar enquanto pendente.

## Desenvolvimento

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Docker (opcional):

```bash
docker compose up --build
```

## Deploy Hostinger (hospedagem compartilhada — Passenger)

Pré-requisitos no hPanel:
1. Crie o banco MySQL (`Sites → masterlightoficial.com.br → Databases`) e monte `DATABASE_URL=mysql://usuario:senha@host:3306/nome_do_banco`.
2. Registre o app Python (`Advanced → Python` / sessão "Python"): Python 3.12, **Application root** = `~/prot_02` (fora de `public_html`), **startup file** = `passenger_wsgi.py`, **entry point** = `application`. Anote o comando de ativação do virtualenv que o painel exibe.
3. Habilite o SSL (Let's Encrypt) para o domínio e o `www`.

No servidor (SSH):
```bash
cd ~/prot_02
cp deploy/.env.prod .env && chmod 600 .env   # arquivo gitignored: envie separadamente no upload
./deploy/setup_prod.sh ~/virtualenv/prot_02/3.12   # caminho do venv que o hPanel exibe
# (ou rode `bash deploy/setup_prod.sh` apontando o venv correto)
```
O `deploy/setup_prod.sh` instala deps, valida a conexão MySQL (`DATABASE_URL`), roda `migrate`, `bootstrap_social`, `collectstatic`
e reinicia o Passenger. Para superuser não-interativo, defina `SUPERUSER_EMAIL`/`SUPERUSER_PASSWORD`
como variáveis de ambiente antes de executar.

### Checklist de credenciais (preencha em `deploy/.env.prod` ANTES de rodar o setup)
1. Banco: confirmar `DATABASE_URL` no hPanel e **rotacionar a senha do MySQL** que já está em `deploy/.env.prod` (está em texto plano e o arquivo transita por máquinas).
2. Pagamentos: `PAYMENT_PROVIDER=asaas` exige `ASAAS_API_KEY` (produção) e `ASAAS_WEBHOOK_TOKEN` (cadastre a URL `https://masterlightoficial.com.br/pagamentos/webhook/` no Asaas). Sem essas chaves, **nenhuma cobrança funciona** — para colocar no ar sem pagamentos, use `PAYMENT_PROVIDER=manual`.
3. SMTP: `DJANGO_EMAIL_HOST`/`USER`/`PASSWORD`/`DEFAULT_FROM_EMAIL` — sem isso emails (reset de senha, notificações) falham silenciosamente.
4. Social login: Google/Facebook (`CLIENT_ID`/`SECRET`) e, se usar, Apple (`APPLE_CLIENT_ID`/`APPLE_KEY_ID`/`APPLE_TEAM_ID`/`APPLE_PRIVATE_KEY`). O Apple é lido das settings (não precisa de SocialApp no admin), mas exige `PyJWT` — já está em `requirements-prod.txt`.
5. `DJANGO_SECRET_KEY`: manter o valor longo gerado; se reutilizar este arquivo, gere um novo (evite exposição em histórico).

> Segurança de produção: com `SECURE_SSL_REDIRECT=True` e HSTS (1 ano), o site só responde por HTTPS — confirme o SSL do hPanel antes do primeiro acesso.

Estáticos vão via whitenoise (`collectstatic`); **media** é servido pelo próprio Django (`DJANGO_SERVE_MEDIA=True`, default) pois o shared não expõe alias para `MEDIA_ROOT`. `staticfiles/` não é versionado no git — regenerado pelo `collectstatic` no deploy.

## Deploy Vercel (serverless)

A Vercel detecta o `manage.py` e usa o entrypoint WSGI (`config/wsgi.py`, definido por `WSGI_APPLICATION`). O settings é o `config.settings.vercel` (selecionado pela env `DJANGO_SETTINGS_MODULE`). Estáticos são coletados e servidos pelo CDN da Vercel; **media** vai para o Cloudflare R2 (bucket público, S3-compatible); banco é o **Vercel Postgres** (Neon) via `DATABASE_URL`.

### Arquivos de deploy
- `config/settings/vercel.py` — settings de produção Vercel (R2, Postgres, ALLOWED_HOSTS com `.vercel.app`, `SERVE_MEDIA=False`).
- `vercel.json` — `maxDuration=60` + `excludeFiles` da function; cron de reconciliação (`/pagamentos/reconciliar`).
- `build.py` — build command: roda `migrate` + `bootstrap_social` (idempotentes) em todo deploy (configurado em `[tool.vercel.scripts]` no `pyproject.toml`).
- `deploy/migrate_to_vercel.sh` — migração única de dados MySQL → Postgres.
- `deploy/migrate_media_to_r2.sh` — migração única de `media/` → bucket R2.

### Configuração no dashboard (uma vez)
1. Importe o repositório; adicione a integração **Vercel Postgres** (injeta `DATABASE_URL`).
2. Defina as env vars (obrigatória: `DJANGO_SETTINGS_MODULE=config.settings.vercel`):
   `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS=masterlightoficial.com.br,www.masterlightoficial.com.br,.vercel.app`,
   `DJANGO_SITE_DOMAIN=masterlightoficial.com.br`, `DJANGO_SITE_NAME=MasterLight`,
   `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_ENDPOINT_URL`, `R2_PUBLIC_DOMAIN`,
   `PAYMENT_PROVIDER`, `ASAAS_API_KEY`, `ASAAS_SANDBOX=False`, `ASAAS_WEBHOOK_TOKEN`, `MANUAL_WEBHOOK_TOKEN`,
   sociais (Google/Facebook/Apple — `APPLE_PRIVATE_KEY` **inline**, nunca path), SMTP (`DJANGO_EMAIL_*`), e `CRON_SECRET` (cron).
3. Domínio: apex + `www` para a Vercel; `media` → custom domain do bucket R2.
4. No painel do Asaas, atualize o webhook para `https://masterlightoficial.com.br/pagamentos/webhook/`.
5. Suba os dados e a media (scripts acima) após o primeiro build.

> Filesystem é efêmero/read-only na Vercel: nunca grave `media/` localmente em produção; todo upload vai para o R2.

## Próximos passos
- Asaas Checkout hosted (página de pagamento do Asaas) como alternativa ao checkout embutido.
- Parcelamento (installments) e boleto no cartão.
- Expansão de testes de cobertura >=70% no CI (hoje em 92%).

---
 Projeto baseado no plano de `PLANO.md`.
