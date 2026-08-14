"""Helpers de leitura de env vars que o django-environ processa de forma
indesejada.

O django-environ trata qualquer valor que comece com '$' como referencia a
outra env var (proxy) e o substitui por string vazia quando ela nao existe.
A chave do Asaas comeca com '$aact_...' e seria zerada em ambientes onde e
injetada crua (Vercel). Estas funcoes leem direto do os.environ e aceitam
tanto a chave crua quanto a forma escapada legada ('\\$').
"""

import os


def asaas_api_key() -> str:
    """Le ASAAS_API_KEY crua, normalizando a forma escapada legada."""
    raw = os.getenv("ASAAS_API_KEY") or ""
    return raw.replace(r"\$", "$")
