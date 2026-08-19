"""Checkout hospedado (Asaas)."""

from django.conf import settings
from django.contrib import messages
from django.urls import reverse

from apps.payments.gateways import CheckoutResult, get_gateway

from .charge import _cancel_order_if_pending, charge_with_rollback


def create_checkout_for_order(
    order,
    request,
    *,
    billing_types: list[str] | None = None,
    charge_type: str = "DETACHED",
    cycle: str = "",
    next_due_date=None,
) -> CheckoutResult:
    """Cria uma sessão de Checkout hosted para a Order no gateway configurado.

    Monta as URLs de callback absolutas a partir do request e delega ao
    gateway (`create_checkout`), que grava a `Transaction` vinculada ao
    checkout. Providers sem Checkout levantam `ValueError`.
    """
    base = request.build_absolute_uri
    callback_urls = {
        "successUrl": base(
            reverse("payments-checkout-callback", kwargs={"order_pk": order.pk, "outcome": "success"})
        ),
        "cancelUrl": base(
            reverse("payments-checkout-callback", kwargs={"order_pk": order.pk, "outcome": "cancel"})
        ),
        "expiredUrl": base(
            reverse("payments-checkout-callback", kwargs={"order_pk": order.pk, "outcome": "expired"})
        ),
    }
    return get_gateway().create_checkout(
        order,
        billing_types=billing_types,
        charge_type=charge_type,
        callback_urls=callback_urls,
        cycle=cycle,
        next_due_date=next_due_date,
    )


def checkout_or_charge(
    order,
    request,
    *,
    address=None,
    billing_types: list[str] | None = None,
    charge_type: str = "DETACHED",
    cycle: str = "",
    next_due_date=None,
    fail_message: str = "Falha ao gerar cobrança.",
) -> dict | None:
    """Dispara Checkout hosted (asaas) ou cobrança embutida (demais providers).

    Usa Checkout hosted quando `PAYMENT_PROVIDER == "asaas"`; caso contrário
    cai no fluxo embutido (`charge_with_rollback`). Em qualquer falha, cancela
    a Order apenas se estiver pendente (OPEN/AWAITING_PAYMENT), registra
    `messages.error` e retorna `None`. Em sucesso, retorna um dict com a URL
    de redirecionamento: `{"url": <hosted>}` ou `{"redirect_url": <embutido>}`.
    """
    if getattr(settings, "PAYMENT_PROVIDER", "manual") == "asaas":
        try:
            result = create_checkout_for_order(
                order,
                request,
                billing_types=billing_types,
                charge_type=charge_type,
                cycle=cycle,
                next_due_date=next_due_date,
            )
        except ValueError as exc:
            _cancel_order_if_pending(order)
            messages.error(request, str(exc) or fail_message)
            return None
        if not result.ok or not result.url:
            _cancel_order_if_pending(order)
            messages.error(request, result.message or fail_message)
            return None
        return {"url": result.url}

    result = charge_with_rollback(order, request, address=address, fail_message=fail_message)
    if result is None:
        return None
    return {"redirect_url": result.redirect_url}
