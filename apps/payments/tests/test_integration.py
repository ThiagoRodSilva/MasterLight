"""Integração ponta a ponta: compra -> PIX -> webhook -> comissão afiliado."""
import json

import pytest

from apps.affiliate.models import Referral
from apps.checkout.models import Order
from apps.payments.models import Transaction
from apps.payments.services import AsaasGateway
from conftest import create_order

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("activation")]


class TestAsaasEndToEnd:
    def _pay(self, asaas, order):
        """Gera cobrança asaas e dispara webhook CONFIRMED."""
        AsaasGateway().charge(order, billing_type="PIX")
        payload = json.dumps(
            {"event": "PAYMENT_CONFIRMED", "payment": {"id": asaas.payment_id}}
        )
        AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})

    def test_paid_transaction_approves_referral(self, asaas, user):
        order = create_order(user, with_referral=True)
        self._pay(asaas, order)

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
