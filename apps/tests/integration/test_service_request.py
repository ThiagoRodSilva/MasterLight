"""Integração ponta a ponta: Service Request completo (solicitação -> orçamento -> aprovação -> pagamento)."""

import json
from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.checkout.models import Order
from apps.payments.models import Transaction
from apps.services.models import Service, ServiceCategory, ServiceRequest
from apps.tests.helpers import AsaasMockMixin, make_user


ASAAS_SETTINGS = {
    "PAYMENT_PROVIDER": "asaas",
    "ASAAS_API_KEY": "teste-key",
    "ASAAS_SANDBOX": True,
    "ASAAS_WEBHOOK_TOKEN": "segredo",
    "CARD_ENABLED": True,
    "BOLETO_ENABLED": True,
}


@override_settings(**ASAAS_SETTINGS)
class TestServiceRequestFlow(AsaasMockMixin, TestCase):
    """Fluxo completo: cliente solicita -> prestador orça -> cliente aprova -> pagamento -> aprovado."""

    def setUp(self):
        super().setUp()
        self.category = ServiceCategory.objects.create(name="Elétrica", slug="eletrica-flow")
        self.provider = make_user(role="prestador", email="provider@test.com")
        self.client_user = make_user(role="cliente", email="client@test.com")
        self.service = Service.objects.create(
            name="Instalação Tomada",
            slug="instalacao-tomada",
            base_price=Decimal("150.00"),
            category=self.category,
            created_by=self.provider,
        )
        self.service.providers.add(self.provider)

    def _client_request_service(self):
        self.client.force_login(self.client_user)
        response = self.client.post(
            reverse("services-request", args=[self.service.slug]),
            {"prestador": self.provider.id, "address": "Rua Teste, 123", "scheduled_at": "2025-01-15T10:00"},
            follow=True,
        )
        return response

    def _provider_quote(self, service_request, price):
        self.client.force_login(self.provider)
        response = self.client.post(
            reverse("services-request-quote", args=[service_request.pk]),
            {"final_price": str(price)},
            follow=True,
        )
        return response

    def _client_approve_and_pay(self, service_request, payment_method="PIX"):
        self.client.force_login(self.client_user)
        response = self.client.post(
            reverse("services-request-approve", args=[service_request.pk]),
            {"payment_method": payment_method},
            follow=True,
        )
        return response

    def _pay_order(self, order):
        from apps.payments.services import AsaasGateway

        AsaasGateway().charge(order, billing_type="PIX")
        payload = json.dumps({"event": "PAYMENT_CONFIRMED", "payment": {"id": self.asaas.payment_id}})
        AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})

    def test_service_request_complete_flow(self):
        """Fluxo completo: solicitar -> orçar -> aprovar -> pagar -> aprovado."""
        self._client_request_service()
        service_request = ServiceRequest.objects.get(cliente=self.client_user)
        self.assertEqual(service_request.status, ServiceRequest.Status.PENDING)
        self.assertEqual(service_request.prestador, self.provider)

        self._provider_quote(service_request, Decimal("200.00"))
        service_request.refresh_from_db()
        self.assertEqual(service_request.status, ServiceRequest.Status.QUOTED)
        self.assertEqual(service_request.final_price, Decimal("200.00"))

        self._client_approve_and_pay(service_request)
        order = Order.objects.filter(user=self.client_user, kind=Order.Kind.SERVICE).latest("created_at")
        self.assertEqual(order.status, Order.Status.AWAITING_PAYMENT)
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().unit_price, Decimal("200.00"))

        tx = order.transactions.get(provider="asaas")
        self.assertEqual(tx.status, Transaction.Status.PENDING)

        self._pay_order(order)

        order.refresh_from_db()
        service_request.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(service_request.status, ServiceRequest.Status.APPROVED)

    def test_service_request_client_cancel_pending(self):
        """Cliente cancela solicitação pendente."""
        self._client_request_service()
        service_request = ServiceRequest.objects.get(cliente=self.client_user)

        self.client.force_login(self.client_user)
        response = self.client.post(reverse("services-request-cancel", args=[service_request.pk]), follow=True)
        self.assertEqual(response.status_code, 200)

        service_request.refresh_from_db()
        self.assertEqual(service_request.status, ServiceRequest.Status.CANCELED)

    def test_service_request_provider_cannot_quote_twice(self):
        """Prestador não pode orçar duas vezes."""
        self._client_request_service()
        service_request = ServiceRequest.objects.get(cliente=self.client_user)

        self._provider_quote(service_request, Decimal("200.00"))
        response = self._provider_quote(service_request, Decimal("250.00"))
        # View filters by status=PENDING, returns 404 if not found
        self.assertEqual(response.status_code, 404)

    def test_service_request_quote_only_pending(self):
        """Orçamento só pode ser enviado em status PENDING."""
        self._client_request_service()
        service_request = ServiceRequest.objects.get(cliente=self.client_user)

        self._provider_quote(service_request, Decimal("200.00"))
        service_request.status = ServiceRequest.Status.APPROVED
        service_request.save()

        self.client.force_login(self.provider)
        response = self.client.post(
            reverse("services-request-quote", args=[service_request.pk]),
            {"final_price": "300.00"},
        )
        # View filters by status=PENDING, returns 404 if not found
        self.assertEqual(response.status_code, 404)


@override_settings(**ASAAS_SETTINGS)
class TestServiceRequestPayLinkFlow(AsaasMockMixin, TestCase):
    """Fluxo com link de pagamento avulso (PaymentLink)."""

    def setUp(self):
        super().setUp()
        self.category = ServiceCategory.objects.create(name="Elétrica", slug="eletrica-plink")
        self.provider = make_user(role="prestador", email="provider-plink@test.com")
        self.client_user = make_user(role="cliente", email="client-plink@test.com")
        self.service = Service.objects.create(
            name="Reparo Elétrico",
            slug="reparo-eletrico",
            base_price=Decimal("300.00"),
            category=self.category,
            created_by=self.provider,
        )
        self.service.providers.add(self.provider)

    def test_service_request_paylink_flow(self):
        """Fluxo: orçamento -> link de pagamento -> pagamento -> aprovado."""
        self.client.force_login(self.client_user)
        response = self.client.post(
            reverse("services-request", args=[self.service.slug]),
            {"prestador": self.provider.id, "address": "Rua Teste, 456", "scheduled_at": "2025-01-15T10:00"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        service_request = ServiceRequest.objects.get(cliente=self.client_user)
        self.client.force_login(self.provider)
        self.client.post(
            reverse("services-request-quote", args=[service_request.pk]),
            {"final_price": "400.00"},
            follow=True,
        )

        self.client.force_login(self.client_user)
        response = self.client.post(
            reverse("services-request-paylink", args=[service_request.pk]),
            follow=False,  # Returns JSON
        )
        self.assertEqual(response.status_code, 200)
        import json
        data = json.loads(response.content)
        self.assertIn("url", data)
        service_request.refresh_from_db()
        self.assertIsNotNone(service_request.asaas_payment_link_id)

        from apps.payments.services import AsaasGateway

        payment_id = self.asaas.payment_id
        link_id = self.asaas.payment_link_id
        payload = json.dumps(
            {
                "event": "PAYMENT_CONFIRMED",
                "payment": {
                    "id": payment_id,
                    "paymentLink": link_id,
                    "value": float(service_request.final_price or service_request.service.base_price),
                },
            }
        )
        AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})

        service_request.refresh_from_db()
        order = Order.objects.filter(user=self.client_user, kind=Order.Kind.SERVICE).latest("created_at")
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(service_request.status, ServiceRequest.Status.APPROVED)