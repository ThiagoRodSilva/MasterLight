"""Regressões das correções de domínio de pagamentos (C1/C2/I3/I4/I1).

- C1: Order -> PAGO e baixa de estoque agora vivem em `payments` (idempotente).
- C2: reembolso reverte pedido (REFUNDED), estoque e comissão de afiliado.
- I3: guardas de transição de status (webhook/reconciliação não revertem).
- I4: criação idempotente de Transaction por (provider, external_id).
- I1: `get_gateway` rígido em produção + system check `payments.E002`.
"""

import json
from unittest import mock

from django.test import TestCase, override_settings

from apps.affiliate.models import Referral
from apps.checkout.models import Order
from apps.payments.checks import payment_provider_check
from apps.payments.gateways.base import can_transition
from apps.payments.models import Transaction
from apps.payments.services import (
    AsaasGateway,
    checkout_or_charge,
)
from apps.tests.helpers import create_order, make_user

ASAAS_SETTINGS = {
    "PAYMENT_PROVIDER": "asaas",
    "ASAAS_API_KEY": "teste-key",
    "ASAAS_SANDBOX": True,
    "ASAAS_WEBHOOK_TOKEN": "segredo",
}


class TestCanTransition(TestCase):
    def test_allowed_transitions(self):
        assert can_transition("pending", "authorized") is True
        assert can_transition("pending", "paid") is True
        assert can_transition("pending", "failed") is True
        assert can_transition("pending", "refunded") is True
        assert can_transition("authorized", "paid") is True
        assert can_transition("paid", "refunded") is True

    def test_terminal_transitions_blocked(self):
        assert can_transition("paid", "failed") is False
        assert can_transition("failed", "paid") is False
        assert can_transition("refunded", "paid") is False
        assert can_transition("refunded", "pending") is False
        assert can_transition("unknown", "paid") is False


@override_settings(**ASAAS_SETTINGS)
class TestMarkOrderPaid(TestCase):
    def test_paid_twice_does_not_double_transition(self):
        user = make_user()
        order = create_order(user, qty=3)
        tx = order.transactions.first()
        tx.provider = "asaas"
        tx.external_id = "pay_test_stock"
        tx.save(update_fields=["provider", "external_id", "status", "updated_at"])

        tx.status = "paid"
        tx.save(update_fields=["status", "updated_at"])
        tx.status = "paid"
        tx.save(update_fields=["status", "updated_at"])

        order.refresh_from_db()
        assert order.status == Order.Status.PAID


@override_settings(**ASAAS_SETTINGS)
class TestRefundReversal(TestCase):
    def test_refund_reverses_order_and_commission(self):
        user = make_user()
        order = create_order(user, with_referral=True, qty=2)
        referral = order.referrals.get()
        affiliate = referral.affiliate
        tx = order.transactions.first()
        tx.provider = "asaas"
        tx.external_id = "pay_test_refund"
        tx.save(update_fields=["provider", "external_id", "status", "updated_at"])

        tx.status = "paid"
        tx.save(update_fields=["status", "updated_at"])
        order.refresh_from_db()
        referral.refresh_from_db()
        affiliate.refresh_from_db()
        assert order.status == Order.Status.PAID
        assert referral.status == Referral.Status.APPROVED
        assert affiliate.balance == referral.commission_amount

        tx.status = "refunded"
        tx.save(update_fields=["status", "updated_at"])

        order.refresh_from_db()
        referral.refresh_from_db()
        affiliate.refresh_from_db()
        assert order.status == Order.Status.REFUNDED
        assert referral.status == Referral.Status.PENDING
        assert affiliate.balance == 0

    def test_refund_twice_no_negative_balance(self):
        user = make_user()
        order = create_order(user, with_referral=True, qty=1)
        referral = order.referrals.get()
        affiliate = referral.affiliate
        tx = order.transactions.first()
        tx.provider = "asaas"
        tx.external_id = "pay_test_refund2"
        tx.save(update_fields=["provider", "external_id", "status", "updated_at"])

        tx.status = "paid"
        tx.save(update_fields=["status", "updated_at"])
        order.refresh_from_db()
        referral.refresh_from_db()
        affiliate.refresh_from_db()
        assert affiliate.balance == referral.commission_amount

        tx.status = "refunded"
        tx.save(update_fields=["status", "updated_at"])
        tx.status = "refunded"
        tx.save(update_fields=["status", "updated_at"])

        affiliate.refresh_from_db()
        assert affiliate.balance == 0


@override_settings(**ASAAS_SETTINGS)
class TestTransitionGuards(TestCase):
    def test_webhook_cannot_revert_paid_to_failed(self):
        user = make_user()
        order = create_order(user, qty=1)
        tx = order.transactions.first()
        tx.provider = "asaas"
        tx.external_id = "pay_test_123"
        tx.save(update_fields=["provider", "external_id", "status", "updated_at"])

        tx.status = "paid"
        tx.save(update_fields=["status", "updated_at"])

        gateway = AsaasGateway()
        payload = json.dumps({"event": "payment_overdue", "payment": {"id": tx.external_id}})
        result = gateway.webhook(payload, {"asaas-access-token": "segredo"})

        tx.refresh_from_db()
        assert tx.status == "paid"
        assert result.status == "paid"

    def test_webhook_cannot_revert_refunded_to_paid(self):
        user = make_user()
        order = create_order(user, qty=1)
        tx = order.transactions.first()
        tx.provider = "asaas"
        tx.external_id = "pay_test_456"
        tx.save(update_fields=["provider", "external_id", "status", "updated_at"])

        tx.status = "refunded"
        tx.save(update_fields=["status", "updated_at"])

        gateway = AsaasGateway()
        payload = json.dumps({"event": "payment_confirmed", "payment": {"id": tx.external_id}})
        result = gateway.webhook(payload, {"asaas-access-token": "segredo"})

        tx.refresh_from_db()
        assert tx.status == "refunded"
        assert result.status == "refunded"


@override_settings(**ASAAS_SETTINGS)
class TestIdempotentTransactionCreation(TestCase):
    def test_same_external_id_reuses_transaction(self):
        user = make_user()
        order = create_order(user, qty=1)
        tx = order.transactions.first()
        tx.provider = "asaas"
        tx.external_id = "pay_test_789"
        tx.save(update_fields=["provider", "external_id", "status", "updated_at"])
        external_id = tx.external_id
        provider = tx.provider

        gateway = AsaasGateway()
        payload = json.dumps(
            {"event": "payment_confirmed", "payment": {"id": external_id, "value": "10.00"}}
        )
        result = gateway.webhook(payload, {"asaas-access-token": "segredo"})

        count = Transaction.objects.filter(external_id=external_id, provider=provider).count()
        assert count == 1
        assert result.transaction_id == str(tx.pk)

    def test_multiple_webhooks_same_payment_same_transaction(self):
        user = make_user()
        order = create_order(user, qty=1)
        tx = order.transactions.first()
        tx.provider = "asaas"
        tx.external_id = "pay_test_999"
        tx.save(update_fields=["provider", "external_id", "status", "updated_at"])
        external_id = tx.external_id
        provider = tx.provider

        gateway = AsaasGateway()
        for _ in range(3):
            payload = json.dumps(
                {"event": "payment_confirmed", "payment": {"id": external_id, "value": "10.00"}}
            )
            gateway.webhook(payload, {"asaas-access-token": "segredo"})

        count = Transaction.objects.filter(external_id=external_id, provider=provider).count()
        assert count == 1


@override_settings(**ASAAS_SETTINGS)
class TestReferralIdempotentApproval(TestCase):
    def test_approve_same_referral_twice_does_not_double_credit(self):
        user = make_user()
        order = create_order(user, with_referral=True, qty=2)
        referral = order.referrals.get()
        affiliate = referral.affiliate
        tx = order.transactions.first()
        tx.provider = "asaas"
        tx.external_id = "pay_test_ref"
        tx.save(update_fields=["provider", "external_id", "status", "updated_at"])

        tx.status = "paid"
        tx.save(update_fields=["status", "updated_at"])

        order.refresh_from_db()
        referral.refresh_from_db()
        affiliate.refresh_from_db()
        pk1 = referral.pk
        # balance1 = affiliate.balance  # unused

        tx2 = Transaction.objects.create(
            order=order,
            user=order.user,
            provider="asaas",
            external_id="ext-2",
            amount=order.total,
            status="paid",
        )
        tx2.status = "paid"
        tx2.save(update_fields=["status", "updated_at"])

        order.refresh_from_db()
        referral.refresh_from_db()
        affiliate.refresh_from_db()
        assert pk1 == referral.pk
        assert referral.status == Referral.Status.APPROVED
        assert affiliate.balance == referral.commission_amount


@override_settings(**ASAAS_SETTINGS)
class TestCheckoutOrChargeDoesNotCancelPaid(TestCase):
    def test_checkout_or_charge_does_not_cancel_paid_order(self):
        """Falha no checkout_or_charge nao cancela pedido ja PAID."""

        user = make_user()
        order = create_order(user, qty=1)

        # Coloca o pedido como PAID
        tx = order.transactions.first()
        tx.status = "paid"
        tx.save(update_fields=["status", "updated_at"])
        order.refresh_from_db()
        assert order.status == Order.Status.PAID

        # Mock create_checkout_for_order para levantar ValueError
        with mock.patch(
            "apps.payments.services.create_checkout_for_order", side_effect=ValueError("erro")
        ):
            with mock.patch("django.contrib.messages.error") as mock_messages:
                from django.test import RequestFactory

                factory = RequestFactory()
                request = factory.post("/")
                request.user = user

                with self.settings(PAYMENT_PROVIDER="asaas"):
                    result = checkout_or_charge(order, request, fail_message="Falha")

        # Pedido deve permanecer PAID
        order.refresh_from_db()
        assert order.status == Order.Status.PAID
        assert result is None
        mock_messages.assert_called_once()


@override_settings(**ASAAS_SETTINGS)
class TestSystemCheck(TestCase):
    def test_asaas_api_key_check_fails_without_key(self):
        from apps.payments.checks import asaas_api_key_check

        with self.settings(PAYMENT_PROVIDER="asaas", ASAAS_API_KEY=""):
            errors = asaas_api_key_check(None)
            assert any(e.id == "payments.E001" for e in errors)

    def test_asaas_api_key_check_passes_with_key(self):
        from apps.payments.checks import asaas_api_key_check

        with self.settings(PAYMENT_PROVIDER="asaas", ASAAS_API_KEY="test-key"):
            errors = asaas_api_key_check(None)
            assert not any(e.id == "payments.E001" for e in errors)

    def test_payment_provider_check_passes_for_manual(self):
        with self.settings(PAYMENT_PROVIDER="manual"):
            errors = payment_provider_check(None)
            assert not any(e.id == "payments.E002" for e in errors)
