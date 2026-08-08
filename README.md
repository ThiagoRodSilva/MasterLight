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

## Deploy Hostinger (Passenger/Python)
1. `git pull` no servidor.
2. `pip install -r requirements.txt`.
3. `python manage.py migrate` e `python manage.py collectstatic --noinput`.
4. Reinicie o Passenger.
5. Variáveis de ambiente via `.env` (permissão 600).

## Próximos passos
- Tokenização de cartão de crédito no front (Asaas SDK) para checkout com cartão.
- Cadastro de chave Pix do afiliado (por ora alvo do payout via Admin).
- Expansão de testes de cobertura >=70% no CI.

---
 Projeto baseado no plano de `PLANO.md`.
