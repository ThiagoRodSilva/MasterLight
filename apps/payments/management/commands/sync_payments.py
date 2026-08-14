"""Sincroniza o status de transações Asaas pendentes com a API.

Útil para reconciliação quando um webhook não foi entregue (falha de rede,
Asaas fora do ar, etc.). Consulta `GET /payments/{external_id}` para cada
transação pendente e atualiza o status local quando diverge.
"""

import json

from django.core.management.base import BaseCommand

from apps.payments.gateways.base import can_transition
from apps.payments.models import Transaction
from apps.payments.services import AsaasGateway

_ASAAS_TO_LOCAL = {
    "confirmed": Transaction.Status.PAID,
    "received": Transaction.Status.PAID,
    "dunning_received": Transaction.Status.PAID,
    "authorized": Transaction.Status.AUTHORIZED,
    "approved_by_risk_analysis": Transaction.Status.AUTHORIZED,
    "pending": Transaction.Status.PENDING,
    "pending_confirmation": Transaction.Status.PENDING,
    "awaiting_risk_analysis": Transaction.Status.PENDING,
    "dunning_requested": Transaction.Status.PENDING,
    "refund_in_progress": Transaction.Status.REFUNDED,
    "partially_refunded": Transaction.Status.REFUNDED,
    "refunded": Transaction.Status.REFUNDED,
    "failed": Transaction.Status.FAILED,
    "overdue": Transaction.Status.FAILED,
    "cancelled": Transaction.Status.FAILED,
    "customer_requested_cancellation": Transaction.Status.FAILED,
    "reproved_by_risk_analysis": Transaction.Status.FAILED,
    "chargeback_requested": Transaction.Status.FAILED,
    "chargeback_dispute": Transaction.Status.FAILED,
    "awaiting_chargeback_reversal": Transaction.Status.FAILED,
    "expired": Transaction.Status.FAILED,
    "bank_slip_cancelled": Transaction.Status.FAILED,
    "deleted": Transaction.Status.FAILED,
    "refund_denied": Transaction.Status.PENDING,
}


class Command(BaseCommand):
    help = "Reconcilia transações Asaas pendentes com o status real da API."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50, help="Máximo de transações por execução.")

    def handle(self, *args, **options):
        gateway = AsaasGateway()
        # Transações de Checkout hosted têm `kind=checkout` (`external_id` = id do
        # checkout, não um payment); são reconciliadas pelo webhook CHECKOUT_*.
        qs = (
            Transaction.objects.filter(
                provider="asaas",
                status=Transaction.Status.PENDING,
                kind=Transaction.Kind.PAYMENT,
                external_id__gt="",
            )
            .order_by("-created_at")[: options["limit"]]
        )

        updated = 0
        for tx in qs:
            self.stdout.write(f"Consultando {tx.external_id} ({tx.pk})...")
            try:
                data = gateway.fetch_payment(tx.external_id)
            except ValueError as exc:
                self.stderr.write(f"  falha: {exc}")
                continue
            asaas_status = str(data.get("status") or "").lower()
            new_status = _ASAAS_TO_LOCAL.get(asaas_status)
            if new_status is None:
                self.stdout.write(f"  status '{asaas_status}' não mapeado.")
                continue
            if new_status == tx.status:
                continue
            if not can_transition(tx.status, new_status):
                # Reconciliação não pode reverter uma transação terminal
                # (ex.: status da API diz PENDING para tx já PAID/REFUNDED).
                self.stdout.write(
                    self.style.WARNING(f"  transição {tx.status} -> {new_status} bloqueada.")
                )
                continue
            tx.status = new_status
            tx.raw_payload = json.dumps(data)
            tx.save(update_fields=["status", "raw_payload", "updated_at"])
            updated += 1
            self.stdout.write(self.style.WARNING(f"  {tx.external_id} -> {new_status}"))
        self.stdout.write(self.style.SUCCESS(f"{updated} transações atualizadas."))
