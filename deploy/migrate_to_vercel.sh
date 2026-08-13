#!/usr/bin/env bash
# Migra dados do MySQL (Hostinger) para o Postgres da Vercel.
#
# Pre-requisito: o .env local deve ser o de PRODUCAO da Hostinger
# (cp deploy/.env.prod .env), com DATABASE_URL apontando para o MySQL.
# A URL do Postgres entra por env var e vence o .env (django-environ usa
# overwrite=False).
#
# Uso:
#   POSTGRES_URL='postgres://user:pass@host:5432/db?sslmode=require' ./deploy/migrate_to_vercel.sh
set -euo pipefail

POSTGRES_URL="${1:-${POSTGRES_URL:-}}"
if [ -z "$POSTGRES_URL" ]; then
  echo "ERRO: passe a URL do Postgres (arg 1 ou env POSTGRES_URL)." >&2
  exit 1
fi

DUMP=/tmp/masterlight_dump.json

echo "==> Dump do MySQL (source)"
DJANGO_SETTINGS_MODULE=config.settings.prod python manage.py dumpdata \
  --natural-primary --natural-foreign \
  --exclude=contenttypes --exclude=auth.permission \
  --exclude=admin.logentry --exclude=sessions \
  --indent 2 --output "$DUMP"

echo "==> Load no Postgres Vercel (target)"
DJANGO_SETTINGS_MODULE=config.settings.vercel DATABASE_URL="$POSTGRES_URL" \
  python manage.py loaddata "$DUMP"

echo "==> Conferencia rapida (contagem por modelo)"
DJANGO_SETTINGS_MODULE=config.settings.vercel DATABASE_URL="$POSTGRES_URL" \
  python manage.py shell -c "
from django.apps import apps
for model in apps.get_models():
    print(f'{model._meta.label}: {model.objects.count()}')
"
echo "Migracao concluida."