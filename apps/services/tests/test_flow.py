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

    def test_approve_creates_service_order_and_pix(self):
        provider = make_user(role=CustomUser.Role.PRESTADOR)
        cliente = make_user(role=CustomUser.Role.CLIENTE)
        sr = self._make_quoted_request(cliente, provider)

        self.client.force_login(cliente)
        response = self.client.post(reverse("services-request-approve", kwargs={"pk": sr.pk}))

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

    def test_paid_webhook_approves_service_request(self):
        provider = make_user(role=CustomUser.Role.PRESTADOR)
        cliente = make_user(role=CustomUser.Role.CLIENTE)
        sr = self._make_quoted_request(cliente, provider)

        self.client.force_login(cliente)
        self.client.post(reverse("services-request-approve", kwargs={"pk": sr.pk}))
        sr.refresh_from_db()
        order = sr.order

        payload = json.dumps({"event": "PAYMENT_CONFIRMED", "payment": {"id": self.asaas.payment_id}})
        AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})

        order.refresh_from_db()
        assert order.status == Order.Status.PAID

        sr.refresh_from_db()
        assert sr.status == ServiceRequest.Status.APPROVED

    def test_approve_with_boleto_redirects_to_boleto_confirm(self):
        provider = make_user(role=CustomUser.Role.PRESTADOR)
        cliente = make_user(role=CustomUser.Role.CLIENTE)
        sr = self._make_quoted_request(cliente, provider)

        self.client.force_login(cliente)
        response = self.client.post(
            reverse("services-request-approve", kwargs={"pk": sr.pk}),
            {"payment_method": "BOLETO"},
        )

        sr.refresh_from_db()
        assert response.status_code == 302
        assert response.url == reverse("payments-boleto-confirm", kwargs={"order_pk": sr.order.pk})
        tx = Transaction.objects.get(order=sr.order)
        assert tx.provider == "asaas"
        assert "bankSlip" in json.loads(tx.raw_payload)

    def test_approve_page_renders_payment_options(self):
        provider = make_user(role=CustomUser.Role.PRESTADOR)
        cliente = make_user(role=CustomUser.Role.CLIENTE)
        sr = self._make_quoted_request(cliente, provider)

        self.client.force_login(cliente)
        response = self.client.get(reverse("services-request-approve", kwargs={"pk": sr.pk}))
        assert response.status_code == 200
        html = response.content.decode()
        assert "Aprovar orçamento" in html
        assert "Boleto bancário" in html
        assert "Cartão de crédito" in html
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
