"""Processamento genérico de webhook."""

from dataclasses import asdict

from apps.payments.gateways import get_gateway


def webhook_handler(payload, headers) -> dict:
    """Processa webhook genérico e retorna dicionário serializável."""
    result = get_gateway().webhook(payload, headers)
    return asdict(result)
