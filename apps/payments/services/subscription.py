"""Assinaturas recorrentes."""

from apps.payments.gateways import ChargeResult, get_gateway


def subscribe_plan(
    plan,
    billing_type: str = "PIX",
    credit_card_token: str = "",
    remote_ip: str = "",
) -> ChargeResult:
    """Cria transação de assinatura e chama gateway configurado."""
    return get_gateway().subscribe(
        plan,
        billing_type=billing_type,
        credit_card_token=credit_card_token,
        remote_ip=remote_ip,
    )
