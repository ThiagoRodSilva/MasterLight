#!/usr/bin/env bash
#
# Bootstrap de producao da MasterLight - roda no servidor Hostinger (SSH),
# dentro da raiz do app (~/prot_02), DEPOIS de:
#   1) o app Python estar registrado no hPanel (passenger_wsgi.py, Python 3.12)
#   2) o .env estar presente (cp deploy/.env.prod -> .env; chmod 600 .env)
#
# Uso:
#   ./deploy/setup_prod.sh [CAMINHO_DO_VENV_DO_HPANEL]
# Ex.: ./deploy/setup_prod.sh ~/virtualenv/prot_02/3.12
#
# Opcoes para criar o superuser nao-interativamente:
#   SUPERUSER_EMAIL=admin@masterlightoficial.com.br SUPERUSER_PASSWORD='...' ./deploy/setup_prod.sh
#
set -euo pipefail

VENV_PATH="${1:-$HOME/virtualenv/prot_02/3.12}"

if [ ! -f "$VENV_PATH/bin/activate" ]; then
  echo "ERRO: venv nao encontrado em $VENV_PATH" >&2
  echo "Ajuste o caminho conforme o comando exibido no hPanel (Python)." >&2
  exit 1
fi

echo "==> Ativando venv do hPanel: $VENV_PATH"
# shellcheck disable=SC1091
source "$VENV_PATH/bin/activate"

echo "==> Instalando dependencias (requirements-prod.txt, sem dev-tools)"
python -m pip install --upgrade pip
pip install -r requirements-prod.txt

export DJANGO_SETTINGS_MODULE=config.settings.prod

echo "==> Migrations no MySQL"
python manage.py migrate

if [ -n "${SUPERUSER_EMAIL:-}" ] && [ -n "${SUPERUSER_PASSWORD:-}" ]; then
  echo "==> Criando superuser ($SUPERUSER_EMAIL)"
  DJANGO_SUPERUSER_EMAIL="$SUPERUSER_EMAIL" \
  DJANGO_SUPERUSER_PASSWORD="$SUPERUSER_PASSWORD" \
    python manage.py createsuperuser --noinput
fi

echo "==> SocialApp (Google/Facebook) + Site (dominio)"
python manage.py bootstrap_social

echo "==> Collectstatic (whitenoise)"
python manage.py collectstatic --noinput

echo "==> Reiniciando Passenger"
mkdir -p tmp
touch tmp/restart.txt

echo ""
echo "Deploy concluido. Teste em https://masterlightoficial.com.br"