"""Tasks assíncronas para o app affiliate."""

from decimal import Decimal

from django.conf import settings


def execute_payout_async(payout_request_id):
    """Executa payout de forma assíncrona (preparado para Celery/RQ).

    Em produção, esta função seria decorada com @shared_task (Celery)
    ou @job (RQ/Django-Q). Por enquanto, executa síncrono.
    """
    from apps.affiliate.models import PayoutRequest

    try:
        payout = PayoutRequest.objects.get(pk=payout_request_id)
    except PayoutRequest.DoesNotExist:
        return {"status": "error", "message": "Payout não encontrado"}

    if payout.status != PayoutRequest.Status.PENDING:
        return {"status": "skipped", "message": "Payout não está pendente"}

    # Verifica se auto-payout está habilitado e valor atinge mínimo
    if getattr(settings, "AFFILIATE_AUTO_PAYOUT", True) and payout.amount >= Decimal(
        str(getattr(settings, "AFFILIATE_AUTO_PAYOUT_MIN_AMOUNT", "10.00"))
    ):
        # TODO: Integração real com API bancária (Pix)
        # Exemplo:
        # from apps.affiliate.services import execute_pix_payout
        # result = execute_pix_payout(payout.affiliate.pix_key, payout.amount)
        # if result.success:
        #     payout.status = PayoutRequest.Status.PAID
        #     payout.paid_at = timezone.now()
        #     payout.save(update_fields=["status", "paid_at", "updated_at"])
        #     return {"status": "success", "message": "Payout executado"}

        # Por enquanto, marca como pago (simulação)
        from django.utils import timezone

        payout.status = PayoutRequest.Status.PAID
        payout.paid_at = timezone.now()
        payout.save(update_fields=["status", "paid_at", "updated_at"])
        return {"status": "success", "message": "Payout executado (simulado)"}

    return {
        "status": "manual_required",
        "message": "Auto-payout desabilitado ou valor abaixo do mínimo",
    }


def process_pending_payouts():
    """Processa todos os payouts pendentes elegíveis para auto-payout.

    Pode ser chamado periodicamente via cron/Celery beat.
    """
    from apps.affiliate.models import PayoutRequest

    results = []
    pending = PayoutRequest.objects.filter(status=PayoutRequest.Status.PENDING)
    for payout in pending:
        results.append(execute_payout_async(payout.pk))
    return results
