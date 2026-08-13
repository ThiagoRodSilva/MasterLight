#!/usr/bin/env bash
# Sobe uploads atuais (media/) para o bucket publico do Cloudflare R2,
# preservando os caminhos relativos (products/, services/, portfolio/,
# avatars/) para que os registros existentes no DB renderizem via image.url.
#
# Pre-requisito: aws cli com profile r2 configurado:
#   aws configure --profile r2   # Access Key ID / Secret da R2
#   aws configure --profile r2 set region auto
#
# Uso:
#   ./deploy/migrate_media_to_r2.sh <BUCKET_NAME> <R2_ENDPOINT_URL>
# Ex.: ./deploy/migrate_media_to_r2.sh masterlight-media https://<accountid>.r2.cloudflarestorage.com
set -euo pipefail

R2_BUCKET="${1:?Uso: migrate_media_to_r2.sh <BUCKET> <ENDPOINT_URL>}"
R2_ENDPOINT_URL="${2:?Uso: migrate_media_to_r2.sh <BUCKET> <ENDPOINT_URL>}"

aws --profile r2 --endpoint-url "$R2_ENDPOINT_URL" s3 sync ./media "s3://$R2_BUCKET" --region auto

echo "Media sincronizada para s3://$R2_BUCKET. Confira no painel R2 / URL publica."