# MasterLight

Plataforma web para prestação de serviços elétricos, gestão de afiliados e pagamentos digitais.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-5.0-092E20?logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?logo=postgresql&logoColor=white)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-7952B3?logo=bootstrap&logoColor=white)

## Visão geral

O MasterLight é uma plataforma construída em Django para unir:

- serviços elétricos;
- cadastro e gestão de prestadores;
- área de afiliados com indicação por link e comissões;
- checkout e pagamentos via Pix/cartão;
- autenticação com email e redes sociais;
- painel administrativo para gestão do site e operações.

A aplicação foi pensada para servir como um ecossistema completo de negócios digitais, com foco em serviços e monetização.

## Stack tecnológica

- Python 3.12
- Django 5.0
- PostgreSQL
- Bootstrap 5
- django-allauth
- django-environ
- psycopg
- Whitenoise
- Asaas API

## Estrutura do projeto

```text
MasterLight/
├── apps/
│   ├── accounts/
│   ├── affiliate/
│   ├── checkout/
│   ├── core/
│   ├── payments/
│   ├── portfolio/
│   ├── services/
│   └── tests/
├── config/
│   ├── settings/
│   ├── asgi.py
│   ├── urls.py
│   ├── wsgi.py
│   └── __init__.py
├── deploy/
├── static/
├── templates/
├── tests/
├── .env.example
├── .gitignore
├── AGENTS.md
├── build.py
├── manage.py
├── pyproject.toml
├── pytest.ini
├── requirements.txt
├── vercel.json
├── README.md
└── ...
```

## Funcionalidades principais

### Serviços
- catálogo de serviços por categoria;
- cadastro de prestadores;
- solicitações de orçamento;
- aprovação de orçamentos e geração de pedidos;
- acompanhamento do status da solicitação.

### Afiliados
- landing pública para indicação;
- código de afiliado por usuário;
- rastreio de indicações via `?ref=`;
- painel para controle de comissões;
- solicitações de saque via Pix.

### Pagamentos
- integração com Asaas;
- cobrança via Pix e cartão;
- checkout hosted;
- confirmação por webhook;
- reconciliação de transações e status.

### Autenticação e administração
- login por email e redes sociais;
- perfis de cliente, prestador, afiliado e administrador;
- painel administrativo Django;
- configurações globais do site via `SiteSettings`.

## Requisitos

Antes de iniciar, certifique-se de ter instalado:

- Python 3.12+
- PostgreSQL
- Ambiente virtual (`venv`)
- Credenciais de integração com Asaas (se for usar pagamentos)

## Configuração local

1. Clone o repositório:

```bash
git clone https://github.com/ThiagoRodSilva/MasterLight.git
cd MasterLight
```

2. Crie e ative um ambiente virtual:

```bash
python -m venv .venv
source .venv/bin/activate
```

3. Instale as dependências:

```bash
pip install -r requirements.txt
```

4. Copie o arquivo de exemplo de ambiente:

```bash
cp .env.example .env
```

Edite o arquivo `.env` com as configurações do seu ambiente, incluindo:

- `DATABASE_URL`
- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `PAYMENT_PROVIDER`
- `ASAAS_API_KEY`
- `ASAAS_WEBHOOK_TOKEN`

5. Execute as migrações:

```bash
python manage.py migrate
```

6. Caso necessário, inicialize os dados do sistema de autenticação social:

```bash
python manage.py bootstrap_social
```

7. Crie um usuário administrador:

```bash
python manage.py createsuperuser
```

8. Inicie o servidor:

```bash
python manage.py runserver
```

A aplicação estará disponível em:

```text
http://localhost:8000
```

## Variáveis de ambiente

O projeto utiliza `django-environ` para carregar configurações a partir do arquivo `.env` ou do ambiente.

Exemplo básico:

```env
DJANGO_SECRET_KEY=seu_secret_key
DJANGO_DEBUG=True
DATABASE_URL=postgresql://usuario:senha@host:5432/masterlight
PAYMENT_PROVIDER=asaas
ASAAS_API_KEY=sua_chave
ASAAS_SANDBOX=True
ASAAS_WEBHOOK_TOKEN=seu_token
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
```

## Testes

Para rodar a suíte de testes:

```bash
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test apps
```

Também é possível usar `pytest` se o ambiente estiver configurado:

```bash
pytest
```

## Deploy

O projeto inclui suporte para deploy em Vercel, com configuração em:

- `vercel.json`
- `build.py`
- `config/settings/vercel.py`

Variáveis de produção importantes:

- `DJANGO_SETTINGS_MODULE=config.settings.vercel`
- `DJANGO_SECRET_KEY`
- `DATABASE_URL`
- `ASAAS_API_KEY`
- `ASAAS_WEBHOOK_TOKEN`
- `CRON_SECRET`

## Segurança

- mantenha o arquivo `.env` fora do controle de versão;
- nunca compartilhe chaves sensíveis de produção;
- valide todos os webhooks de pagamento;
- utilize separação entre ambiente de desenvolvimento e produção.

## Contribuição

Contribuições são bem-vindas. Para colaborar:

1. faça um fork do projeto;
2. crie uma branch para sua alteração;
3. implemente a mudança e teste localmente;
4. abra um pull request com descrição clara.

## Licença

Veja na Aba Licença

## Contato

Repositório oficial:

https://github.com/ThiagoRodSilva/MasterLight
