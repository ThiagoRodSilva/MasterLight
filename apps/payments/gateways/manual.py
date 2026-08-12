"""Gateway manual (dev): transação pendente sem cobrança real."""

import json
import uuid

from django.conf import settings
from django.urls import reverse_lazy

from .base import ChargeResult, PaymentGateway, PaymentLinkResult, WebhookAuthError


class ManualGateway(PaymentGateway):
    """Gateway testes: marca transacao como pendente sem cobrar fato.

    webhook recebe payload JSON com `transaction_id` e `status` (paid/refunded)
    para simular confirmacao manual de pagamento.
    """

    name = "manual"

    def charge(
        self,
        order,
        billing_type: str = "PIX",
        credit_card_token: str = "",
        remote_ip: str = "",
    ) -> ChargeResult:
        from apps.payments.models import Transaction

        tx = Transaction.objects.create(
            order=order,
            user=order.user,
            provider=self.name,
            amount=order.total,
            status=Transaction.Status.PENDING,
        )
        return ChargeResult(
            ok=True,
            redirect_url=str(
                reverse_lazy("payments-manual-confirm", kwargs={"order_pk": order.pk})
            ),
            external_id=str(tx.pk),
            message="Pedido criado. Pagamento manual em análise.",
        )

    def subscribe(
        self,
        plan,
        billing_type: str = "PIX",
        credit_card_token: str = "",
        remote_ip: str = "",
    ) -> ChargeResult:
        from apps.payments.models import Transaction

        tx = Transaction.objects.create(
            order=plan.order,
            user=plan.client,
            provider=self.name,
            amount=plan.value,
            status=Transaction.Status.PENDING,
        )
        return ChargeResult(
            ok=True,
            redirect_url=str(
                reverse_lazy("payments-manual-confirm", kwargs={"order_pk": plan.order.pk})
            ),
            external_id=str(tx.pk),
            message="Assinatura criada. Pagamento manual em análise.",
        )

    def tokenize_credit_card(self, user, card: dict, holder: dict, remote_ip: str = "") -> str:
        raise ValueError("Cartão de crédito requer o provider 'asaas'.")

    def create_payment_link(
        self,
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
        raise ValueError("Link de pagamento requer o provider 'asaas'.")

    def refund(self, transaction_id, amount) -> ChargeResult:
        from apps.payments.models import Transaction

        tx = Transaction.objects.filter(pk=transaction_id).first()
        if tx:
            tx.status = Transaction.Status.REFUNDED
            tx.save(update_fields=["status", "updated_at"])
            return ChargeResult(ok=True, redirect_url="/", external_id=str(tx.pk))
        return ChargeResult(ok=False, redirect_url="/", message="Tx não encontrada.")

    def webhook(self, payload, headers) -> ChargeResult:
        from apps.payments.models import Transaction

        token = str(headers.get("x-webhook-token") or "")
        if not settings.MANUAL_WEBHOOK_TOKEN:
            raise WebhookAuthError(
                "MANUAL_WEBHOOK_TOKEN não configurada (webhook manual desabilitado)."
            )
        if token != settings.MANUAL_WEBHOOK_TOKEN:
            raise WebhookAuthError("Assinatura de webhook manual inválida.")

        if isinstance(payload, (bytes, bytearray)):
            try:
                payload_str = payload.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("Payload deve estar em UTF-8.") from exc
        else:
            payload_str = payload or ""

        try:
            data = json.loads(payload_str or "{}")
        except (ValueError, TypeError) as exc:
            raise ValueError("Payload inválido: não é JSON válido.") from exc

        if not isinstance(data, dict):
            raise ValueError("Payload deve ser um objeto JSON.")

        transaction_id = data.get("transaction_id")
        status = (data.get("status") or "").lower()
        if not transaction_id or not status:
            raise ValueError("Payload deve conter 'transaction_id' e 'status'.")
        try:
            transaction_id = str(uuid.UUID(str(transaction_id)))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"transaction_id '{transaction_id}' não é um UUID válido.") from exc

        tx = Transaction.objects.filter(pk=transaction_id).first()
        if tx is None:
            raise ValueError(f"Transação {transaction_id} não encontrada.")

        try:
            tx.status = Transaction.Status(status)
        except ValueError as exc:
            raise ValueError(f"Status '{status}' inválido.") from exc

        tx.raw_payload = payload_str
        tx.save(update_fields=["status", "raw_payload", "updated_at"])

        return ChargeResult(
            ok=True,
            redirect_url="/",
            external_id=str(tx.pk),
            message=f"Transação atualizada para {tx.status}.",
            status=tx.status,
            raw_payload=payload_str,
        )
