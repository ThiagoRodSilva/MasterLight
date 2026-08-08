"""Fluxo completo: aprovação do orçamento gera pedido PIX e aprova solicitação."""

import json
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.checkout.models import Order, OrderItem
from apps.payments.models import Transaction
from apps.payments.services import AsaasGateway
from apps.services.models import Service, ServiceCategory, ServiceRequest
from conftest import UserFactory

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("activation")]


class TestApprovalCreatesOrderAndPays:
    def _make_quoted_request(self, cliente, provider):
        category = ServiceCategory.objects.create(name="Elétrica", slug="eletrica")
        service = Service.objects.create(
            name="Instalação",
            slug="instalacao",
            base_price=10,
            category=category,
            created_by=provider,
        )
        service.providers.add(provider)
        sr = ServiceRequest.objects.create(
            cliente=cliente,
            service=service,
            prestador=provider,
            status=ServiceRequest.Status.QUOTED,
            final_price=99.90,
        )
        return sr

    def test_approve_creates_service_order_and_pix(self, asaas, client):
        provider = UserFactory(role=CustomUser.Role.PRESTADOR)
        cliente = UserFactory(role=CustomUser.Role.CLIENTE)
        sr = self._make_quoted_request(cliente, provider)

        client.force_login(cliente)
        response = client.post(reverse("services-request-approve", kwargs={"pk": sr.pk}))

        sr.refresh_from_db()
        assert response.status_code == 302
        assert sr.order is not None

        order = sr.order
        assert order.kind == Order.Kind.SERVICE
        assert order.user == cliente
        assert order.status == Order.Status.AWAITING_PAYMENT

        item = OrderItem.objects.get(order=order)
        assert item.unit_price == Decimal("99.90")
        assert order.total == Decimal("99.90")

        tx = Transaction.objects.get(order=order)
        assert tx.provider == "asaas"

    def test_paid_webhook_approves_service_request(self, asaas, client):
        provider = UserFactory(role=CustomUser.Role.PRESTADOR)
        cliente = UserFactory(role=CustomUser.Role.CLIENTE)
        sr = self._make_quoted_request(cliente, provider)

        client.force_login(cliente)
        client.post(reverse("services-request-approve", kwargs={"pk": sr.pk}))
        sr.refresh_from_db()
        order = sr.order

        payload = json.dumps({"event": "PAYMENT_CONFIRMED", "payment": {"id": asaas.payment_id}})
        AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})

        order.refresh_from_db()
        assert order.status == Order.Status.PAID

        sr.refresh_from_db()
        assert sr.status == ServiceRequest.Status.APPROVED
