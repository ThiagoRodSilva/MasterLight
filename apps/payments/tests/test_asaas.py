"""Testes do AsaasGateway: cobrança Pix/cartão, refund e webhook."""

import json
from datetime import date, timedelta

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.checkout.models import Order
from apps.payments.models import Transaction
from apps.payments.services import AsaasGateway, WebhookAuthError
from apps.services.models import MaintenancePlan
from apps.tests.helpers import AsaasMockMixin, create_order, make_user

ASAAS_SETTINGS = {
    "PAYMENT_PROVIDER": "asaas",
    "ASAAS_API_KEY": "teste-key",
    "ASAAS_SANDBOX": True,
    "ASAAS_WEBHOOK_TOKEN": "segredo",
}


def _make_plan(cliente, prestador=None):
    order = Order.objects.create(
        user=cliente, status=Order.Status.AWAITING_PAYMENT, kind=Order.Kind.SUBSCRIPTION
    )
    return MaintenancePlan.objects.create(
        plan_type="mensal",
        value="79.90",
        next_due_date=date.today() + timedelta(days=30),
        client=cliente,
        prestador=prestador,
        order=order,
    )


@override_settings(**ASAAS_SETTINGS)
class TestAsaasCharge(AsaasMockMixin, TestCase):
    def test_charge_pix_creates_transaction(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        gateway = AsaasGateway()
        result = gateway.charge(order, billing_type="PIX")

        assert result.ok is True
        assert result.status == Transaction.Status.PENDING
        tx = Transaction.objects.get(pk=result.external_id)
        assert tx.provider == "asaas"
        assert tx.external_id == self.asaas.payment_id
        assert tx.amount == order.total

        payload = json.loads(tx.raw_payload)
        assert payload["pix"]["payload"] == "00020126580014BR.GOV.BCB.PIX"

    def test_charge_creates_customer_once(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        gateway = AsaasGateway()
        gateway.charge(order)
        gateway.charge(order)

        create_customer_calls = [
            c for c in self.asaas.calls if c["method"] == "POST" and c["url"].endswith("/customers")
        ]
        assert len(create_customer_calls) == 1

    def test_charge_credit_card_requires_token(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        gateway = AsaasGateway()
        with self.assertRaisesRegex(ValueError, "creditCardToken"):
            gateway.charge(order, billing_type="CREDIT_CARD")

    def test_charge_credit_card_with_token(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        gateway = AsaasGateway()
        result = gateway.charge(
            order,
            billing_type="CREDIT_CARD",
            credit_card_token=self.asaas.card_token,
            remote_ip="127.0.0.1",
        )
        tx = Transaction.objects.get(pk=result.external_id)
        assert tx.status == Transaction.Status.PENDING
        request_body = None
        for call in self.asaas.calls:
            if call["method"] == "POST" and call["url"].endswith("/payments"):
                request_body = call["body"]
        assert request_body is not None
        assert request_body["creditCardToken"] == self.asaas.card_token

    def test_tokenize_credit_card_returns_token(self):
        from apps.checkout.models import Address

        user = make_user()
        Address.objects.create(
            user=user,
            street="Rua A",
            number="10",
            city="Cidade",
            state="SP",
            zip_code="01001000",
            country="BR",
        )
        user.cpf = "12345678901"
        user.telefone = "11999999999"
        user.save(update_fields=["cpf", "telefone"])
        token = AsaasGateway().tokenize_credit_card(
            user,
            card={
                "holder_name": "Fulano",
                "number": "4111111111111111",
                "expiry_month": "12",
                "expiry_year": "2030",
                "ccv": "123",
            },
            holder={
                "name": user.get_full_name() or user.email,
                "email": user.email,
                "cpf_cnpj": user.cpf,
                "phone": user.telefone,
                "postal_code": "01001000",
                "address_number": "10",
            },
            remote_ip="127.0.0.1",
        )
        assert token == "tok_0001"

    def test_charge_invalid_billing_type(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        with self.assertRaises(ValueError):
            AsaasGateway().charge(order, billing_type="BOLETO")

    def test_charge_pix_redirects_to_pix_confirm(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        result = AsaasGateway().charge(order, billing_type="PIX")
        assert result.redirect_url == reverse("payments-pix-confirm", args=[order.pk])

    def test_charge_credit_card_redirects_to_manual_confirm(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        result = AsaasGateway().charge(
            order, billing_type="CREDIT_CARD", credit_card_token=self.asaas.card_token
        )
        assert result.redirect_url == reverse("payments-manual-confirm", args=[order.pk])

    def test_customer_cpf_sanitized(self):
        user = make_user()
        user.cpf = "123.456.789-01"
        user.save(update_fields=["cpf"])
        AsaasGateway().charge(create_order(user, with_referral=False), billing_type="PIX")
        customers_call = next(
            c
            for c in self.asaas.calls
            if c["method"] == "POST" and c["url"].endswith("/customers")
        )
        assert customers_call["body"]["cpfCnpj"] == "12345678901"


@override_settings(**ASAAS_SETTINGS)
class TestAsaasWebhook(AsaasMockMixin, TestCase):
    def test_webhook_confirmed_marks_paid(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        AsaasGateway().charge(order)
        tx = order.transactions.get(provider="asaas")

        payload = json.dumps({"event": "PAYMENT_CONFIRMED", "payment": {"id": self.asaas.payment_id}})
        AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})

        tx.refresh_from_db()
        assert tx.status == Transaction.Status.PAID

    def test_webhook_invalid_token_raises(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        AsaasGateway().charge(order)

        payload = json.dumps({"event": "PAYMENT_CONFIRMED", "payment": {"id": self.asaas.payment_id}})
        with self.assertRaises(ValueError):
            AsaasGateway().webhook(payload, {"x-webhook-token": "errado"})

    def test_webhook_unknown_payment_raises(self):
        payload = json.dumps({"event": "PAYMENT_CONFIRMED", "payment": {"id": "outra-pay"}})
        with self.assertRaises(ValueError):
            AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})


@override_settings(**ASAAS_SETTINGS)
class TestPixConfirmationView(AsaasMockMixin, TestCase):
    def test_pix_confirmation_shows_qr(self):

        user = make_user()
        self.client.force_login(user)
        order = create_order(user, with_referral=False)
        AsaasGateway().charge(order, billing_type="PIX")

        response = self.client.get(reverse("payments-pix-confirm", kwargs={"order_pk": order.pk}))
        assert response.status_code == 200
        html = response.content.decode()
        assert "Pay with Pix" in html or "Pix" in html
        assert "base64png" in html

    def test_pix_confirmation_requires_own_order(self):
        from apps.accounts.models import CustomUser

        user = make_user()
        self.client.force_login(user)
        other = make_user(role=CustomUser.Role.AFILIADO)
        order = create_order(other, with_referral=False)

        response = self.client.get(reverse("payments-pix-confirm", kwargs={"order_pk": order.pk}))
        assert response.status_code == 404

    def test_refund_sets_refunded(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        tx_id = AsaasGateway().charge(order).external_id
        tx_not_refunded = Transaction.objects.get(pk=tx_id)

        result = AsaasGateway().refund(tx_not_refunded.pk, amount=order.total)

        assert result.ok is True
        tx_not_refunded.refresh_from_db()
        assert tx_not_refunded.status == Transaction.Status.REFUNDED

    def test_refund_untracked_returns_not_ok(self):
        from uuid import uuid4

        result = AsaasGateway().refund(str(uuid4()), amount=1)
        assert result.ok is False


@override_settings(**ASAAS_SETTINGS)
class TestAsaasSubscription(AsaasMockMixin, TestCase):
    def test_subscribe_pix_stores_qr(self):
        from apps.accounts.models import CustomUser

        prestador = make_user(role=CustomUser.Role.PRESTADOR)
        cliente = make_user(role=CustomUser.Role.CLIENTE)
        plan = _make_plan(cliente, prestador=prestador)
        result = AsaasGateway().subscribe(plan, billing_type="PIX")

        payload = json.loads(result.raw_payload)
        assert payload["pix"]["encodedImage"] == "base64png"
        tx = Transaction.objects.get(order=plan.order)
        tx_payload = json.loads(tx.raw_payload)
        assert tx_payload["pix"]["payload"].startswith("000201")

    def test_subscribe_credit_card_requires_token(self):
        from apps.accounts.models import CustomUser

        cliente = make_user(role=CustomUser.Role.CLIENTE)
        plan = _make_plan(cliente)
        with self.assertRaisesRegex(ValueError, "creditCardToken"):
            AsaasGateway().subscribe(plan, billing_type="CREDIT_CARD")

    def test_subscribe_without_first_payment_survives(self):
        from apps.accounts.models import CustomUser

        self.asaas.empty_subscription_payments = True
        cliente = make_user(role=CustomUser.Role.CLIENTE)
        plan = _make_plan(cliente)
        result = AsaasGateway().subscribe(plan, billing_type="PIX")
        assert result.ok is True
        payload = json.loads(result.raw_payload)
        assert payload["pix"] == {}
        tx = Transaction.objects.get(order=plan.order)
        assert tx.external_id == self.asaas.subscription_id


@override_settings(**ASAAS_SETTINGS)
class TestSubscriptionRenewalWebhook(AsaasMockMixin, TestCase):
    def setUp(self):
        super().setUp()
        from apps.accounts.models import CustomUser

        prestador = make_user(role=CustomUser.Role.PRESTADOR)
        cliente = make_user(role=CustomUser.Role.CLIENTE)
        self.plan = _make_plan(cliente, prestador=prestador)
        AsaasGateway().subscribe(self.plan, billing_type="PIX")
        # simula a confirmação da 1ª cobrança (ciclo 1 pago)
        first_payload = json.dumps(
            {
                "event": "PAYMENT_CONFIRMED",
                "payment": {"id": self.asaas.payment_id, "subscription": self.asaas.subscription_id},
            }
        )
        AsaasGateway().webhook(first_payload, {"x-webhook-token": "segredo"})
        self.plan.refresh_from_db()

    def _renew(self, payment_id, subscription_id=None):
        subscription = subscription_id or self.asaas.subscription_id
        payload = json.dumps(
            {
                "event": "PAYMENT_CONFIRMED",
                "payment": {
                    "id": payment_id,
                    "subscription": subscription,
                    "value": 79.9,
                },
            }
        )
        return AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})

    def test_renewal_creates_transaction_and_advances_plan(self):
        from apps.services.models import MaintenanceVisit

        due_after_first = self.plan.next_due_date
        result = self._renew(self.asaas.renewal_payment_id)

        assert result.ok is True
        tx = Transaction.objects.get(external_id=self.asaas.renewal_payment_id)
        assert tx.status == Transaction.Status.PAID
        assert tx.order == self.plan.order

        self.plan.refresh_from_db()
        assert self.plan.next_due_date == due_after_first + timedelta(days=30)
        visit = MaintenanceVisit.objects.get(plan=self.plan, scheduled_at__date=due_after_first)
        assert visit.scheduled_at.date() == due_after_first

    def test_renewal_duplicate_webhook_is_idempotent(self):
        from apps.services.models import MaintenanceVisit

        due_after_first = self.plan.next_due_date
        self._renew(self.asaas.renewal_payment_id)
        self._renew(self.asaas.renewal_payment_id)

        self.plan.refresh_from_db()
        assert self.plan.next_due_date == due_after_first + timedelta(days=30)
        assert MaintenanceVisit.objects.filter(plan=self.plan).count() == 2
        assert Transaction.objects.filter(external_id=self.asaas.renewal_payment_id).count() == 1

    def test_renewal_unknown_subscription_raises(self):
        with self.assertRaisesRegex(ValueError, "encontrada"):
            self._renew(self.asaas.renewal_payment_id, subscription_id="sub_desconhecida")


@override_settings(**ASAAS_SETTINGS)
class TestAsaasWebhookTokenEnforced(AsaasMockMixin, TestCase):
    def test_webhook_requires_configured_token(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        AsaasGateway().charge(order, billing_type="PIX")
        payload = json.dumps({"event": "PAYMENT_CONFIRMED", "payment": {"id": self.asaas.payment_id}})
        with override_settings(ASAAS_WEBHOOK_TOKEN=""):
            with self.assertRaises(WebhookAuthError):
                AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})
