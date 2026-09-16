"""Regressões da remoção do ManualGateway (simplificação).

Garante que o provider manual não existe mais: `get_gateway()` levanta
`ImproperlyConfigured` quando `PAYMENT_PROVIDER=manual`, o registry só
contém `asaas`, a URL de confirmação manual não resolve e o módulo foi
removido. Também mantém coberta a regressão de bloqueio de transições
que antes vivia no gateway manual.
"""

import json

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings
from django.urls import NoReverseMatch, reverse

from apps.payments.gateways import _REGISTRY, get_gateway
from apps.payments.gateways.asaas import AsaasGateway
from apps.payments.models import Transaction
from apps.tests.helpers import AsaasMockMixin, create_order, make_user


class TestManualGatewayRemoved(TestCase):
    @override_settings(PAYMENT_PROVIDER="manual", ASAAS_API_KEY="")
    def test_manual_provider_raises(self):
        with self.assertRaisesRegex(ImproperlyConfigured, "manual"):
            get_gateway()

    def test_registry_contains_only_asaas(self):
        assert set(_REGISTRY) == {"asaas"}

    def test_manual_confirmation_url_does_not_exist(self):
        from apps.checkout.models import Order

        user = make_user()
        order = Order.objects.create(user=user, status=Order.Status.AWAITING_PAYMENT)
        with self.assertRaises(NoReverseMatch):
            reverse("payments-manual-confirm", kwargs={"order_pk": order.pk})

    def test_no_manual_gateway_module(self):
        import importlib

        with self.assertRaises(ModuleNotFoundError):
            importlib.import_module("apps.payments.gateways.manual")


@override_settings(
    PAYMENT_PROVIDER="asaas",
    ASAAS_API_KEY="teste-key",
    ASAAS_SANDBOX=True,
    ASAAS_WEBHOOK_TOKEN="segredo",
)
class TestTransitionRegressionAfterManualRemoval(AsaasMockMixin, TestCase):
    """Regressões que antes eram cobertas pelo ManualGateway continuam valendo.

    A lógica de bloqueio de transições vive no `BasePaymentGateway`/`can_transition`
    e é exercitada aqui via `AsaasGateway` (provider único após a simplificação).
    """

    def test_webhook_blocks_refunded_to_paid(self):
        user = make_user()
        order = create_order(user, with_referral=True)
        gateway = AsaasGateway()

        result = gateway.charge(order, billing_type="PIX")
        tx = Transaction.objects.get(pk=result.transaction_id)
        assert tx.external_id == self.asaas.payment_id

        payload = json.dumps(
            {"event": "PAYMENT_CONFIRMED", "payment": {"id": self.asaas.payment_id}}
        )
        r = gateway.webhook(payload, {"x-webhook-token": "segredo"})
        assert r.ok
        tx.refresh_from_db()
        assert tx.status == Transaction.Status.PAID

        payload = json.dumps(
            {"event": "PAYMENT_REFUNDED", "payment": {"id": self.asaas.payment_id}}
        )
        r = gateway.webhook(payload, {"x-webhook-token": "segredo"})
        assert r.ok
        tx.refresh_from_db()
        assert tx.status == Transaction.Status.REFUNDED

        payload = json.dumps(
            {"event": "PAYMENT_CONFIRMED", "payment": {"id": self.asaas.payment_id}}
        )
        r = gateway.webhook(payload, {"x-webhook-token": "segredo"})
        assert r.ok
        assert "bloqueada" in r.message
        tx.refresh_from_db()
        assert tx.status == Transaction.Status.REFUNDED
