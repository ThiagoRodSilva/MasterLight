"""Testes da fabrica de gateway (registry)."""

from django.test import TestCase, override_settings

from apps.payments.services import AsaasGateway, ManualGateway, get_gateway
from apps.tests.helpers import make_user


class TestGetGateway(TestCase):
    @override_settings(PAYMENT_PROVIDER="manual", ASAAS_API_KEY="")
    def test_default_returns_manual(self):
        assert isinstance(get_gateway(), ManualGateway)

    @override_settings(PAYMENT_PROVIDER="asaas")
    def test_asaas_provider_returns_asaas_gateway(self):
        assert isinstance(get_gateway(), AsaasGateway)

    @override_settings(DEBUG=True, PAYMENT_PROVIDER="gateway-desconhecido")
    def test_unknown_provider_falls_back_to_manual_in_dev(self):
        assert isinstance(get_gateway(), ManualGateway)

    @override_settings(DEBUG=False, PAYMENT_PROVIDER="gateway-desconhecido")
    def test_unknown_provider_raises_in_production(self):
        from django.core.exceptions import ImproperlyConfigured

        with self.assertRaisesRegex(ImproperlyConfigured, "gateway-desconhecido"):
            get_gateway()


@override_settings(PAYMENT_PROVIDER="asaas", ASAAS_API_KEY="teste", ASAAS_SANDBOX=True)
class TestAsaasGatewayHostedCheckout(TestCase):
    """Testes do gateway Asaas para checkout hospedado."""

    def _user(self):
        return make_user()

    def _address(self, user):
        from apps.checkout.models import Address
        return Address.objects.create(
            user=user,
            street="Rua A",
            number="10",
            city="Cidade",
            state="SP",
            zip_code="01001000",
            country="BR",
        )

    def test_create_checkout_returns_url(self):
        from apps.checkout.models import Order, OrderItem
        from apps.shop.models import Category, Product

        user = self._user()
        self._address(user)

        category = Category.objects.create(name="Teste", slug="teste")
        product = Product.objects.create(
            name="Produto Teste", slug="produto-teste", price=100, category=category, stock=10
        )
        order = Order.objects.create(user=user, status=Order.Status.AWAITING_PAYMENT)
        OrderItem.objects.create(order=order, product=product, name=product.name, qty=1, unit_price=product.price)
        order.recompute_total()

        from django.test import RequestFactory

        from apps.tests.helpers import mock_asaas

        factory = RequestFactory()
        request = factory.post("/")
        request.user = user

        with mock_asaas() as fake:
            gateway = AsaasGateway()
            result = gateway.create_checkout(
                order,
                billing_types=["PIX", "CREDIT_CARD"],
                charge_type="DETACHED",
                callback_urls={
                    "successUrl": "http://test/success",
                    "cancelUrl": "http://test/cancel",
                    "expiredUrl": "http://test/expired",
                },
            )

        assert result.ok is True
        assert result.url == fake.checkout_url
        assert result.checkout_id
