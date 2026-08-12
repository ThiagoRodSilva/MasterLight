"""Interface abstrata de gateway de pagamento e resultados tipados."""

from dataclasses import dataclass
from typing import Optional


class WebhookAuthError(ValueError):
    """Erro de autenticação de webhook (token ausente/inválido)."""


@dataclass
class ChargeResult:
    ok: bool
    redirect_url: str
    external_id: str = ""
    message: str = ""
    raw_payload: str = ""
    status: Optional[str] = None
    subscription_id: str = ""


@dataclass
class PaymentLinkResult:
    ok: bool
    url: str
    link_id: str = ""
    message: str = ""


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
        due_date_limit_days: Optional[int] = None,
        max_installment_count: Optional[int] = None,
        subscription_cycle: str = "",
        end_date=None,
        external_reference: str = "",
    ) -> PaymentLinkResult:
        """Gera um link de pagamento avulso (sem customer) no provedor."""
        raise NotImplementedError

    def refund(self, transaction_id, amount) -> ChargeResult:  # pragma: no cover
        raise NotImplementedError

    def webhook(self, payload, headers) -> ChargeResult:  # pragma: no cover
        raise NotImplementedError
