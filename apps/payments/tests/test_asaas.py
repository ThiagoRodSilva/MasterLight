"""Testes do AsaasGateway: cobrança Pix/cartão, refund e webhook."""

import json
from decimal import Decimal
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.payments.models import Transaction
from apps.payments.services import AsaasGateway, WebhookAuthError
from apps.tests.helpers import AsaasMockMixin, create_order, make_user

ASAAS_SETTINGS = {
    "PAYMENT_PROVIDER": "asaas",
    "ASAAS_API_KEY": "teste-key",
    "ASAAS_SANDBOX": True,
    "ASAAS_WEBHOOK_TOKEN": "segredo",
}


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
            c for c in self.asaas.calls if c["method"] == "POST" and c["url"].endswith("/customers")
        )
        assert customers_call["body"]["cpfCnpj"] == "12345678901"

    def test_customer_gets_phone_and_no_notification(self):
        user = make_user()
        user.cpf = "12345678901"
        user.telefone = "(11) 99999-9999"
        user.save(update_fields=["cpf", "telefone"])
        AsaasGateway().charge(create_order(user, with_referral=False), billing_type="PIX")
        customers_call = next(
            c for c in self.asaas.calls if c["method"] == "POST" and c["url"].endswith("/customers")
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

        payload = json.dumps(
            {"event": "PAYMENT_CONFIRMED", "payment": {"id": self.asaas.payment_id}}
        )
        AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})

        tx.refresh_from_db()
        assert tx.status == Transaction.Status.PAID

    def test_webhook_received_marks_paid(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        AsaasGateway().charge(order)
        tx = order.transactions.get(provider="asaas")
        payload = json.dumps(
            {"event": "PAYMENT_RECEIVED", "payment": {"id": self.asaas.payment_id}}
        )
        AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})

        tx.refresh_from_db()
        assert tx.status == Transaction.Status.PAID

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
        payload = json.dumps(
            {"event": "PAYMENT_AUTHORIZED", "payment": {"id": self.asaas.payment_id}}
        )
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
            {
                "event": "PAYMENT_CREDIT_CARD_CAPTURE_CANCELLED",
                "payment": {"id": self.asaas.payment_id},
            }
        )
        AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})
        tx.refresh_from_db()
        assert tx.status == Transaction.Status.FAILED

    def test_webhook_invalid_token_raises(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        AsaasGateway().charge(order)

        payload = json.dumps(
            {"event": "PAYMENT_CONFIRMED", "payment": {"id": self.asaas.payment_id}}
        )
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
        payload = json.dumps(
            {"event": "PAYMENT_RECEIVED", "payment": {"id": self.asaas.payment_id}}
        )
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
            {
                "event": "PAYMENT_CREDIT_CARD_CAPTURE_REFUSED",
                "payment": {"id": self.asaas.payment_id},
            }
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


@override_settings(**ASAAS_SETTINGS)
class TestAsaasWebhookTokenEnforced(AsaasMockMixin, TestCase):
    def test_webhook_requires_configured_token(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        AsaasGateway().charge(order, billing_type="PIX")
        payload = json.dumps(
            {"event": "PAYMENT_CONFIRMED", "payment": {"id": self.asaas.payment_id}}
        )
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

    def test_create_checkout_rejects_invalid_billing(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        with self.assertRaises(ValueError):
            AsaasGateway().create_checkout(order, billing_types=["CHEQUE"])

    def test_checkout_paid_webhook_marks_paid(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        AsaasGateway().create_checkout(order)
        tx = order.transactions.get(provider="asaas")

        payload = json.dumps({"event": "CHECKOUT_PAID", "checkout": {"id": self.asaas.checkout_id}})
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
                    "id": "pay_extra_0001",
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
