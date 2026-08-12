"""Testes dos serviços de orquestração de cobrança (Fase A)."""

from unittest.mock import Mock, patch

from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase

from apps.accounts.models import CustomUser
from apps.checkout.models import Address, Order
from apps.payments.services import (
    ChargeResult,
    charge_with_rollback,
    resolve_billing,
)
from apps.tests.helpers import make_user, mock_asaas


def _with_middleware(request):
    """Anexa session/messages ao request p/ `messages.error` do service."""
    SessionMiddleware(Mock()).process_request(request)
    MessageMiddleware(Mock()).process_request(request)
    return request


class TestResolveBilling(TestCase):
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.user = make_user(role=CustomUser.Role.CLIENTE)

    def test_default_to_pix_without_token(self):
        request = self.factory.post("/", {})
        params = resolve_billing(request, self.user)
        assert params.billing_type == "PIX"
        assert params.credit_card_token == ""
        assert params.remote_ip

    def test_credit_card_tokenizes_with_asaas(self):
        user = make_user(role=CustomUser.Role.CLIENTE, cpf="12345678900")
        Address.objects.create(
            user=user,
            street="Rua A",
            number="100",
            city="Cidade",
            state="SP",
            zip_code="01001000",
        )
        request = self.factory.post(
            "/",
            {
                "payment_method": "CREDIT_CARD",
                "card_holder": "Cliente Teste",
                "card_number": "4111111111111111",
                "card_expiry_month": "12",
                "card_expiry_year": "2030",
                "card_ccv": "123",
                "card_cpf": "12345678900",
            },
        )
        with self.settings(PAYMENT_PROVIDER="asaas", ASAAS_API_KEY="teste", ASAAS_SANDBOX=True):
            with mock_asaas() as fake:
                params = resolve_billing(request, user)
        assert params.billing_type == "CREDIT_CARD"
        assert params.credit_card_token == fake.card_token

    def test_credit_card_requires_address(self):
        user = make_user(role=CustomUser.Role.CLIENTE, cpf="12345678900")
        request = self.factory.post(
            "/",
            {
                "payment_method": "CREDIT_CARD",
                "card_cpf": "12345678900",
            },
        )
        with self.settings(PAYMENT_PROVIDER="asaas", ASAAS_API_KEY="teste", ASAAS_SANDBOX=True):
            with self.assertRaises(ValueError):
                resolve_billing(request, user)


class TestChargeWithRollback(TestCase):
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.user = make_user(role=CustomUser.Role.CLIENTE)
        self.order = Order.objects.create(
            user=self.user, status=Order.Status.AWAITING_PAYMENT
        )

    def test_success_keeps_order_and_returns_result(self):
        request = _with_middleware(self.factory.post("/", {}))
        result = charge_with_rollback(self.order, request)
        assert result is not None
        assert result.ok is True
        self.order.refresh_from_db()
        assert self.order.status == Order.Status.AWAITING_PAYMENT

    def test_gateway_error_cancels_order_and_returns_none(self):
        request = _with_middleware(self.factory.post("/", {}))
        with patch(
            "apps.payments.services.charge_order",
            side_effect=ValueError("gateway fora"),
        ):
            result = charge_with_rollback(self.order, request)
        assert result is None
        self.order.refresh_from_db()
        assert self.order.status == Order.Status.CANCELED

    def test_not_ok_cancels_order_and_returns_none(self):
        request = _with_middleware(self.factory.post("/", {}))
        fake = ChargeResult(ok=False, redirect_url="", message="falha ao gerar")
        with patch("apps.payments.services.charge_order", return_value=fake):
            result = charge_with_rollback(self.order, request)
        assert result is None
        self.order.refresh_from_db()
        assert self.order.status == Order.Status.CANCELED
