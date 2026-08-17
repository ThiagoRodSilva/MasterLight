"""Signals services: conclui a solicitacao quando o pedido e pago."""

from datetime import datetime, timedelta

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.checkout.models import Order


@receiver(post_save, sender=Order)
def complete_service_request_on_paid(sender, instance, **kwargs):
    """Quando o Order de um servico e PAGO, aprova a solicitacao ligada."""
    if instance.status != Order.Status.PAID:
        return
    service_request = getattr(instance, "service_request", None)
    if service_request is None:
        return
    from .models import ServiceRequest

    if service_request.status != ServiceRequest.Status.QUOTED:
        return
    service_request.status = ServiceRequest.Status.APPROVED
    service_request.save(update_fields=["status", "updated_at"])


@receiver(post_save, sender="payments.Transaction")
def schedule_first_maintenance_visit(sender, instance, **kwargs):
    """Quando a Transaction de assinatura e PAGA, agenda a 1ª visita.

    Usa o vencimento atual do plano e avanca `next_due_date` para o ciclo
    seguinte, de so que a proxima cobranca agende a visita seguinte.

    Regras de disparo:
    - So age em transicoes de status (update_fields contem "status" ou e None).
    - So age para transacoes kind=PAYMENT (ignora kind=CHECKOUT do hosted).
    - Idempotente: trava o plano e verifica se ja existe visita na data.
    """
    update_fields = kwargs.get("update_fields")
    if update_fields is not None and "status" not in update_fields:
        return
    if instance.status != "paid":
        return
    plan = getattr(getattr(instance, "order", None), "maintenance_plan", None)
    if plan is None:
        return
    from apps.payments.models import Transaction

    if instance.kind != Transaction.Kind.PAYMENT:
        return
    from .models import MaintenancePlan, MaintenanceVisit

    with transaction.atomic():
        locked = MaintenancePlan.objects.select_for_update().get(pk=plan.pk)
        if locked.visits.filter(scheduled_at__date=locked.next_due_date).exists():
            return
        scheduled_at = timezone.make_aware(
            datetime.combine(locked.next_due_date, datetime.min.time())
        )
        MaintenanceVisit.objects.create(plan=locked, scheduled_at=scheduled_at)
        locked.next_due_date = locked.next_due_date + timedelta(days=locked.cycle_days())
        locked.save(update_fields=["next_due_date", "updated_at"])
