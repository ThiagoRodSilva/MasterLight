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
1. Crie o banco MySQL (`Sites → masterlightoficial.com → Databases`) e monte `DATABASE_URL=mysql://usuario:senha@host:3306/nome_do_banco`.
2. Registre o app Python (`Advanced → Python` / sessão "Python"): Python 3.12, **Application root** = `~/prot_02` (fora de `public_html`), **startup file** = `passenger_wsgi.py`, **entry point** = `application`. Anote o comando de ativação do virtualenv que o painel exibe.
3. Habilite o SSL (Let's Encrypt) para o domínio e o `www`.

No servidor (SSH):
```bash
cd ~/prot_02
cp deploy/.env.prod .env && chmod 600 .env   # preencha SECRET_KEY, Asaas, social e SMTP
./deploy/setup_prod.sh ~/virtualenv/prot_02/3.12   # caminho do venv que o hPanel exibe
# (ou rode `bash deploy/setup_prod.sh` apontando o venv correto)
```
O `deploy/setup_prod.sh` instala deps, roda `migrate`, `bootstrap_social`, `collectstatic`
e reinicia o Passenger. Para superuser não-interativo, defina `SUPERUSER_EMAIL`/`SUPERUSER_PASSWORD`
como variáveis de ambiente antes de executar.
Variáveis necessárias no `.env` de produção: `DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_SECRET_KEY`, `DATABASE_URL`, `PAYMENT_PROVIDER`, `ASAAS_API_KEY`, `ASAAS_SANDBOX=False`, `ASAAS_WEBHOOK_TOKEN`, credenciais Google/Facebook/Apple e SMTP. O Apple gera o client secret JWT a partir de `APPLE_CLIENT_ID`/`APPLE_KEY_ID`/`APPLE_TEAM_ID`/`APPLE_PRIVATE_KEY`.

Estáticos vão via whitenoise (`collectstatic`); **media** é servido pelo próprio Django (`DJANGO_SERVE_MEDIA=True`, default) pois o shared não expõe alias para `MEDIA_ROOT`.

## Próximos passos
- Asaas Checkout hosted (página de pagamento do Asaas) como alternativa ao checkout embutido.
- Parcelamento (installments) e boleto no cartão.
- Expansão de testes de cobertura >=70% no CI (hoje em 92%).

---
 Projeto baseado no plano de `PLANO.md`.
