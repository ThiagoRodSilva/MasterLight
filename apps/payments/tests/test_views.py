"""Testes do app de pagamentos (webhook + gateway manual)."""

import json

import pytest
from django.test import Client, override_settings
from django.urls import reverse

from apps.payments.models import Transaction
from apps.payments.services import ManualGateway
from conftest import create_order

pytestmark = pytest.mark.django_db

WEBHOOK_TOKEN = "segredo-manual"


@pytest.fixture
def manual_token():
    """Ativa o token do gateway manual no contexto dos testes."""
    with override_settings(MANUAL_WEBHOOK_TOKEN=WEBHOOK_TOKEN):
        yield


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"x-webhook-token": "errado"},
    ],
)
def test_webhook_manual_requires_valid_token(headers, user):
    order = create_order(user, with_referral=False)
    tx = order.transactions.first()
    gateway = ManualGateway()
    try:
        gateway.webhook(json.dumps({"transaction_id": str(tx.pk), "status": "paid"}), headers)
    except ValueError:
        assert True
    else:
        pytest.fail("webhook sem token válido deveria falhar")


class TestManualGatewayWebhook:
    @pytest.mark.usefixtures("manual_token")
    def test_charge_creates_pending_transaction(self, user):
        order = create_order(user, with_referral=False)
        gateway = ManualGateway()
        result = gateway.charge(order)
        assert result.ok is True
        tx = Transaction.objects.get(pk=result.external_id)
        assert tx.status == Transaction.Status.PENDING
        assert tx.amount == order.total

    @pytest.mark.usefixtures("manual_token")
    def test_webhook_marks_paid_with_token(self, user):
        order = create_order(user, with_referral=False)
        tx = order.transactions.first()
        result = ManualGateway().webhook(
            json.dumps({"transaction_id": str(tx.pk), "status": "paid"}),
            {"x-webhook-token": WEBHOOK_TOKEN},
        )
        assert result.ok is True
        tx.refresh_from_db()
        assert tx.status == Transaction.Status.PAID

    @pytest.mark.usefixtures("manual_token")
    def test_webhook_invalid_json_raises(self):
        with pytest.raises(ValueError):
            ManualGateway().webhook("not json", {"x-webhook-token": WEBHOOK_TOKEN})

    @pytest.mark.usefixtures("manual_token")
    def test_webhook_invalid_uuid_raises(self):
        with pytest.raises(ValueError):
            ManualGateway().webhook(
                json.dumps({"transaction_id": "abc", "status": "paid"}),
                {"x-webhook-token": WEBHOOK_TOKEN},
            )

    @pytest.mark.usefixtures("manual_token")
    def test_webhook_missing_status_raises(self):
        with pytest.raises(ValueError):
            ManualGateway().webhook(
                json.dumps({"transaction_id": "x"}),
                {"x-webhook-token": WEBHOOK_TOKEN},
            )

    @pytest.mark.usefixtures("manual_token")
    def test_charge_redirects_to_manual_confirm(self, user):
        order = create_order(user, with_referral=False)
        result = ManualGateway().charge(order)
        expected = reverse("payments-manual-confirm", args=[order.pk])
        assert result.redirect_url == expected


@pytest.mark.usefixtures("manual_token")
class TestWebhookView:
    def _post(self, client, payload, content_type="application/json", token=WEBHOOK_TOKEN):
        return client.post(
            reverse("payments-webhook"),
            data=json.dumps(payload),
            content_type=content_type,
            HTTP_X_WEBHOOK_TOKEN=token,
        )

    def test_webhook_paid_marks_transaction(self, client, user):
        order = create_order(user, with_referral=False)
        tx = order.transactions.first()
        response = self._post(client, {"transaction_id": str(tx.pk), "status": "paid"})
        assert response.status_code == 200
        tx.refresh_from_db()
        assert tx.status == Transaction.Status.PAID

    def test_webhook_missing_token_returns_401(self, client, user):
        order = create_order(user, with_referral=False)
        tx = order.transactions.first()
        response = self._post(client, {"transaction_id": str(tx.pk), "status": "paid"}, token="")
        assert response.status_code == 401

    def test_webhook_bad_json_returns_400(self, client):
        response = client.post(
            reverse("payments-webhook"),
            data="não-json",
            content_type="application/json",
            HTTP_X_WEBHOOK_TOKEN=WEBHOOK_TOKEN,
        )
        assert response.status_code == 400

    def test_webhook_unknown_tx_returns_404(self, client):
        from uuid import uuid4

        response = self._post(client, {"transaction_id": str(uuid4()), "status": "paid"})
        assert response.status_code == 404

    def test_webhook_invalid_uuid_returns_400(self, client):
        response = self._post(client, {"transaction_id": "abc", "status": "paid"})
        assert response.status_code == 400

    def test_webhook_allowed_without_csrf(self, user):
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


@pytest.mark.usefixtures("manual_token")
class TestManualConfirmationView:
    def test_manual_tokenize_credit_card_raises(self, user):
        gateway = ManualGateway()
        with pytest.raises(ValueError, match="asaas"):
            gateway.tokenize_credit_card(user, card={}, holder={})

    def test_manual_confirm_200_for_owner(self, user, client):
        client.force_login(user)
        order = create_order(user, with_referral=False)
        response = client.get(reverse("payments-manual-confirm", kwargs={"order_pk": order.pk}))
        assert response.status_code == 200
        assert str(order.pk)[:5] in response.content.decode()

    def test_manual_confirm_404_other_user(self, user, client, affiliate_profile):
        client.force_login(user)
        other = affiliate_profile.user
        order = create_order(other, with_referral=False)
        response = client.get(reverse("payments-manual-confirm", kwargs={"order_pk": order.pk}))
        assert response.status_code == 404
