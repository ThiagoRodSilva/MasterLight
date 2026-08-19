"""Links de pagamento avulsos."""

from apps.payments.gateways import PaymentLinkResult, get_gateway


def create_payment_link(
    *,
    name: str,
    value=None,
    description: str = "",
    billing_type: str = "UNDEFINED",
    charge_type: str = "DETACHED",
    due_date_limit_days=None,
    max_installment_count=None,
    subscription_cycle: str = "",
    end_date=None,
    external_reference: str = "",
) -> PaymentLinkResult:
    """Gera um link de pagamento avulso no gateway configurado."""
    return get_gateway().create_payment_link(
        name=name,
        value=value,
        description=description,
        billing_type=billing_type,
        charge_type=charge_type,
        due_date_limit_days=due_date_limit_days,
        max_installment_count=max_installment_count,
        subscription_cycle=subscription_cycle,
        end_date=end_date,
        external_reference=external_reference,
    )
