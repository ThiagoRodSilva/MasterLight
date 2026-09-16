"""Testes dos serviços de orquestração de checkout hospedado (Asaas)."""

from unittest.mock import Mock, patch

from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase

from apps.accounts.models import CustomUser
from apps.checkout.models import Order
from apps.payments.services import checkout_or_charge
from apps.tests.helpers import make_user, mock_asaas


def _with_middleware(request):
    """Anexa session/messages ao request p/ `messages.error` do service."""
    SessionMiddleware(Mock()).process_request(request)
    MessageMiddleware(Mock()).process_request(request)
    return request


class TestCheckoutOrCharge(TestCase):
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.user = make_user(role=CustomUser.Role.CLIENTE)
        from apps.services.models import Service, ServiceCategory

        category = ServiceCategory.objects.create(name="Teste", slug="teste")
        service = Service.objects.create(
            name="Serviço Teste", slug="servico-teste", base_price=100, category=category
        )
        self.order = Order.objects.create(user=self.user, status=Order.Status.AWAITING_PAYMENT)
        from apps.checkout.models import OrderItem

        OrderItem.objects.create(
            order=self.order,
            service=service,
            name=service.name,
            qty=1,
            unit_price=service.base_price,
        )
        self.order.recompute_total()

    def test_asaas_hosted_checkout_success(self):
        request = _with_middleware(self.factory.post("/", {}))
        with self.settings(PAYMENT_PROVIDER="asaas", ASAAS_API_KEY="teste", ASAAS_SANDBOX=True):
            with mock_asaas() as fake:
                result = checkout_or_charge(self.order, request)
        assert result is not None
        assert "url" in result
        assert result["url"] == fake.checkout_url
        self.order.refresh_from_db()
        assert self.order.status == Order.Status.AWAITING_PAYMENT

    def test_asaas_checkout_error_cancels_order(self):
        request = _with_middleware(self.factory.post("/", {}))
        with self.settings(PAYMENT_PROVIDER="asaas", ASAAS_API_KEY="teste", ASAAS_SANDBOX=True):
            # Mock create_checkout_for_order para levantar erro
            with patch(
                "apps.payments.orchestration.create_checkout_for_order",
                side_effect=ValueError("Falha no Asaas"),
            ):
                with patch("django.contrib.messages.error"):
                    request = _with_middleware(self.factory.post("/", {}))
                    result = checkout_or_charge(self.order, request)
        assert result is None
        self.order.refresh_from_db()
        assert self.order.status == Order.Status.CANCELED

    def test_non_asaas_provider_raises_error(self):
        request = _with_middleware(self.factory.post("/", {}))
        with self.settings(PAYMENT_PROVIDER="manual"):
            with self.assertRaises(ValueError):
                checkout_or_charge(self.order, request)

    def test_empty_cart_returns_none(self):
        """Pedido sem itens deve falhar ao criar checkout."""
        request = _with_middleware(self.factory.post("/", {}))
        empty_order = Order.objects.create(user=self.user, status=Order.Status.AWAITING_PAYMENT)
        with self.settings(PAYMENT_PROVIDER="asaas", ASAAS_API_KEY="teste", ASAAS_SANDBOX=True):
            result = checkout_or_charge(empty_order, request)
        assert result is None
        empty_order.refresh_from_db()
        assert empty_order.status == Order.Status.CANCELED
