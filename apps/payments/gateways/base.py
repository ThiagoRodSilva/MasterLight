"""Interface abstrata de gateway de pagamento e resultados tipados."""

from dataclasses import dataclass


class WebhookAuthError(ValueError):
    """Erro de autenticação de webhook (token ausente/inválido)."""


@dataclass
class ChargeResult:
    ok: bool
    redirect_url: str
    external_id: str = ""
    message: str = ""
    raw_payload: str = ""
    status: str | None = None
    subscription_id: str = ""


@dataclass
class PaymentLinkResult:
    ok: bool
    url: str
    link_id: str = ""
    message: str = ""


@dataclass
class CheckoutResult:
    ok: bool
    url: str
    checkout_id: str = ""
    message: str = ""
    redirect_url: str = ""


class PaymentGateway:
    """Interface abstrata gateway pagamento.

    Cada provedor concreto (Asaas, Mercado Pago, Stripe, etc.) deve herdar
    desta classe e implementar `charge`, `refund` e `webhook`.
    """

    name: str = "base"

    def charge(
        self,
        order,
        billing_type: str = "PIX",
        credit_card_token: str = "",
        remote_ip: str = "",
    ) -> ChargeResult:
        raise NotImplementedError

    def subscribe(
        self,
        plan,
        billing_type: str = "PIX",
        credit_card_token: str = "",
        remote_ip: str = "",
    ) -> ChargeResult:
        """Cria assinatura recorrente para um plano de manutenção."""
        raise NotImplementedError

    def tokenize_credit_card(self, user, card: dict, holder: dict, remote_ip: str = "") -> str:
        """Tokeniza cartão de crédito; apenas providers que suportam cartão."""
        raise NotImplementedError

    def create_payment_link(
        self,
        *,
        name: str,
        value=None,
        description: str = "",
        billing_type: str = "UNDEFINED",
        charge_type: str = "DETACHED",
        due_date_limit_days: int | None = None,
        max_installment_count: int | None = None,
        subscription_cycle: str = "",
        end_date=None,
        external_reference: str = "",
    ) -> PaymentLinkResult:
        """Gera um link de pagamento avulso (sem customer) no provedor."""
        raise NotImplementedError

    def refund(self, transaction_id, amount) -> ChargeResult:  # pragma: no cover
        raise NotImplementedError

    def create_checkout(
        self,
        order,
        *,
        billing_types: list[str] | None = None,
        charge_type: str = "DETACHED",
        callback_urls: dict | None = None,
        cycle: str = "",
        next_due_date=None,
    ) -> CheckoutResult:
        """Cria uma página de pagamento hospedada no provedor (Asaas Checkout).

        Substitui o checkout embutido: o cliente é redirecionado para `url`.
        Providers sem suporte devem levantar `NotImplementedError`/`ValueError`.
        """
        raise NotImplementedError

    def webhook(self, payload, headers) -> ChargeResult:  # pragma: no cover
        raise NotImplementedError
