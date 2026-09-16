"""Signals services: conclui a solicitacao quando o pedido e pago."""

from django.db.models.signals import post_save
from django.dispatch import receiver

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
