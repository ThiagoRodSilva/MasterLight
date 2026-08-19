"""Resolução de forma de pagamento e tokenização de cartão."""

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any

from django.http import HttpRequest

if TYPE_CHECKING:
    from apps.accounts.models import CustomUser
    from apps.checkout.models import Address


@dataclass
class BillingParams:
    """Forma de pagamento resolvida a partir do POST, com dados de cartão."""

    billing_type: str
    credit_card_token: str = ""
    remote_ip: str = ""


def prepare_card_payload(
    post: dict[str, Any],
    user: "CustomUser",
    address: "Address | None" = None,
) -> tuple[dict[str, str], dict[str, str]]:
    """Valida dados de cartão do POST e monta `card`/`holder` para tokenização.

    Levanta `ValueError` com mensagem amigável se faltar CPF/endereço do titular
    (o Asaas exige `cpfCnpj`, `postalCode` e `addressNumber`) ou se a validade
    estiver no passado. O CPF é sanitizado apenas com dígitos.

    Args:
        post: Dicionário com dados do POST (ex.: request.POST).
        user: Usuário titular do cartão.
        address: Endereço do usuário para preencher dados do holder.

    Returns:
        Tupla (card_dict, holder_dict) prontos para tokenização.

    Raises:
        ValueError: Se CPF, endereço ou validade do cartão forem inválidos.
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


def resolve_billing(
    request: HttpRequest,
    user: "CustomUser",
    address: "Address | None" = None,
) -> BillingParams:
    """Resolve a forma de pagamento do POST e tokeniza o cartão se CREDIT_CARD.

    Centraliza a leitura de `payment_method` e a tokenização (que consumiam o
    mesmo código em checkout e nos fluxos de serviços). Levanta `ValueError`
    com mensagem amigável quando os dados de cartão/endereço são inválidos.

    Args:
        request: Request HTTP com POST contendo `payment_method`.
        user: Usuário que fará o pagamento.
        address: Endereço opcional; se não informado, usa o primeiro ativo do usuário.

    Returns:
        BillingParams com tipo de cobrança, token de cartão (se aplicável) e IP remoto.

    Raises:
        ValueError: Se pagamento for cartão e dados forem inválidos.
    """
    from apps.payments.gateways import get_gateway

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
