"""Signals services: conclui a solicitacao quando o pedido e pago."""

from datetime import datetime, timedelta

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
    service_request.status = "approved"
    service_request.save(update_fields=["status", "updated_at"])


@receiver(post_save, sender="payments.Transaction")
def schedule_first_maintenance_visit(sender, instance, **kwargs):
    """Quando a Transaction de assinatura e PAGA, agenda a 1ª visita.

    Usa o vencimento atual do plano e avanca `next_due_date` para o ciclo
    seguinte, de modo que a proxima cobranca agende a visita seguinte.
    """
    if kwargs.get("created"):
        return
    if instance.status != "paid":
        return
    plan = getattr(getattr(instance, "order", None), "maintenance_plan", None)
    if plan is None:
        return
    from .models import MaintenanceVisit

    if plan.visits.filter(scheduled_at__date=plan.next_due_date).exists():
        return
    scheduled_at = timezone.make_aware(
        datetime.combine(plan.next_due_date, datetime.min.time())
    )
    MaintenanceVisit.objects.create(plan=plan, scheduled_at=scheduled_at)
    plan.next_due_date = plan.next_due_date + timedelta(days=plan.cycle_days())
    plan.save(update_fields=["next_due_date", "updated_at"])
