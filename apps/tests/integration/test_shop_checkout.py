"""Integração ponta a ponta: Shop Checkout completo (produto -> carrinho -> pagamento)."""

import json
from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.checkout.models import Order
from apps.payments.models import Transaction
from apps.shop.models import Category, Product
from apps.tests.helpers import AsaasMockMixin, make_user

ASAAS_SETTINGS = {
    "PAYMENT_PROVIDER": "asaas",
    "ASAAS_API_KEY": "teste-key",
    "ASAAS_SANDBOX": True,
    "ASAAS_WEBHOOK_TOKEN": "segredo",
    "CARD_ENABLED": True,
}


@override_settings(**ASAAS_SETTINGS)
class TestShopCheckoutFlow(AsaasMockMixin, TestCase):
    """Fluxo completo: listar produto -> adicionar ao carrinho -> checkout -> pagamento."""

    def setUp(self):
        super().setUp()
        self.category = Category.objects.create(name="Teste", slug="teste-flow")
        self.product = Product.objects.create(
            name="Produto Flow",
            slug="produto-flow",
            sku="SKU-FLOW",
            price=Decimal("49.90"),
            stock=10,
            category=self.category,
        )
        self.client_user = make_user(role="cliente", email="cliente@test.com")
        # Add CPF, phone, address for Asaas checkout
        self.client_user.cpf = "12345678901"
        self.client_user.telefone = "11999999999"
        self.client_user.save()
        from apps.checkout.models import Address
        Address.objects.create(
            user=self.client_user,
            street="Rua Teste",
            number="123",
            city="São Paulo",
            state="SP",
            zip_code="01000-000",
            country="BR",
            is_active=True,
        )

    def _add_to_cart(self, product, qty=1):
        session = self.client.session
        cart = session.get("cart", {})
        key = str(product.id)
        if key not in cart:
            cart[key] = {"qty": 0, "price": float(product.price), "name": product.name}
        cart[key]["qty"] = cart[key].get("qty", 0) + qty
        session["cart"] = cart
        session.save()

    def _checkout_pix(self):
        self.client.force_login(self.client_user)
        response = self.client.post(
            reverse("checkout"),
            {"payment_method": "PIX"},
            follow=False,  # Don't follow external redirect
        )
        return response

    def _pay_order(self, order):
        """Simulate webhook for hosted checkout (CHECKOUT_PAID)."""
        from apps.payments.services import AsaasGateway

        # For hosted checkout, the webhook is CHECKOUT_PAID with checkout data
        checkout_id = self.asaas.checkout_id
        payload = json.dumps({"event": "CHECKOUT_PAID", "checkout": {"id": checkout_id, "status": "PAID"}})
        AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})

    def test_shop_checkout_pix_complete_flow(self):
        """Fluxo completo: produto -> carrinho -> checkout PIX -> webhook -> pedido pago."""
        self._add_to_cart(self.product, qty=2)

        response = self._checkout_pix()
        # With Asaas hosted checkout, redirects to Asaas URL (302)
        self.assertEqual(response.status_code, 302)

        order = Order.objects.filter(user=self.client_user).latest("created_at")
        self.assertEqual(order.status, Order.Status.AWAITING_PAYMENT)
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().qty, 2)
        self.assertEqual(order.total, Decimal("99.80"))

        tx = order.transactions.get(provider="asaas")
        self.assertEqual(tx.status, Transaction.Status.PENDING)

        self._pay_order(order)

        order.refresh_from_db()
        tx.refresh_from_db()
        self.assertEqual(tx.status, Transaction.Status.PAID)
        self.assertEqual(order.status, Order.Status.PAID)


        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)

    def test_shop_checkout_requires_login(self):
        """Checkout exige usuário logado."""
        self._add_to_cart(self.product)
        response = self.client.post(reverse("checkout"), {"payment_method": "PIX"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/social/login/", response.url)

    def test_shop_checkout_empty_cart_redirects(self):
        """Carrinho vazio redireciona para loja."""
        self.client.force_login(self.client_user)
        response = self.client.post(reverse("checkout"), {"payment_method": "PIX"})
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("shop-list"), response.url)

    def test_shop_checkout_stock_validation(self):
        """Valida estoque insuficiente no checkout."""
        self._add_to_cart(self.product, qty=15)
        self.client.force_login(self.client_user)

        response = self.client.post(reverse("checkout"), {"payment_method": "PIX"}, follow=True)
        # Stock validation happens before checkout creation, redirects to cart then shop-list with error message
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "disponível na quantidade")


@override_settings(**ASAAS_SETTINGS)
class TestShopCheckoutCardFlow(AsaasMockMixin, TestCase):
    """Fluxo checkout com cartão de crédito."""

    def setUp(self):
        super().setUp()
        self.category = Category.objects.create(name="Teste", slug="teste-flow-card")
        self.product = Product.objects.create(
            name="Produto Card",
            slug="produto-card",
            sku="SKU-CARD",
            price=Decimal("99.00"),
            stock=5,
            category=self.category,
        )
        self.client_user = make_user(role="cliente", email="cliente-card@test.com")
        # Add CPF, phone, address for Asaas checkout
        self.client_user.cpf = "12345678901"
        self.client_user.telefone = "11999999999"
        self.client_user.save()
        from apps.checkout.models import Address
        Address.objects.create(
            user=self.client_user,
            street="Rua Teste",
            number="123",
            city="São Paulo",
            state="SP",
            zip_code="01000-000",
            country="BR",
            is_active=True,
        )

    def test_shop_checkout_card_complete_flow(self):
        """Fluxo checkout com cartão -> webhook -> pedido pago."""
        session = self.client.session
        session["cart"] = {str(self.product.id): {"qty": 1, "price": float(self.product.price), "name": self.product.name}}
        session.save()

        self.client.force_login(self.client_user)
        response = self.client.post(
            reverse("checkout"),
            {"payment_method": "CREDIT_CARD", "card_token": "tok_test"},
            follow=False,  # Don't follow external redirect
        )
        # With Asaas hosted checkout, redirects to Asaas URL (302)
        self.assertEqual(response.status_code, 302)

        order = Order.objects.filter(user=self.client_user).latest("created_at")
        self.assertEqual(order.status, Order.Status.AWAITING_PAYMENT)

        # For hosted checkout, use CHECKOUT_PAID webhook
        from apps.payments.services import AsaasGateway

        checkout_id = self.asaas.checkout_id
        payload = json.dumps({"event": "CHECKOUT_PAID", "checkout": {"id": checkout_id, "status": "PAID"}})
        AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
