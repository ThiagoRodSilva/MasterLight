"""Testes do AsaasGateway: cobrança Pix/cartão, refund e webhook."""

import json

import pytest
from django.urls import reverse

from apps.payments.models import Transaction
from apps.payments.services import AsaasGateway
from conftest import create_order

pytestmark = pytest.mark.django_db

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("activation")]


class TestAsaasCharge:
    def test_charge_pix_creates_transaction(self, asaas, user):
        order = create_order(user, with_referral=False)
        gateway = AsaasGateway()
        result = gateway.charge(order, billing_type="PIX")

        assert result.ok is True
        assert result.status == Transaction.Status.PENDING
        tx = Transaction.objects.get(pk=result.external_id)
        assert tx.provider == "asaas"
        assert tx.external_id == asaas.payment_id
        assert tx.amount == order.total

        payload = json.loads(tx.raw_payload)
        assert payload["pix"]["payload"] == "00020126580014BR.GOV.BCB.PIX"

    def test_charge_creates_customer_once(self, asaas, user):
        order = create_order(user, with_referral=False)
        gateway = AsaasGateway()
        gateway.charge(order)
        gateway.charge(order)

        create_customer_calls = [
            c for c in asaas.calls if c["method"] == "POST" and c["url"].endswith("/customers")
        ]
        assert len(create_customer_calls) == 1

    def test_charge_credit_card(self, asaas, user):
        order = create_order(user, with_referral=False)
        gateway = AsaasGateway()
        result = gateway.charge(order, billing_type="CREDIT_CARD")

        tx = Transaction.objects.get(pk=result.external_id)
        assert tx.status == Transaction.Status.PENDING

    def test_charge_invalid_billing_type(self, asaas, user):
        order = create_order(user, with_referral=False)
        with pytest.raises(ValueError):
            AsaasGateway().charge(order, billing_type="BOLETO")


class TestAsaasWebhook:
    def test_webhook_confirmed_marks_paid(self, asaas, user):
        order = create_order(user, with_referral=False)
        AsaasGateway().charge(order)
        tx = order.transactions.get(provider="asaas")

        payload = json.dumps({"event": "PAYMENT_CONFIRMED", "payment": {"id": asaas.payment_id}})
        AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})

        tx.refresh_from_db()
        assert tx.status == Transaction.Status.PAID

    def test_webhook_invalid_token_raises(self, asaas, user):
        order = create_order(user, with_referral=False)
        AsaasGateway().charge(order)

        payload = json.dumps({"event": "PAYMENT_CONFIRMED", "payment": {"id": asaas.payment_id}})
        with pytest.raises(ValueError):
            AsaasGateway().webhook(payload, {"x-webhook-token": "errado"})

    def test_webhook_unknown_payment_raises(self, asaas, user):
        payload = json.dumps({"event": "PAYMENT_CONFIRMED", "payment": {"id": "outra-pay"}})
        with pytest.raises(ValueError):
            AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})


class TestPixConfirmationView:
    def test_pix_confirmation_shows_qr(self, asaas, user, client):
        client.force_login(user)
        order = create_order(user, with_referral=False)
        AsaasGateway().charge(order, billing_type="PIX")

        response = client.get(reverse("payments-pix-confirm", kwargs={"order_pk": order.pk}))
        assert response.status_code == 200
        html = response.content.decode()
        assert "Pay with Pix" in html or "Pix" in html
        assert "base64png" in html

    def test_pix_confirmation_requires_own_order(self, asaas, user, client, affiliate_profile):
        client.force_login(user)
        other = affiliate_profile.user
        order = create_order(other, with_referral=False)

        response = client.get(reverse("payments-pix-confirm", kwargs={"order_pk": order.pk}))
        assert response.status_code == 404

    def test_refund_sets_refunded(self, asaas, user):
        order = create_order(user, with_referral=False)
        tx_id = AsaasGateway().charge(order).external_id
        tx_not_refunded = Transaction.objects.get(pk=tx_id)

        result = AsaasGateway().refund(tx_not_refunded.pk, amount=order.total)

        assert result.ok is True
        tx_not_refunded.refresh_from_db()
        assert tx_not_refunded.status == Transaction.Status.REFUNDED

    def test_refund_untracked_returns_not_ok(self, asaas, user):
        from uuid import uuid4

        result = AsaasGateway().refund(str(uuid4()), amount=1)
        assert result.ok is False
