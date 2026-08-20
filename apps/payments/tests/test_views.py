"""Testes do app de pagamentos (webhook + gateway manual)."""

import json

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.payments.models import Transaction
from apps.payments.services import ManualGateway
from apps.tests.helpers import create_order, make_user

WEBHOOK_TOKEN = "segredo-manual"


@override_settings(MANUAL_WEBHOOK_TOKEN=WEBHOOK_TOKEN)
class TestManualGatewayWebhook(TestCase):
    def test_charge_creates_pending_transaction(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        gateway = ManualGateway()
        result = gateway.charge(order)
        assert result.ok is True
        tx = Transaction.objects.get(pk=result.transaction_id)
        assert tx.status == Transaction.Status.PENDING
        assert tx.amount == order.total

    def test_webhook_marks_paid_with_token(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        tx = order.transactions.first()
        result = ManualGateway().webhook(
            json.dumps({"transaction_id": str(tx.pk), "status": "paid"}),
            {"x-webhook-token": WEBHOOK_TOKEN},
        )
        assert result.ok is True
        tx.refresh_from_db()
        assert tx.status == Transaction.Status.PAID

    def test_webhook_invalid_json_raises(self):
        with self.assertRaises(ValueError):
            ManualGateway().webhook("not json", {"x-webhook-token": WEBHOOK_TOKEN})

    def test_webhook_invalid_uuid_raises(self):
        with self.assertRaises(ValueError):
            ManualGateway().webhook(
                json.dumps({"transaction_id": "abc", "status": "paid"}),
                {"x-webhook-token": WEBHOOK_TOKEN},
            )

    def test_webhook_missing_status_raises(self):
        with self.assertRaises(ValueError):
            ManualGateway().webhook(
                json.dumps({"transaction_id": "x"}),
                {"x-webhook-token": WEBHOOK_TOKEN},
            )

    def test_charge_redirects_to_manual_confirm(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        result = ManualGateway().charge(order)
        expected = reverse("payments-manual-confirm", args=[order.pk])
        assert result.redirect_url == expected


@override_settings(MANUAL_WEBHOOK_TOKEN=WEBHOOK_TOKEN)
class TestWebhookManualAuth(TestCase):
    def test_webhook_manual_requires_valid_token(self):
        for headers in ({}, {"x-webhook-token": "errado"}):
            with self.subTest(headers=headers):
                user = make_user()
                order = create_order(user, with_referral=False)
                tx = order.transactions.first()
                with self.assertRaises(ValueError):
                    ManualGateway().webhook(
                        json.dumps({"transaction_id": str(tx.pk), "status": "paid"}), headers
                    )


@override_settings(MANUAL_WEBHOOK_TOKEN=WEBHOOK_TOKEN)
class TestWebhookView(TestCase):
    def _post(self, payload, content_type="application/json", token=WEBHOOK_TOKEN):
        return self.client.post(
            reverse("payments-webhook"),
            data=json.dumps(payload),
            content_type=content_type,
            HTTP_X_WEBHOOK_TOKEN=token,
        )

    def test_webhook_paid_marks_transaction(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        tx = order.transactions.first()
        response = self._post({"transaction_id": str(tx.pk), "status": "paid"})
        assert response.status_code == 200
        tx.refresh_from_db()
        assert tx.status == Transaction.Status.PAID

    def test_webhook_missing_token_returns_401(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        tx = order.transactions.first()
        response = self._post({"transaction_id": str(tx.pk), "status": "paid"}, token="")
        assert response.status_code == 401

    def test_webhook_bad_json_returns_400(self):
        response = self.client.post(
            reverse("payments-webhook"),
            data="não-json",
            content_type="application/json",
            HTTP_X_WEBHOOK_TOKEN=WEBHOOK_TOKEN,
        )
        assert response.status_code == 400

    def test_webhook_unknown_tx_returns_404(self):
        from uuid import uuid4

        response = self._post({"transaction_id": str(uuid4()), "status": "paid"})
        assert response.status_code == 404

    def test_webhook_invalid_uuid_returns_400(self):
        response = self._post({"transaction_id": "abc", "status": "paid"})
        assert response.status_code == 400

    def test_webhook_allowed_without_csrf(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        tx = order.transactions.first()
        client = Client(enforce_csrf_checks=True)
        response = client.post(
            reverse("payments-webhook"),
            data=json.dumps({"transaction_id": str(tx.pk), "status": "paid"}),
            content_type="application/json",
            HTTP_X_WEBHOOK_TOKEN=WEBHOOK_TOKEN,
        )
        assert response.status_code == 200


ASAAS_WEBHOOK_SETTINGS = {
    "PAYMENT_PROVIDER": "asaas",
    "ASAAS_WEBHOOK_TOKEN": "segredo",
    "ASAAS_SANDBOX": True,
}


@override_settings(**ASAAS_WEBHOOK_SETTINGS)
class TestAsaasWebhookView(TestCase):
    def _post(self, payload, token="segredo"):
        return self.client.post(
            reverse("payments-webhook"),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_WEBHOOK_TOKEN=token,
        )

    def test_unknown_payment_returns_200_not_404(self):
        response = self._post({"event": "PAYMENT_CONFIRMED", "payment": {"id": "pay_xpto"}})
        assert response.status_code == 200

    def test_subscription_created_returns_200(self):
        payload = {
            "event": "SUBSCRIPTION_CREATED",
            "subscription": {"id": "sub_0001", "status": "ACTIVE", "checkoutSession": "chk_0001"},
        }
        response = self._post(payload)
        assert response.status_code == 200

    def test_missing_token_returns_401(self):
        response = self._post({"event": "PAYMENT_CONFIRMED", "payment": {"id": "pay_xpto"}}, token="")
        assert response.status_code == 401


class TestManualConfirmationView(TestCase):
    def test_manual_tokenize_credit_card_raises(self):
        user = make_user(
            cpf="12345678901",
            telefone="11999999999",
            address={"street": "Rua Teste", "number": "123", "city": "São Paulo", "state": "SP", "zip_code": "01234567"},
        )
        gateway = ManualGateway()
        with self.assertRaisesRegex(ValueError, "asaas"):
            gateway.tokenize_credit_card(user, card={}, holder={})

    def test_manual_confirm_200_for_owner(self):
        user = make_user(
            cpf="12345678901",
            telefone="11999999999",
            address={"street": "Rua Teste", "number": "123", "city": "São Paulo", "state": "SP", "zip_code": "01234567"},
        )
        self.client.force_login(user)
        order = create_order(user, with_referral=False)
        response = self.client.get(reverse("payments-manual-confirm", kwargs={"order_pk": order.pk}))
        assert response.status_code == 200
        assert str(order.pk)[:5] in response.content.decode()

    def test_manual_confirm_404_other_user(self):
        user = make_user(
            cpf="12345678901",
            telefone="11999999999",
            address={"street": "Rua Teste", "number": "123", "city": "São Paulo", "state": "SP", "zip_code": "01234567"},
        )
        self.client.force_login(user)
        other = make_user(
            cpf="12345678902",
            telefone="11999999998",
            address={"street": "Rua Teste", "number": "456", "city": "São Paulo", "state": "SP", "zip_code": "01234567"},
        )
        order = create_order(other, with_referral=False)
        response = self.client.get(reverse("payments-manual-confirm", kwargs={"order_pk": order.pk}))
        assert response.status_code == 404


class TestCardConfirmationView(TestCase):
    def setUp(self):
        self.user = make_user(
            cpf="12345678901",
            telefone="11999999999",
            address={"street": "Rua Teste", "number": "123", "city": "São Paulo", "state": "SP", "zip_code": "01234567"},
        )
        self.client.force_login(self.user)
        self.order = create_order(self.user, with_referral=False)

    def _url(self, order=None):
        return reverse("payments-card-confirm", kwargs={"order_pk": (order or self.order).pk})

    def test_card_confirm_200_for_owner(self):
        response = self.client.get(self._url())
        assert response.status_code == 200

    def test_card_confirm_404_other_user(self):
        other = make_user(
            cpf="12345678902",
            telefone="11999999998",
            address={"street": "Rua Teste", "number": "456", "city": "São Paulo", "state": "SP", "zip_code": "01234567"},
        )
        order = create_order(other, with_referral=False)
        response = self.client.get(self._url(order))
        assert response.status_code == 404

    def test_card_confirm_requires_login(self):
        self.client.logout()
        response = self.client.get(self._url())
        assert response.status_code in (302, 403)


class TestOrderStatusView(TestCase):
    def test_status_json_for_owner(self):
        user = make_user(
            cpf="12345678901",
            telefone="11999999999",
            address={"street": "Rua Teste", "number": "123", "city": "São Paulo", "state": "SP", "zip_code": "01234567"},
        )
        self.client.force_login(user)
        order = create_order(user, with_referral=False)
        response = self.client.get(reverse("payments-status", kwargs={"order_pk": order.pk}))
        assert response.status_code == 200
        data = response.json()
        assert data["paid"] is False
        assert data["order_status"] == "awaiting_payment"

    def test_status_404_other_user(self):
        user = make_user(
            cpf="12345678901",
            telefone="11999999999",
            address={"street": "Rua Teste", "number": "123", "city": "São Paulo", "state": "SP", "zip_code": "01234567"},
        )
        self.client.force_login(user)
        other = make_user(
            cpf="12345678902",
            telefone="11999999998",
            address={"street": "Rua Teste", "number": "456", "city": "São Paulo", "state": "SP", "zip_code": "01234567"},
        )
        order = create_order(other, with_referral=False)
        response = self.client.get(reverse("payments-status", kwargs={"order_pk": order.pk}))
        assert response.status_code == 404

    def test_status_requires_login(self):
        order = create_order(make_user(), with_referral=False)
        response = self.client.get(reverse("payments-status", kwargs={"order_pk": order.pk}))
        assert response.status_code in (302, 403)


class TestPaymentConfirmationRoleSeparation(TestCase):
    def test_confirmacoes_restritas_a_cliente(self):
        from apps.accounts.models import CustomUser

        for role in (CustomUser.Role.PRESTADOR, CustomUser.Role.AFILIADO):
            with self.subTest(role=role):
                user = make_user(
                    role=role,
                    cpf="12345678901",
                    telefone="11999999999",
                    address={"street": "Rua Teste", "number": "123", "city": "São Paulo", "state": "SP", "zip_code": "01234567"},
                )
                self.client.force_login(user)
                order = create_order(user, with_referral=False)
                for url_name in ("payments-manual-confirm", "payments-status"):
                    response = self.client.get(
                        reverse(url_name, kwargs={"order_pk": order.pk})
                    )
                    assert response.status_code == 403

    def test_admin_pode_acessar_confirmacoes(self):
        from apps.accounts.models import CustomUser

        admin = make_user(
            role=CustomUser.Role.ADMIN,
            is_superuser=True,
        )
        self.client.force_login(admin)
        order = create_order(admin, with_referral=False)
        response = self.client.get(
            reverse("payments-manual-confirm", kwargs={"order_pk": order.pk})
        )
        assert response.status_code == 200


class TestPixConfirmationView(TestCase):
    def setUp(self):
        self.user = make_user(
            cpf="12345678901",
            telefone="11999999999",
            address={"street": "Rua Teste", "number": "123", "city": "São Paulo", "state": "SP", "zip_code": "01234567"},
        )
        self.client.force_login(self.user)
        self.order = create_order(self.user, with_referral=False)
        Transaction.objects.create(
            order=self.order, provider="asaas", external_id="pay_123", amount=self.order.total, status=Transaction.Status.PENDING
        )

    def _url(self, order=None):
        return reverse("payments-pix-confirm", kwargs={"order_pk": (order or self.order).pk})

    def test_pix_confirm_200_for_owner(self):
        response = self.client.get(self._url())
        assert response.status_code == 200

    def test_pix_confirm_404_other_user(self):
        other = make_user(
            cpf="12345678902",
            telefone="11999999998",
            address={"street": "Rua Teste", "number": "456", "city": "São Paulo", "state": "SP", "zip_code": "01234567"},
        )
        order = create_order(other, with_referral=False)
        response = self.client.get(self._url(order))
        assert response.status_code == 404

    def test_pix_confirm_uses_select_related(self):
        """Pix confirmation deve usar select_related para order e user."""
        # 6 queries: session + user + socialaccount + order + transaction(select_related order,user) + sitesettings
        with self.assertNumQueries(6):
            response = self.client.get(self._url())
        assert response.status_code == 200



    def test_boleto_confirm_404_other_user(self):
        other = make_user(
            cpf="12345678902",
            telefone="11999999998",
            address={"street": "Rua Teste", "number": "456", "city": "São Paulo", "state": "SP", "zip_code": "01234567"},
        )
        order = create_order(other, with_referral=False)
        response = self.client.get(self._url(order))
        assert response.status_code == 404

    def test_boleto_confirm_uses_select_related(self):
        """Boleto confirmation deve usar select_related para order e user."""
        # 6 queries: session + user + socialaccount + order + transaction(select_related order,user) + sitesettings
        with self.assertNumQueries(6):
            response = self.client.get(self._url())
        assert response.status_code == 200
