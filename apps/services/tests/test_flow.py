"""Fluxo completo: aprovação do orçamento gera pedido PIX e aprova solicitação."""

import json
from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.checkout.models import Order, OrderItem
from apps.payments.models import Transaction
from apps.payments.services import AsaasGateway
from apps.services.models import Service, ServiceCategory, ServiceRequest
from apps.tests.helpers import AsaasMockMixin, make_user

ASAAS_SETTINGS = {
    "PAYMENT_PROVIDER": "asaas",
    "ASAAS_API_KEY": "teste-key",
    "ASAAS_SANDBOX": True,
    "ASAAS_WEBHOOK_TOKEN": "segredo",
}


@override_settings(**ASAAS_SETTINGS)
class TestApprovalCreatesOrderAndPays(AsaasMockMixin, TestCase):
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

    def test_approve_creates_service_order_and_checkout(self):
        provider = make_user(role=CustomUser.Role.PRESTADOR)
        cliente = make_user(role=CustomUser.Role.CLIENTE)
        sr = self._make_quoted_request(cliente, provider)

        self.client.force_login(cliente)
        response = self.client.post(reverse("services-request-approve", kwargs={"pk": sr.pk}))

        sr.refresh_from_db()
        assert response.status_code == 302
        assert response.url == self.asaas.checkout_url
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
        assert tx.external_id == self.asaas.checkout_id

    def test_paid_webhook_approves_service_request(self):
        provider = make_user(role=CustomUser.Role.PRESTADOR)
        cliente = make_user(role=CustomUser.Role.CLIENTE)
        sr = self._make_quoted_request(cliente, provider)

        self.client.force_login(cliente)
        self.client.post(reverse("services-request-approve", kwargs={"pk": sr.pk}))
        sr.refresh_from_db()
        order = sr.order

        payload = json.dumps(
            {
                "event": "CHECKOUT_PAID",
                "checkout": {"id": self.asaas.checkout_id, "externalReference": str(order.pk)},
            }
        )
        AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})

        order.refresh_from_db()
        assert order.status == Order.Status.PAID

        sr.refresh_from_db()
        assert sr.status == ServiceRequest.Status.APPROVED

    def test_approve_page_renders_hosted_info(self):
        provider = make_user(role=CustomUser.Role.PRESTADOR)
        cliente = make_user(role=CustomUser.Role.CLIENTE)
        sr = self._make_quoted_request(cliente, provider)

        self.client.force_login(cliente)
        response = self.client.get(reverse("services-request-approve", kwargs={"pk": sr.pk}))
        assert response.status_code == 200
        html = response.content.decode()
        assert "Aprovar orçamento" in html
        assert "Aprovar e pagar" in html
        assert "Boleto bancário" not in html
        assert "Pagar com link do Asaas" in html


@override_settings(**ASAAS_SETTINGS)
class TestApprovalPayLink(AsaasMockMixin, TestCase):
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
        return ServiceRequest.objects.create(
            cliente=cliente,
            service=service,
            prestador=provider,
            status=ServiceRequest.Status.QUOTED,
            final_price=99.90,
        )

    def test_paylink_returns_asaas_url(self):
        provider = make_user(role=CustomUser.Role.PRESTADOR)
        cliente = make_user(role=CustomUser.Role.CLIENTE)
        sr = self._make_quoted_request(cliente, provider)

        self.client.force_login(cliente)
        response = self.client.post(reverse("services-request-paylink", kwargs={"pk": sr.pk}))

        assert response.status_code == 200
        data = response.json()
        assert data["url"] == self.asaas.payment_link_url
        assert data["link_id"] == self.asaas.payment_link_id
        assert not Order.objects.filter(user=cliente).exists()
        assert Transaction.objects.count() == 0

    def test_paylink_sends_request_value(self):
        provider = make_user(role=CustomUser.Role.PRESTADOR)
        cliente = make_user(role=CustomUser.Role.CLIENTE)
        sr = self._make_quoted_request(cliente, provider)

        self.client.force_login(cliente)
        self.client.post(reverse("services-request-paylink", kwargs={"pk": sr.pk}))

        link_call = next(
            c
            for c in self.asaas.calls
            if c["method"] == "POST" and c["url"].endswith("/paymentLinks")
        )
        assert link_call["body"]["value"] == "99.90"
        assert link_call["body"]["externalReference"] == str(sr.pk)
        assert link_call["body"]["billingType"] == "UNDEFINED"

    def test_paylink_requires_own_quoted_request(self):
        provider = make_user(role=CustomUser.Role.PRESTADOR)
        other = make_user(role=CustomUser.Role.CLIENTE)
        sr = self._make_quoted_request(other, provider)

        self.client.force_login(make_user(role=CustomUser.Role.CLIENTE))
        response = self.client.post(reverse("services-request-paylink", kwargs={"pk": sr.pk}))
        assert response.status_code == 404

    def test_paylink_manual_provider_returns_error(self):
        provider = make_user(role=CustomUser.Role.PRESTADOR)
        cliente = make_user(role=CustomUser.Role.CLIENTE)
        sr = self._make_quoted_request(cliente, provider)

        self.client.force_login(cliente)
        with override_settings(PAYMENT_PROVIDER="manual"):
            response = self.client.post(reverse("services-request-paylink", kwargs={"pk": sr.pk}))
        assert response.status_code == 400
        assert response.json()["error"]

    def test_paylink_persists_link_id(self):
        provider = make_user(role=CustomUser.Role.PRESTADOR)
        cliente = make_user(role=CustomUser.Role.CLIENTE)
        sr = self._make_quoted_request(cliente, provider)

        self.client.force_login(cliente)
        self.client.post(reverse("services-request-paylink", kwargs={"pk": sr.pk}))

        sr.refresh_from_db()
        assert sr.asaas_payment_link_id == self.asaas.payment_link_id

    def test_paylink_paid_webhook_reconciles_order_and_approves(self):
        provider = make_user(role=CustomUser.Role.PRESTADOR)
        cliente = make_user(role=CustomUser.Role.CLIENTE)
        sr = self._make_quoted_request(cliente, provider)
        sr.asaas_payment_link_id = self.asaas.payment_link_id
        sr.save(update_fields=["asaas_payment_link_id", "updated_at"])

        payload = json.dumps(
            {
                "event": "PAYMENT_CONFIRMED",
                "payment": {
                    "id": self.asaas.payment_id,
                    "paymentLink": self.asaas.payment_link_id,
                    "value": 99.9,
                },
            }
        )
        AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})

        sr.refresh_from_db()
        assert sr.order is not None
        order = sr.order
        assert order.status == Order.Status.PAID
        assert order.kind == Order.Kind.SERVICE
        assert order.total == Decimal("99.90")

        tx = Transaction.objects.get(order=order)
        assert tx.provider == "asaas"
        assert tx.external_id == self.asaas.payment_id
        assert tx.status == Transaction.Status.PAID

        assert sr.status == ServiceRequest.Status.APPROVED

    def test_paylink_paid_webhook_is_idempotent(self):
        provider = make_user(role=CustomUser.Role.PRESTADOR)
        cliente = make_user(role=CustomUser.Role.CLIENTE)
        sr = self._make_quoted_request(cliente, provider)
        sr.asaas_payment_link_id = self.asaas.payment_link_id
        sr.save(update_fields=["asaas_payment_link_id", "updated_at"])

        payload = json.dumps(
            {
                "event": "PAYMENT_CONFIRMED",
                "payment": {
                    "id": self.asaas.payment_id,
                    "paymentLink": self.asaas.payment_link_id,
                    "value": 99.9,
                },
            }
        )
        gateway = AsaasGateway()
        gateway.webhook(payload, {"x-webhook-token": "segredo"})
        gateway.webhook(payload, {"x-webhook-token": "segredo"})

        sr.refresh_from_db()
        assert sr.status == ServiceRequest.Status.APPROVED
        assert Transaction.objects.filter(external_id=self.asaas.payment_id).count() == 1
        assert Order.objects.filter(pk=sr.order_id).count() == 1

    def test_paylink_paid_webhook_ignores_unknown_link(self):
        provider = make_user(role=CustomUser.Role.PRESTADOR)
        cliente = make_user(role=CustomUser.Role.CLIENTE)
        self._make_quoted_request(cliente, provider)

        payload = json.dumps(
            {
                "event": "PAYMENT_CONFIRMED",
                "payment": {"id": self.asaas.payment_id, "paymentLink": "pl_desconhecida"},
            }
        )
        with self.assertRaises(ValueError):
            AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})
        assert Order.objects.filter(user=cliente).count() == 0
