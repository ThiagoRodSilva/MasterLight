"""Testes do AsaasGateway: cobrança Pix/cartão, refund e webhook."""

import json
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import CustomUser
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
        tx = Transaction.objects.get(pk=result.transaction_id)
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
        tx = Transaction.objects.get(pk=result.transaction_id)
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
            AsaasGateway().charge(order, billing_type="CHEQUE")



    def test_charge_pix_redirects_to_pix_confirm(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        result = AsaasGateway().charge(order, billing_type="PIX")
        assert result.redirect_url == reverse("payments-pix-confirm", args=[order.pk])

    def test_charge_credit_card_redirects_to_card_confirm(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        result = AsaasGateway().charge(
            order, billing_type="CREDIT_CARD", credit_card_token=self.asaas.card_token
        )
        assert result.redirect_url == reverse("payments-card-confirm", args=[order.pk])

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

    def test_customer_gets_phone_and_no_notification(self):
        user = make_user()
        user.cpf = "12345678901"
        user.telefone = "(11) 99999-9999"
        user.save(update_fields=["cpf", "telefone"])
        AsaasGateway().charge(create_order(user, with_referral=False), billing_type="PIX")
        customers_call = next(
            c
            for c in self.asaas.calls
            if c["method"] == "POST" and c["url"].endswith("/customers")
        )
        assert customers_call["body"]["mobilePhone"] == "11999999999"
        assert customers_call["body"]["notificationDisabled"] is True

    def test_charge_value_sent_as_decimal_string(self):
        user = make_user()
        order = create_order(user, with_referral=False, qty=2)
        AsaasGateway().charge(order, billing_type="PIX")
        payment_call = next(
            c for c in self.asaas.calls if c["method"] == "POST" and c["url"].endswith("/payments")
        )
        assert payment_call["body"]["value"] == f"{order.total:.2f}"
        assert isinstance(payment_call["body"]["value"], str)

    def test_charge_sends_idempotency_key(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        AsaasGateway().charge(order, billing_type="PIX")
        payment_call = next(
            c for c in self.asaas.calls if c["method"] == "POST" and c["url"].endswith("/payments")
        )
        assert payment_call["headers"].get("X-Idempotency-Key") == f"order-{order.pk}"

    def test_charge_retries_on_5xx(self):
        self.asaas.fail_5xx = 2
        user = make_user()
        order = create_order(user, with_referral=False)
        with mock.patch("apps.payments.gateways.asaas_client.time.sleep"):
            result = AsaasGateway().charge(order, billing_type="PIX")
        assert result.ok is True

    def test_charge_pix_survives_missing_qr(self):
        self.asaas.pix_missing = True
        user = make_user()
        order = create_order(user, with_referral=False)
        result = AsaasGateway().charge(order, billing_type="PIX")
        assert result.ok is True
        tx = Transaction.objects.get(pk=result.transaction_id)
        assert json.loads(tx.raw_payload)["pix"] == {}


@override_settings(**ASAAS_SETTINGS)
class TestAsaasWebhook(AsaasMockMixin, TestCase):
    def test_webhook_confirmed_marks_paid(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        AsaasGateway().charge(order)
        tx = order.transactions.get(provider="asaas")
        tx.refresh_from_db()
        assert tx.status == Transaction.Status.PENDING

        payload = json.dumps({"event": "PAYMENT_CONFIRMED", "payment": {"id": self.asaas.payment_id}})
        AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})

        tx.refresh_from_db()
        assert tx.status == Transaction.Status.PAID

    def test_webhook_received_marks_paid(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        AsaasGateway().charge(order)
        tx = order.transactions.get(provider="asaas")
        payload = json.dumps({"event": "PAYMENT_RECEIVED", "payment": {"id": self.asaas.payment_id}})
        AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})

        tx.refresh_from_db()
        assert tx.status == Transaction.Status.PAID

    def test_checkout_recurrent_links_subscription_via_payments_fallback(self):
        from apps.accounts.models import CustomUser
        from apps.checkout.models import OrderItem

        cliente = make_user(role=CustomUser.Role.CLIENTE)
        plan = _make_plan(cliente)
        OrderItem.objects.create(
            order=plan.order,
            name="Plano mensal",
            qty=1,
            unit_price=plan.value,
        )
        plan.order.recompute_total()
        AsaasGateway().create_checkout(plan.order, charge_type="RECURRENT", cycle="mensal")
        assert plan.asaas_subscription_id == ""

        # GET /checkouts/{id} indisponível (endpoint não documentado pelo Asaas):
        # cai no fallback GET /payments?externalReference=<order.pk>.
        self.asaas.fail_next = (404, {"errors": [{"description": "not found"}]})
        payload = json.dumps(
            {"event": "CHECKOUT_PAID", "checkout": {"id": self.asaas.checkout_id}}
        )
        result = AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})
        assert result.ok is True

        plan.refresh_from_db()
        assert plan.asaas_subscription_id == self.asaas.subscription_id

    def test_checkout_unknown_event_ignored_without_transition(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        AsaasGateway().create_checkout(order)
        tx = order.transactions.get(provider="asaas")
        payload = json.dumps(
            {"event": "CHECKOUT_EVENTO_INVENTADO", "checkout": {"id": self.asaas.checkout_id}}
        )
        result = AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})
        assert result.ok is True
        tx.refresh_from_db()
        assert tx.status == Transaction.Status.PENDING
    def test_webhook_authorized_does_not_mark_paid(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        AsaasGateway().charge(order)
        tx = order.transactions.get(provider="asaas")
        payload = json.dumps({"event": "PAYMENT_AUTHORIZED", "payment": {"id": self.asaas.payment_id}})
        AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})
        tx.refresh_from_db()
        assert tx.status == Transaction.Status.AUTHORIZED

    def test_webhook_due_is_informational_and_keeps_pending(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        AsaasGateway().charge(order)
        tx = order.transactions.get(provider="asaas")
        payload = json.dumps({"event": "PAYMENT_DUE", "payment": {"id": self.asaas.payment_id}})
        result = AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})
        assert result.ok is True
        assert "informativo" in result.message
        tx.refresh_from_db()
        assert tx.status == Transaction.Status.PENDING

    def test_webhook_capture_cancelled_marks_failed(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        AsaasGateway().charge(order, billing_type="PIX")
        tx = order.transactions.get(provider="asaas")
        payload = json.dumps(
            {"event": "PAYMENT_CREDIT_CARD_CAPTURE_CANCELLED", "payment": {"id": self.asaas.payment_id}}
        )
        AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})
        tx.refresh_from_db()
        assert tx.status == Transaction.Status.FAILED

    def test_webhook_invalid_token_raises(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        AsaasGateway().charge(order)

        payload = json.dumps({"event": "PAYMENT_CONFIRMED", "payment": {"id": self.asaas.payment_id}})
        with self.assertRaises(ValueError):
            AsaasGateway().webhook(payload, {"x-webhook-token": "errado"})

    def test_webhook_unknown_payment_is_ignored_without_404(self):
        payload = json.dumps({"event": "PAYMENT_CONFIRMED", "payment": {"id": "outra-pay"}})
        result = AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})
        assert result.ok is True
        assert "sem transação local" in result.message

    def test_webhook_accepts_asaas_access_token_header(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        AsaasGateway().charge(order)
        tx = order.transactions.get(provider="asaas")
        payload = json.dumps({"event": "PAYMENT_RECEIVED", "payment": {"id": self.asaas.payment_id}})
        result = AsaasGateway().webhook(payload, {"asaas-access-token": "segredo"})
        assert result.ok is True
        tx.refresh_from_db()
        assert tx.status == Transaction.Status.PAID

    def test_webhook_unknown_event_is_ignored_without_transition(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        AsaasGateway().charge(order)
        tx = order.transactions.get(provider="asaas")
        payload = json.dumps(
            {"event": "PAYMENT_EVENTO_INVENTADO", "payment": {"id": self.asaas.payment_id}}
        )
        result = AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})
        assert result.ok is True
        tx.refresh_from_db()
        assert tx.status == Transaction.Status.PENDING

    def test_webhook_credit_card_capture_refused_marks_failed(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        AsaasGateway().charge(order, billing_type="PIX")
        tx = order.transactions.get(provider="asaas")
        payload = json.dumps(
            {"event": "PAYMENT_CREDIT_CARD_CAPTURE_REFUSED", "payment": {"id": self.asaas.payment_id}}
        )
        AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})
        tx.refresh_from_db()
        assert tx.status == Transaction.Status.FAILED


@override_settings(**ASAAS_SETTINGS)
class TestPixConfirmationView(AsaasMockMixin, TestCase):
    def test_pix_confirmation_shows_qr(self):

        user = make_user(role=CustomUser.Role.CLIENTE)
        self.client.force_login(user)
        order = create_order(user, with_referral=False)
        AsaasGateway().charge(order, billing_type="PIX")

        response = self.client.get(reverse("payments-pix-confirm", kwargs={"order_pk": order.pk}))
        assert response.status_code == 200
        html = response.content.decode()
        assert "Pay with Pix" in html or "Pix" in html
        assert "base64png" in html

    def test_pix_confirmation_requires_own_order(self):
        user = make_user()
        self.client.force_login(user)
        other = make_user()
        order = create_order(other, with_referral=False)

        response = self.client.get(reverse("payments-pix-confirm", kwargs={"order_pk": order.pk}))
        assert response.status_code == 404

    def test_refund_sets_refunded(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        tx_id = AsaasGateway().charge(order).transaction_id
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
class TestAsaasPaymentLink(AsaasMockMixin, TestCase):
    def test_create_payment_link_with_value_returns_url(self):
        from apps.payments.services import create_payment_link

        result = create_payment_link(
            name="Orçamento — Instalação",
            value=Decimal("99.90"),
            description="Orçamento de Instalação",
            billing_type="UNDEFINED",
            charge_type="DETACHED",
            external_reference="abc-123",
        )

        assert result.ok is True
        assert result.url == self.asaas.payment_link_url
        assert result.link_id == self.asaas.payment_link_id

        link_call = next(
            c
            for c in self.asaas.calls
            if c["method"] == "POST" and c["url"].endswith("/paymentLinks")
        )
        assert link_call["body"]["name"] == "Orçamento — Instalação"
        assert link_call["body"]["value"] == "99.90"
        assert link_call["body"]["billingType"] == "UNDEFINED"
        assert link_call["body"]["chargeType"] == "DETACHED"
        assert link_call["body"]["externalReference"] == "abc-123"

    def test_create_payment_link_without_value(self):
        from apps.payments.services import create_payment_link

        result = create_payment_link(name="Valor aberto", billing_type="PIX")
        assert result.ok is True
        link_call = next(
            c
            for c in self.asaas.calls
            if c["method"] == "POST" and c["url"].endswith("/paymentLinks")
        )
        assert "value" not in link_call["body"]
        assert link_call["body"]["billingType"] == "PIX"

    def test_create_payment_link_rejects_invalid_billing_type(self):
        from apps.payments.services import create_payment_link

        with self.assertRaises(ValueError):
            create_payment_link(name="X", value=10, billing_type="DEPOSIT")

    def test_create_payment_link_rejects_invalid_charge_type(self):
        from apps.payments.services import create_payment_link

        with self.assertRaises(ValueError):
            create_payment_link(name="X", value=10, charge_type="AVULSA")

    def test_create_payment_link_manual_provider_raises(self):
        from apps.payments.services import create_payment_link

        with override_settings(PAYMENT_PROVIDER="manual"):
            with self.assertRaisesRegex(ValueError, "provider 'asaas'"):
                create_payment_link(name="X", value=10)


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

    def test_renewal_unknown_subscription_is_ignored_without_404(self):
        result = self._renew(self.asaas.renewal_payment_id, subscription_id="sub_desconhecida")
        assert result.ok is True
        assert "sem transação local" in result.message
        assert not Transaction.objects.filter(external_id=self.asaas.renewal_payment_id).exists()

    def test_renewal_links_subscription_via_external_reference(self):
        from apps.accounts.models import CustomUser

        # Plano criado por Checkout RECURRENT sem asaas_subscription_id vinculado.
        prestador = make_user(role=CustomUser.Role.PRESTADOR)
        cliente = make_user(role=CustomUser.Role.CLIENTE)
        plan = _make_plan(cliente, prestador=prestador)
        assert plan.asaas_subscription_id == ""

        payload = json.dumps(
            {
                "event": "PAYMENT_RECEIVED",
                "payment": {
                    "id": self.asaas.renewal_payment_id,
                    "subscription": "sub_checkout",
                    "externalReference": str(plan.order.pk),
                    "value": 79.9,
                },
            }
        )
        result = AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})
        assert result.ok is True

        plan.refresh_from_db()
        assert plan.asaas_subscription_id == "sub_checkout"
        tx = Transaction.objects.get(external_id=self.asaas.renewal_payment_id)
        assert tx.order == plan.order
        assert tx.status == Transaction.Status.PAID


@override_settings(**ASAAS_SETTINGS)
class TestSubscriptionCreatedWebhook(AsaasMockMixin, TestCase):
    def setUp(self):
        super().setUp()
        from apps.accounts.models import CustomUser

        prestador = make_user(role=CustomUser.Role.PRESTADOR)
        self.cliente = make_user(role=CustomUser.Role.CLIENTE)
        self.plan = _make_plan(self.cliente, prestador=prestador)
        self.tx = Transaction.objects.create(
            order=self.plan.order,
            user=self.cliente,
            provider="asaas",
            external_id=self.asaas.checkout_id,
            amount=self.plan.value,
            status=Transaction.Status.PENDING,
            kind=Transaction.Kind.CHECKOUT,
        )

    def _payload(self, event="SUBSCRIPTION_CREATED", **subscription_overrides):
        subscription = {
            "object": "subscription",
            "id": "sub_ep6iuav2bfxm78cl",
            "customer": "cus_000008710825",
            "value": 79.9,
            "cycle": "MONTHLY",
            "billingType": "CREDIT_CARD",
            "status": "ACTIVE",
            "checkoutSession": self.asaas.checkout_id,
            **subscription_overrides,
        }
        return json.dumps(
            {
                "id": "evt_6561b631fa5580caadd00bbe3b858607&18071956",
                "event": event,
                "subscription": subscription,
            }
        )

    def test_subscription_created_links_plan_via_checkout_session(self):
        result = AsaasGateway().webhook(self._payload(), {"x-webhook-token": "segredo"})
        assert result.ok is True
        self.plan.refresh_from_db()
        assert self.plan.asaas_subscription_id == "sub_ep6iuav2bfxm78cl"
        self.tx.refresh_from_db()
        assert self.tx.status == Transaction.Status.PENDING

    def test_subscription_created_idempotent_when_already_linked(self):
        self.plan.asaas_subscription_id = "sub_ep6iuav2bfxm78cl"
        self.plan.save(update_fields=["asaas_subscription_id", "updated_at"])
        result = AsaasGateway().webhook(self._payload(), {"x-webhook-token": "segredo"})
        assert result.ok is True
        self.plan.refresh_from_db()
        assert self.plan.asaas_subscription_id == "sub_ep6iuav2bfxm78cl"

    def test_subscription_created_without_plan_returns_ok(self):
        result = AsaasGateway().webhook(
            self._payload(checkoutSession="chk_sem_vinculo"), {"x-webhook-token": "segredo"}
        )
        assert result.ok is True

    def test_subscription_deleted_event_ignored_without_transition(self):
        result = AsaasGateway().webhook(
            self._payload(event="SUBSCRIPTION_DELETED"), {"x-webhook-token": "segredo"}
        )
        assert result.ok is True
        self.tx.refresh_from_db()
        assert self.tx.status == Transaction.Status.PENDING


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


@override_settings(**ASAAS_SETTINGS)
class TestSyncPaymentsCommand(AsaasMockMixin, TestCase):
    def test_command_reconciles_pending_transaction(self):
        from django.core.management import call_command

        user = make_user()
        order = create_order(user, with_referral=False)
        AsaasGateway().charge(order, billing_type="PIX")
        tx = order.transactions.get(provider="asaas")
        assert tx.status == Transaction.Status.PENDING

        self.asaas.customer_status = "CONFIRMED"
        call_command("sync_payments")

        tx.refresh_from_db()
        assert tx.status == Transaction.Status.PAID

    def test_command_maps_customer_requested_cancellation_to_failed(self):
        from django.core.management import call_command

        self.asaas.customer_status = "CUSTOMER_REQUESTED_CANCELLATION"
        user = make_user()
        order = create_order(user, with_referral=False)
        AsaasGateway().charge(order, billing_type="PIX")
        tx = order.transactions.get(provider="asaas")

        call_command("sync_payments")

        tx.refresh_from_db()
        assert tx.status == Transaction.Status.FAILED

    def test_command_preserves_truly_unknown_status(self):
        from django.core.management import call_command

        self.asaas.customer_status = "STATUS_INVENTADO_PELO_ASAAS"
        user = make_user()
        order = create_order(user, with_referral=False)
        AsaasGateway().charge(order, billing_type="PIX")
        tx = order.transactions.get(provider="asaas")

        call_command("sync_payments")

        tx.refresh_from_db()
        assert tx.status == Transaction.Status.PENDING


@override_settings(**ASAAS_SETTINGS)
class TestAsaasCheckout(AsaasMockMixin, TestCase):
    def test_create_checkout_creates_transaction_with_checkout_id(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        result = AsaasGateway().create_checkout(order)

        assert result.ok is True
        assert result.url == self.asaas.checkout_url
        assert result.checkout_id == self.asaas.checkout_id

        tx = Transaction.objects.get(order=order, provider="asaas")
        assert tx.provider == "asaas"
        assert tx.external_id == self.asaas.checkout_id
        assert tx.status == Transaction.Status.PENDING
        assert json.loads(tx.raw_payload)["checkout"]["id"] == self.asaas.checkout_id

    def test_create_checkout_sends_items_customer_and_callback(self):
        user = make_user()
        user.cpf = "12345678901"
        user.telefone = "11999999999"
        user.save(update_fields=["cpf", "telefone"])
        order = create_order(user, with_referral=False)
        AsaasGateway().create_checkout(
            order,
            billing_types=["PIX", "CREDIT_CARD"],
            callback_urls={
                "successUrl": "https://exemplo.com/ok",
                "cancelUrl": "https://exemplo.com/cancel",
            },
        )

        checkout_call = next(
            c for c in self.asaas.calls if c["method"] == "POST" and c["url"].endswith("/checkouts")
        )
        body = checkout_call["body"]
        assert body["billingTypes"] == ["PIX", "CREDIT_CARD"]
        assert body["chargeTypes"] == ["DETACHED"]
        assert body["externalReference"] == str(order.pk)
        assert body["items"][0]["name"] == order.items.first().name
        assert body["items"][0]["quantity"] == order.items.first().qty
        assert body["customerData"]["cpfCnpj"] == "12345678901"
        assert body["customerData"]["phone"] == "11999999999"
        assert body["callback"]["successUrl"] == "https://exemplo.com/ok"

    def test_create_checkout_recurrent_sends_subscription(self):
        from apps.accounts.models import CustomUser
        from apps.checkout.models import OrderItem

        cliente = make_user(role=CustomUser.Role.CLIENTE)
        plan = _make_plan(cliente)
        OrderItem.objects.create(
            order=plan.order,
            name="Plano mensal",
            qty=1,
            unit_price=plan.value,
        )
        plan.order.recompute_total()
        result = AsaasGateway().create_checkout(
            plan.order,
            charge_type="RECURRENT",
            cycle="mensal",
            next_due_date=date.today() + timedelta(days=30),
        )
        assert result.ok is True
        checkout_call = next(
            c for c in self.asaas.calls if c["method"] == "POST" and c["url"].endswith("/checkouts")
        )
        assert checkout_call["body"]["chargeTypes"] == ["RECURRENT"]
        assert checkout_call["body"]["billingTypes"] == ["CREDIT_CARD"]
        assert checkout_call["body"]["subscription"]["cycle"] == "MONTHLY"

    def test_create_checkout_recurrent_forces_credit_card_ignoring_pix(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        result = AsaasGateway().create_checkout(
            order,
            billing_types=["PIX"],
            charge_type="RECURRENT",
            cycle="mensal",
        )
        assert result.ok is True
        checkout_call = next(
            c for c in self.asaas.calls if c["method"] == "POST" and c["url"].endswith("/checkouts")
        )
        assert checkout_call["body"]["billingTypes"] == ["CREDIT_CARD"]
        assert "PIX" not in checkout_call["body"]["billingTypes"]

    def test_fake_rejects_recurrent_with_pix(self):
        response = self.asaas(
            "POST",
            "https://api.asaas.com/api/v3/checkouts",
            {},
            {"billingTypes": ["PIX", "CREDIT_CARD"], "chargeTypes": ["RECURRENT"]},
        )
        assert response.status_code == 400
        assert response.ok is False

    def test_create_checkout_rejects_invalid_billing(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        with self.assertRaises(ValueError):
            AsaasGateway().create_checkout(order, billing_types=["CHEQUE"])

    def test_manual_provider_raises_on_checkout(self):
        from apps.payments.services import ManualGateway

        with override_settings(PAYMENT_PROVIDER="manual"):
            with self.assertRaisesRegex(ValueError, "provider 'asaas'"):
                ManualGateway().create_checkout(None)

    def test_checkout_paid_webhook_marks_paid(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        AsaasGateway().create_checkout(order)
        tx = order.transactions.get(provider="asaas")

        payload = json.dumps(
            {"event": "CHECKOUT_PAID", "checkout": {"id": self.asaas.checkout_id}}
        )
        AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})

        tx.refresh_from_db()
        assert tx.status == Transaction.Status.PAID

    def test_checkout_expired_webhook_marks_failed(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        AsaasGateway().create_checkout(order)
        tx = order.transactions.get(provider="asaas")

        payload = json.dumps(
            {"event": "CHECKOUT_EXPIRED", "checkout": {"id": self.asaas.checkout_id}}
        )
        AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})

        tx.refresh_from_db()
        assert tx.status == Transaction.Status.FAILED

    def test_checkout_webhook_fallback_by_external_reference(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        AsaasGateway().create_checkout(order)
        tx = order.transactions.get(provider="asaas")
        tx.external_id = ""
        tx.save(update_fields=["external_id"])

        payload = json.dumps(
            {
                "event": "CHECKOUT_PAID",
                "checkout": {
                    "id": self.asaas.checkout_id,
                    "externalReference": str(order.pk),
                },
            }
        )
        AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})

        tx.refresh_from_db()
        assert tx.status == Transaction.Status.PAID

    def test_payment_confirmed_for_checkout_resolves_via_external_reference(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        AsaasGateway().create_checkout(order)
        tx = order.transactions.get(provider="asaas")

        payload = json.dumps(
            {
                "event": "PAYMENT_CONFIRMED",
                "payment": {
                    "id": self.asaas.renewal_payment_id,
                    "externalReference": str(order.pk),
                },
            }
        )
        result = AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})

        assert result.ok is True
        tx.refresh_from_db()
        assert tx.status == Transaction.Status.PAID


@override_settings(**ASAAS_SETTINGS)
class TestCheckoutCallbackView(AsaasMockMixin, TestCase):
    def test_callback_success_renders(self):

        user = make_user()
        self.client.force_login(user)
        order = create_order(user, with_referral=False)
        response = self.client.get(
            reverse(
                "payments-checkout-callback",
                kwargs={"order_pk": order.pk, "outcome": "success"},
            )
        )
        assert response.status_code == 200
        assert "Pagamento concluído" in response.content.decode()

    def test_callback_requires_own_order(self):
        from apps.accounts.models import CustomUser

        user = make_user()
        self.client.force_login(user)
        other = make_user(role=CustomUser.Role.AFILIADO)
        order = create_order(other, with_referral=False)
        response = self.client.get(
            reverse(
                "payments-checkout-callback",
                kwargs={"order_pk": order.pk, "outcome": "cancel"},
            )
        )
        assert response.status_code == 404


@override_settings(**ASAAS_SETTINGS)
class TestSyncPaymentsSkipsCheckout(AsaasMockMixin, TestCase):
    def test_command_skips_checkout_transactions(self):
        from django.core.management import call_command

        user = make_user()
        order = create_order(user, with_referral=False)
        AsaasGateway().create_checkout(order)
        tx = order.transactions.get(provider="asaas")
        assert tx.external_id == self.asaas.checkout_id

        call_command("sync_payments")

        tx.refresh_from_db()
        assert tx.status == Transaction.Status.PENDING
