"""Sincroniza o status de transações Asaas pendentes com a API.

Útil para reconciliação quando um webhook não foi entregue (falha de rede,
Asaas fora do ar, etc.). Consulta `GET /payments/{external_id}` para cada
transação pendente e atualiza o status local quando diverge.
"""

import json

from django.core.management.base import BaseCommand

from apps.payments.models import Transaction
from apps.payments.services import AsaasGateway

_ASAAS_TO_LOCAL = {
    "confirmed": Transaction.Status.PAID,
    "received": Transaction.Status.PAID,
    "dunning_received": Transaction.Status.PAID,
    "authorized": Transaction.Status.AUTHORIZED,
    "failed": Transaction.Status.FAILED,
    "overdue": Transaction.Status.FAILED,
    "cancelled": Transaction.Status.FAILED,
    "deleted": Transaction.Status.FAILED,
    "refunded": Transaction.Status.REFUNDED,
}


class Command(BaseCommand):
    help = "Reconcilia transações Asaas pendentes com o status real da API."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50, help="Máximo de transações por execução.")

    def handle(self, *args, **options):
        gateway = AsaasGateway()
        qs = Transaction.objects.filter(
            provider="asaas", status=Transaction.Status.PENDING, external_id__gt=""
        ).order_by("-created_at")[: options["limit"]]

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
            tx.status = new_status
            tx.raw_payload = json.dumps(data)
            tx.save(update_fields=["status", "raw_payload", "updated_at"])
            updated += 1
            self.stdout.write(self.style.WARNING(f"  {tx.external_id} -> {new_status}"))
        self.stdout.write(self.style.SUCCESS(f"{updated} transações atualizadas."))
