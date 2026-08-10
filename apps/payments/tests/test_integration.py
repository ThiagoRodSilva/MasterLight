"""Integração ponta a ponta: compra -> PIX -> webhook -> comissão afiliado."""

import json

from django.test import TestCase, override_settings

from apps.affiliate.models import Referral
from apps.checkout.models import Order
from apps.payments.models import Transaction
from apps.payments.services import AsaasGateway
from apps.tests.helpers import AsaasMockMixin, create_order, make_user

ASAAS_SETTINGS = {
    "PAYMENT_PROVIDER": "asaas",
    "ASAAS_API_KEY": "teste-key",
    "ASAAS_SANDBOX": True,
    "ASAAS_WEBHOOK_TOKEN": "segredo",
}


@override_settings(**ASAAS_SETTINGS)
class TestAsaasEndToEnd(AsaasMockMixin, TestCase):
    def _pay(self, order):
        """Gera cobrança asaas e dispara webhook CONFIRMED."""
        AsaasGateway().charge(order, billing_type="PIX")
        payload = json.dumps({"event": "PAYMENT_CONFIRMED", "payment": {"id": self.asaas.payment_id}})
        AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})

    def test_paid_transaction_approves_referral(self):
        user = make_user()
        order = create_order(user, with_referral=True)
        self._pay(order)

        tx = order.transactions.get(provider="asaas")
        tx.refresh_from_db()
        assert tx.status == Transaction.Status.PAID

        order.refresh_from_db()
        assert order.status == Order.Status.PAID

        referral = order.referrals.get()
        referral.refresh_from_db()
        assert referral.status == Referral.Status.APPROVED
        assert referral.affiliate.balance > 0
        assert referral.affiliate.balance == referral.commission_amount
