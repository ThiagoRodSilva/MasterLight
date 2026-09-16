"""Testes do app de pagamentos (webhook + confirmações)."""

import json

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.payments.models import Transaction
from apps.tests.helpers import AsaasMockMixin, create_order, make_user

WEBHOOK_TOKEN = "segredo"


@override_settings(
    PAYMENT_PROVIDER="asaas",
    ASAAS_API_KEY="teste-key",
    ASAAS_SANDBOX=True,
    ASAAS_WEBHOOK_TOKEN=WEBHOOK_TOKEN,
)
class TestAsaasWebhookMarksPaid(AsaasMockMixin, TestCase):
    def test_charge_creates_pending_transaction(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        from apps.payments.gateways.asaas import AsaasGateway

        result = AsaasGateway().charge(order, billing_type="PIX")
        assert result.ok is True
        tx = Transaction.objects.get(pk=result.transaction_id)
        assert tx.status == Transaction.Status.PENDING
        assert tx.amount == order.total

    def test_webhook_marks_paid_with_token(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        from apps.payments.gateways.asaas import AsaasGateway

        gateway = AsaasGateway()
        result = gateway.charge(order, billing_type="PIX")
        tx = Transaction.objects.get(pk=result.transaction_id)
        payload = json.dumps(
            {"event": "PAYMENT_CONFIRMED", "payment": {"id": self.asaas.payment_id}}
        )
        result = gateway.webhook(payload, {"asaas-access-token": WEBHOOK_TOKEN})
        assert result.ok is True
        tx.refresh_from_db()
        assert tx.status == Transaction.Status.PAID


@override_settings(
    PAYMENT_PROVIDER="asaas",
    ASAAS_API_KEY="teste-key",
    ASAAS_SANDBOX=True,
    ASAAS_WEBHOOK_TOKEN=WEBHOOK_TOKEN,
)
class TestWebhookView(AsaasMockMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()
        self.order = create_order(self.user, with_referral=False)
        self.tx = Transaction.objects.create(
            order=self.order,
            user=self.user,
            provider="asaas",
            external_id=self.asaas.payment_id,
            amount=self.order.total,
            status=Transaction.Status.PENDING,
        )

    def _post(self, payload, content_type="application/json", token=WEBHOOK_TOKEN):
        return self.client.post(
            reverse("payments-webhook"),
            data=json.dumps(payload),
            content_type=content_type,
            HTTP_ASAAS_ACCESS_TOKEN=token,
        )

    def test_webhook_paid_marks_transaction(self):
        response = self._post(
            {"event": "PAYMENT_CONFIRMED", "payment": {"id": self.asaas.payment_id}}
        )
        assert response.status_code == 200
        self.tx.refresh_from_db()
        assert self.tx.status == Transaction.Status.PAID

    def test_webhook_missing_token_returns_401(self):
        response = self._post(
            {"event": "PAYMENT_CONFIRMED", "payment": {"id": self.asaas.payment_id}},
            token="",
        )
        assert response.status_code == 401

    def test_webhook_bad_json_returns_400(self):
        response = self.client.post(
            reverse("payments-webhook"),
            data="não-json",
            content_type="application/json",
            HTTP_ASAAS_ACCESS_TOKEN=WEBHOOK_TOKEN,
        )
        assert response.status_code == 400

    def test_webhook_unknown_payment_returns_200(self):
        response = self._post({"event": "PAYMENT_CONFIRMED", "payment": {"id": "pay_xpto"}})
        assert response.status_code == 200

    def test_webhook_missing_payment_returns_400(self):
        response = self._post({"event": "SUBSCRIPTION_CREATED"})
        assert response.status_code == 400

    def test_webhook_allowed_without_csrf(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(
            reverse("payments-webhook"),
            data=json.dumps(
                {"event": "PAYMENT_CONFIRMED", "payment": {"id": self.asaas.payment_id}}
            ),
            content_type="application/json",
            HTTP_ASAAS_ACCESS_TOKEN=WEBHOOK_TOKEN,
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

    def test_subscription_only_payload_returns_400(self):
        """Sem assinaturas, payload de `subscription` sem `payment` é rejeitado."""
        payload = {
            "event": "SUBSCRIPTION_CREATED",
            "subscription": {"id": "sub_0001", "status": "ACTIVE"},
        }
        response = self._post(payload)
        assert response.status_code == 400

    def test_missing_token_returns_401(self):
        response = self._post(
            {"event": "PAYMENT_CONFIRMED", "payment": {"id": "pay_xpto"}}, token=""
        )
        assert response.status_code == 401


class TestCardConfirmationView(TestCase):
    def setUp(self):
        self.user = make_user(
            cpf="12345678901",
            telefone="11999999999",
            address={
                "street": "Rua Teste",
                "number": "123",
                "city": "São Paulo",
                "state": "SP",
                "zip_code": "01234567",
            },
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
            address={
                "street": "Rua Teste",
                "number": "456",
                "city": "São Paulo",
                "state": "SP",
                "zip_code": "01234567",
            },
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
            address={
                "street": "Rua Teste",
                "number": "123",
                "city": "São Paulo",
                "state": "SP",
                "zip_code": "01234567",
            },
        )
        self.client.force_login(user)
        order = create_order(user, with_referral=False)
        response = self.client.get(reverse("payments-status", kwargs={"order_pk": order.pk}))
        assert response.status_code == 200
        data = response.json()
        assert data["paid"] is False
        assert data["order_status"] == "open"

    def test_status_404_other_user(self):
        user = make_user(
            cpf="12345678901",
            telefone="11999999999",
            address={
                "street": "Rua Teste",
                "number": "123",
                "city": "São Paulo",
                "state": "SP",
                "zip_code": "01234567",
            },
        )
        self.client.force_login(user)
        other = make_user(
            cpf="12345678902",
            telefone="11999999998",
            address={
                "street": "Rua Teste",
                "number": "456",
                "city": "São Paulo",
                "state": "SP",
                "zip_code": "01234567",
            },
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
                    address={
                        "street": "Rua Teste",
                        "number": "123",
                        "city": "São Paulo",
                        "state": "SP",
                        "zip_code": "01234567",
                    },
                )
                self.client.force_login(user)
                order = create_order(user, with_referral=False)
                for url_name in ("payments-pix-confirm", "payments-status"):
                    response = self.client.get(reverse(url_name, kwargs={"order_pk": order.pk}))
                    assert response.status_code == 403

    def test_admin_pode_acessar_confirmacoes(self):
        from apps.accounts.models import CustomUser

        admin = make_user(
            role=CustomUser.Role.ADMIN,
            is_superuser=True,
        )
        self.client.force_login(admin)
        order = create_order(admin, with_referral=False)
        response = self.client.get(reverse("payments-status", kwargs={"order_pk": order.pk}))
        assert response.status_code == 200


class TestPixConfirmationView(TestCase):
    def setUp(self):
        self.user = make_user(
            cpf="12345678901",
            telefone="11999999999",
            address={
                "street": "Rua Teste",
                "number": "123",
                "city": "São Paulo",
                "state": "SP",
                "zip_code": "01234567",
            },
        )
        self.client.force_login(self.user)
        self.order = create_order(self.user, with_referral=False)
        Transaction.objects.create(
            order=self.order,
            provider="asaas",
            external_id="pay_123",
            amount=self.order.total,
            status=Transaction.Status.PENDING,
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
            address={
                "street": "Rua Teste",
                "number": "456",
                "city": "São Paulo",
                "state": "SP",
                "zip_code": "01234567",
            },
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
