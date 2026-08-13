"""Servicos orquestracao pagamentos (camada de negocio).

Orquestra gateways (ver `apps/payments.gateways`) e conceitos financeiros:
cobranca de pedido, assinatura de plano, link de pagamento e webhook.
"""

from dataclasses import asdict, dataclass
from datetime import date

from django.contrib import messages

from .gateways import (
    AsaasGateway,
    ChargeResult,
    ManualGateway,
    PaymentGateway,
    PaymentLinkResult,
    WebhookAuthError,
    get_gateway,
)

__all__ = [
    "AsaasGateway",
    "ChargeResult",
    "ManualGateway",
    "PaymentGateway",
    "PaymentLinkResult",
    "WebhookAuthError",
    "get_gateway",
]


@dataclass
class BillingParams:
    """Forma de pagamento resolvida a partir do POST, com dados de cartão."""

    billing_type: str
    credit_card_token: str = ""
    remote_ip: str = ""


def prepare_card_payload(post, user, address=None) -> tuple[dict, dict]:
    """Valida dados de cartão do POST e monta `card`/`holder` para tokenização.

    Levanta `ValueError` com mensagem amigável se faltar CPF/endereço do titular
    (o Asaas exige `cpfCnpj`, `postalCode` e `addressNumber`) ou se a validade
    estiver no passado. O CPF é sanitizado apenas com dígitos.
    """
    cpf = "".join(ch for ch in (post.get("card_cpf") or user.cpf or "") if ch.isdigit())
    if not cpf:
        raise ValueError("Informe o CPF do titular do cartão.")
    if address is None or not (address.zip_code or "").strip() or not (address.number or "").strip():
        raise ValueError("Cadastre um endereço com CEP e número para pagar com cartão.")

    try:
        month = int(post.get("card_expiry_month") or 0)
    except (TypeError, ValueError):
        month = 0
    try:
        year = int(post.get("card_expiry_year") or 0)
    except (TypeError, ValueError):
        year = 0
    if month < 1 or month > 12:
        raise ValueError("Mês de validade do cartão inválido.")

    if date(year, month, 1) <= date.today().replace(day=1):
        raise ValueError("Cartão de crédito vencido.")

    holder = {
        "name": user.get_full_name() or user.email,
        "email": user.email,
        "cpf_cnpj": cpf,
        "phone": user.telefone,
        "postal_code": address.zip_code,
        "address_number": address.number,
    }
    card = {
        "holder_name": post.get("card_holder", ""),
        "number": post.get("card_number", ""),
        "expiry_month": f"{month:02d}",
        "expiry_year": str(year),
        "ccv": post.get("card_ccv", ""),
    }
    return card, holder


def resolve_billing(request, user, address=None) -> BillingParams:
    """Resolve a forma de pagamento do POST e tokeniza o cartão se CREDIT_CARD.

    Centraliza a leitura de `payment_method` e a tokenização (que consumiam o
    mesmo código em checkout e nos fluxos de serviços). Levanta `ValueError`
    com mensagem amigável quando os dados de cartão/endereço são inválidos.
    """
    billing_type = (request.POST.get("payment_method") or "PIX").upper()
    remote_ip = request.META.get("REMOTE_ADDR", "")
    if billing_type != "CREDIT_CARD":
        return BillingParams(billing_type=billing_type, remote_ip=remote_ip)
    if address is None:
        address = user.addresses.filter(is_active=True).first()
    card, holder = prepare_card_payload(request.POST, user, address)
    credit_card_token = get_gateway().tokenize_credit_card(
        user, card, holder, remote_ip=remote_ip
    )
    return BillingParams(
        billing_type=billing_type,
        credit_card_token=credit_card_token,
        remote_ip=remote_ip,
    )


def charge_with_rollback(
    order,
    request,
    *,
    address=None,
    fail_message: str = "Falha ao gerar cobrança.",
) -> ChargeResult | None:
    """Dispara a cobrança de uma Order, cancelando-a em qualquer falha.

    Unifica o fluxo cartão/tokenize + `charge_order` + cancelamento que estava
    duplicado entre checkout e aprovação de orçamento. Em falha (`ValueError`
    ou `ok=False`), cancela a Order, registra `messages.error` e retorna
    `None`; a view faz apenas o redirect. Em sucesso, retorna o `ChargeResult`.
    """
    from apps.checkout.models import Order

    try:
        params = resolve_billing(request, order.user, address=address)
        result = charge_order(
            order,
            billing_type=params.billing_type,
            credit_card_token=params.credit_card_token,
            remote_ip=params.remote_ip,
        )
    except ValueError as exc:
        order.status = Order.Status.CANCELED
        order.save(update_fields=["status", "updated_at"])
        messages.error(request, str(exc) or fail_message)
        return None

    if not result.ok:
        order.status = Order.Status.CANCELED
        order.save(update_fields=["status", "updated_at"])
        messages.error(request, result.message or fail_message)
        return None
    return result


def charge_order(
    order,
    billing_type: str = "PIX",
    credit_card_token: str = "",
    remote_ip: str = "",
) -> ChargeResult:
    """Cria transacao inicial e chama gateway configurado."""
    from .models import Transaction

    result = get_gateway().charge(
        order,
        billing_type=billing_type,
        credit_card_token=credit_card_token,
        remote_ip=remote_ip,
    )
    if result.external_id:
        tx = Transaction.objects.filter(pk=result.external_id).first()
        if tx:
            if not result.ok:
                tx.status = Transaction.Status.FAILED
            else:
                # Mantém o status informado pelo gateway (ex.: PENDING no Pix),
                # preservando a semântica: cobrança criada ≠ pagamento confirmado.
                tx.status = result.status or tx.status
            tx.raw_payload = result.raw_payload
            tx.save(update_fields=["status", "raw_payload", "updated_at"])
    return result


def subscribe_plan(
    plan,
    billing_type: str = "PIX",
    credit_card_token: str = "",
    remote_ip: str = "",
) -> ChargeResult:
    """Cria transacao de assinatura e chama gateway configurado."""
    return get_gateway().subscribe(
        plan,
        billing_type=billing_type,
        credit_card_token=credit_card_token,
        remote_ip=remote_ip,
    )


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


def webhook_handler(payload, headers) -> dict:
    """Processa webhook generico e retorna dicionario serializavel."""
    result = get_gateway().webhook(payload, headers)
    return asdict(result)
