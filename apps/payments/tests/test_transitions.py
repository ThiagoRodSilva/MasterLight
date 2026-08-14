"""Regressões das correções de domínio de pagamentos (C1/C2/I3/I4/I1).

- C1: Order -> PAGO e baixa de estoque agora vivem em `payments` (idempotente).
- C2: reembolso reverte pedido (REFUNDED), estoque e comissão de afiliado.
- I3: guardas de transição de status (webhook/reconciliação não revertem).
- I4: criação idempotente de Transaction por (provider, external_id).
- I1: `get_gateway` rígido em produção + system check `payments.E002`.
"""

import json

from django.test import TestCase, override_settings

from apps.affiliate.models import Referral
from apps.checkout.models import Address, Order
from apps.payments.checks import payment_provider_check
from apps.payments.gateways.base import can_transition
from apps.payments.models import Transaction
from apps.payments.services import AsaasGateway, ManualGateway
from apps.tests.helpers import AsaasMockMixin, create_order, make_user

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


class TestMarkOrderPaid(TestCase):
    def test_paid_twice_does_not_double_decrement_stock(self):
        user = make_user()
        order = create_order(user, qty=3)
        product = order.items.first().product
        initial_stock = product.stock
        tx = order.transactions.first()

        tx.status = "paid"
        tx.save(update_fields=["status", "updated_at"])
        tx.status = "paid"
        tx.save(update_fields=["status", "updated_at"])

        order.refresh_from_db()
        product.refresh_from_db()
        assert order.status == Order.Status.PAID
        assert product.stock == initial_stock - 3


@override_settings(**ASAAS_SETTINGS)
class TestRefundReversal(TestCase):
    def test_refund_reverses_stock_order_and_commission(self):
        user = make_user()
        order = create_order(user, with_referral=True, qty=2)
        product = order.items.first().product
        referral = order.referrals.get()
        affiliate = referral.affiliate
        initial_stock = product.stock
        tx = order.transactions.first()

        tx.status = "paid"
        tx.save(update_fields=["status", "updated_at"])
        order.refresh_from_db()
        product.refresh_from_db()
        referral.refresh_from_db()
        affiliate.refresh_from_db()
        assert order.status == Order.Status.PAID
        assert product.stock == initial_stock - 2
        assert referral.status == Referral.Status.APPROVED
        assert affiliate.balance == referral.commission_amount

        tx.status = "refunded"
        tx.save(update_fields=["status", "updated_at"])

        order.refresh_from_db()
        product.refresh_from_db()
        referral.refresh_from_db()
        affiliate.refresh_from_db()
        assert order.status == Order.Status.REFUNDED
        assert product.stock == initial_stock
        assert affiliate.balance == 0
        assert referral.status == Referral.Status.PENDING

    def test_refund_idempotent(self):
        user = make_user()
        order = create_order(user, with_referral=True, qty=1)
        product = order.items.first().product
        initial_stock = product.stock
        tx = order.transactions.first()

        tx.status = "paid"
        tx.save(update_fields=["status", "updated_at"])
        tx.status = "refunded"
        tx.save(update_fields=["status", "updated_at"])
        tx.status = "refunded"
        tx.save(update_fields=["status", "updated_at"])

        order.refresh_from_db()
        product.refresh_from_db()
        assert order.status == Order.Status.REFUNDED
        assert product.stock == initial_stock


@override_settings(**ASAAS_SETTINGS)
class TestWebhookTransitionGuards(AsaasMockMixin, TestCase):
    def _pay(self, order):
        AsaasGateway().charge(order, billing_type="PIX")
        payload = json.dumps(
            {"event": "PAYMENT_CONFIRMED", "payment": {"id": self.asaas.payment_id}}
        )
        AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})

    def test_refunded_tx_ignores_late_confirmed_event(self):
        user = make_user()
        order = create_order(user)
        self._pay(order)
        tx = order.transactions.get(provider="asaas")
        tx.status = Transaction.Status.REFUNDED
        tx.save(update_fields=["status", "updated_at"])

        payload = json.dumps(
            {"event": "PAYMENT_CONFIRMED", "payment": {"id": self.asaas.payment_id}}
        )
        AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})

        tx.refresh_from_db()
        assert tx.status == Transaction.Status.REFUNDED

    def test_paid_tx_ignores_overdue_event(self):
        user = make_user()
        order = create_order(user)
        self._pay(order)
        tx = order.transactions.get(provider="asaas")

        payload = json.dumps(
            {"event": "PAYMENT_OVERDUE", "payment": {"id": self.asaas.payment_id}}
        )
        AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})

        tx.refresh_from_db()
        assert tx.status == Transaction.Status.PAID


@override_settings(**ASAAS_SETTINGS)
class TestIdempotentTransactions(AsaasMockMixin, TestCase):
    def test_charge_twice_creates_single_transaction(self):
        user = make_user()
        order = create_order(user)
        AsaasGateway().charge(order, billing_type="PIX")
        AsaasGateway().charge(order, billing_type="PIX")
        assert order.transactions.filter(provider="asaas").count() == 1

    def test_checkout_twice_creates_single_transaction(self):
        user = make_user()
        order = create_order(user)
        AsaasGateway().create_checkout(order, charge_type="DETACHED")
        AsaasGateway().create_checkout(order, charge_type="DETACHED")
        assert order.transactions.filter(provider="asaas").count() == 1


class TestPaymentProviderCheck(TestCase):
    @override_settings(PAYMENT_PROVIDER="gateway-desconhecido")
    def test_unknown_provider_returns_error(self):
        errors = payment_provider_check(None)
        assert len(errors) == 1
        assert errors[0].id == "payments.E002"

    @override_settings(PAYMENT_PROVIDER="asaas")
    def test_known_provider_returns_empty(self):
        assert payment_provider_check(None) == []


@override_settings(**ASAAS_SETTINGS)
class TestAsaasCustomerData(AsaasMockMixin, TestCase):
    def test_customer_creation_sends_cpf_phone_and_address(self):
        user = make_user()
        user.cpf = "123.456.789-01"
        user.telefone = "(11) 99999-9999"
        user.save(update_fields=["cpf", "telefone"])
        Address.objects.create(
            user=user,
            street="Rua das Flores",
            number="123",
            city="São Paulo",
            state="SP",
            zip_code="01001-000",
        )
        order = create_order(user)
        AsaasGateway().charge(order, billing_type="PIX")

        post = next(
            c for c in self.asaas.calls if c["method"] == "POST" and c["url"].endswith("/customers")
        )
        body = post["body"]
        assert body["cpfCnpj"] == "12345678901"
        assert body["mobilePhone"] == "11999999999"
        assert body["address"] == "Rua das Flores"
        assert body["addressNumber"] == "123"
        assert body["province"] == "SP"
        assert body["city"] == "São Paulo"
        assert body["postalCode"] == "01001000"

    def test_missing_customer_fields_raise_friendly_error(self):
        user = make_user()  # sem CPF/telefone/endereço
        order = create_order(user)
        self.asaas.fail_customer_creation = True

        with self.assertRaisesRegex(ValueError, "cadastre CPF, telefone e endereço"):
            AsaasGateway().charge(order, billing_type="PIX")

    def test_checkout_customer_data_includes_cpf_and_address(self):
        user = make_user()
        user.cpf = "12345678901"
        user.save(update_fields=["cpf"])
        Address.objects.create(
            user=user,
            street="Av. Central",
            number="10",
            city="Recife",
            state="PE",
            zip_code="50000-000",
        )
        order = create_order(user)
        AsaasGateway().create_checkout(order, charge_type="DETACHED")

        call = next(
            c for c in self.asaas.calls if c["method"] == "POST" and c["url"].endswith("/checkouts")
        )
        customer_data = call["body"]["customerData"]
        assert customer_data["cpfCnpj"] == "12345678901"
        assert customer_data["postalCode"] == "50000000"
        assert customer_data["address"] == "Av. Central"
        assert customer_data["addressNumber"] == "10"
        assert customer_data["province"] == "PE"
        assert customer_data["city"] == "Recife"


@override_settings(**ASAAS_SETTINGS)
class TestCustomerCacheRetry(AsaasMockMixin, TestCase):
    def test_stale_customer_cache_is_cleared_and_retried(self):
        user = make_user()
        order = create_order(user)
        user.asaas_customer_id = "cus_antigo"
        user.save(update_fields=["asaas_customer_id"])
        self.asaas.fail_next = (
            400,
            {"errors": [{"code": "invalid_customer", "description": "Customer not found"}]},
        )

        result = AsaasGateway().charge(order, billing_type="PIX")

        assert result.ok is True
        user.refresh_from_db()
        assert user.asaas_customer_id == "cus_0001"
        assert order.transactions.filter(provider="asaas").count() == 1


@override_settings(**ASAAS_SETTINGS)
class TestTransactionKind(AsaasMockMixin, TestCase):
    def test_checkout_transaction_has_checkout_kind(self):
        user = make_user()
        order = create_order(user)
        AsaasGateway().create_checkout(order, charge_type="DETACHED")
        tx = order.transactions.get(provider="asaas")
        assert tx.kind == Transaction.Kind.CHECKOUT

    def test_charge_transaction_has_payment_kind(self):
        user = make_user()
        order = create_order(user)
        AsaasGateway().charge(order, billing_type="PIX")
        tx = order.transactions.get(provider="asaas")
        assert tx.kind == Transaction.Kind.PAYMENT

    def test_manual_transaction_has_payment_kind(self):
        user = make_user()
        order = create_order(user)
        ManualGateway().charge(order)
        txs = order.transactions.filter(provider="manual")
        assert txs.count() == 2
        assert all(tx.kind == Transaction.Kind.PAYMENT for tx in txs)


@override_settings(**ASAAS_SETTINGS)
class TestChargeResultSemantics(AsaasMockMixin, TestCase):
    def test_manual_charge_returns_transaction_id_and_empty_external_id(self):
        user = make_user()
        order = create_order(user)
        result = ManualGateway().charge(order)

        assert result.transaction_id
        assert result.external_id == ""
        tx = Transaction.objects.get(pk=result.transaction_id)
        assert tx.status == Transaction.Status.PENDING

    @override_settings(**ASAAS_SETTINGS)
    def test_asaas_charge_returns_transaction_id_and_external_id_on_model(self):
        user = make_user()
        order = create_order(user)
        result = AsaasGateway().charge(order, billing_type="PIX")

        assert result.transaction_id
        tx = Transaction.objects.get(pk=result.transaction_id)
        assert tx.external_id == self.asaas.payment_id
