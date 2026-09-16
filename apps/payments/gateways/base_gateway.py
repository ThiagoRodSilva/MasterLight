"""Gateway base com funcionalidades comuns compartilhadas."""

import logging
from typing import TYPE_CHECKING

from django.db import IntegrityError

from .base import ChargeResult, can_transition

if TYPE_CHECKING:
    from apps.accounts.models import CustomUser
    from apps.checkout.models import Order
    from apps.payments.models import Transaction

logger = logging.getLogger(__name__)


class BasePaymentGateway:
    """Classe base com utilitários comuns para gateways de pagamento.

    Extrai lógica compartilhada entre os gateways (Asaas):
    - Criação idempotente de Transaction (_upsert_transaction)
    - Lógica de reembolso com validação de transição (refund)
    - Estrutura base para autenticação de webhook
    """

    name: str = "base"

    def _upsert_transaction(
        self,
        *,
        order: "Order",
        user: "CustomUser",
        external_id: str,
        amount,
        status: str,
        raw_payload: str,
        kind: str = "payment",
    ) -> "Transaction":
        """Cria a Transaction de forma idempotente por (provider, external_id).

        Evita duplicar transações locais quando o mesmo id externo chega de novo
        (retry de webhook, idempotency do provedor, reenvio de renovação).
        A constraint parcial `uniq_payments_provider_external_id` é o fallback
        de segurança. Se já existe, apenas atualiza amount/raw_payload.
        """
        from apps.payments.models import Transaction

        if external_id:
            tx = Transaction.objects.filter(provider=self.name, external_id=external_id).first()
            if tx is not None:
                tx.amount = amount
                tx.raw_payload = raw_payload
                tx.save(update_fields=["amount", "raw_payload", "updated_at"])
                return tx
        try:
            return Transaction.objects.create(
                order=order,
                user=user,
                provider=self.name,
                external_id=external_id,
                amount=amount,
                status=status,
                kind=kind,
                raw_payload=raw_payload,
            )
        except IntegrityError:
            # Race condition: outro webhook criou a transação entre o filter e o create.
            # Busca a existente e atualiza (idempotente).
            tx = Transaction.objects.filter(provider=self.name, external_id=external_id).first()
            if tx is not None:
                tx.amount = amount
                tx.raw_payload = raw_payload
                tx.save(update_fields=["amount", "raw_payload", "updated_at"])
                return tx
            # Se ainda não existe (improvável), re-levanta.
            raise

    def _process_refund(
        self,
        transaction_id: str,
        amount,
        expected_new_status: str = "refunded",
    ) -> ChargeResult:
        """Processa reembolso comum com validação de transição de status."""
        from apps.payments.models import Transaction

        tx = Transaction.objects.filter(pk=transaction_id).first()
        if tx is None:
            return ChargeResult(ok=False, redirect_url="/", message="Tx não encontrada.")

        if not can_transition(tx.status, expected_new_status):
            return ChargeResult(
                ok=False,
                redirect_url="/",
                transaction_id=str(tx.pk),
                message=f"Transição '{tx.status} -> {expected_new_status}' bloqueada.",
            )

        tx.status = expected_new_status
        tx.save(update_fields=["status", "updated_at"])
        return ChargeResult(
            ok=True,
            redirect_url="/",
            transaction_id=str(tx.pk),
            message=f"Transação atualizada para {tx.status}.",
            status=tx.status,
        )

    def _validate_webhook_auth(self, headers: dict, expected_token: str) -> str:
        """Valida token de webhook; levanta WebhookAuthError se inválido."""
        token = str(headers.get("asaas-access-token") or headers.get("x-webhook-token") or "")
        if not expected_token:
            from .base import WebhookAuthError

            raise WebhookAuthError(
                f"Webhook token não configurado para provider '{self.name}' (webhook desabilitado)."
            )
        if token != expected_token:
            from .base import WebhookAuthError

            raise WebhookAuthError("Assinatura de webhook inválida.")
        return token

    def _parse_webhook_payload(self, payload: bytes | str) -> dict:
        """Parseia payload de webhook (bytes/str) para dict; levanta ValueError se inválido."""
        import json

        if isinstance(payload, bytes | bytearray):
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

        return data
