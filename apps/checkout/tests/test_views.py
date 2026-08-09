"""Testes do carrinho/checkout."""

import pytest
from django.conf import settings
from django.shortcuts import reverse
from django.test import override_settings

from apps.affiliate.models import AffiliateProfile, Referral
from apps.checkout.models import Order
from conftest import ProductFactory

pytestmark = pytest.mark.django_db


class TestCartAddView:
    def test_add_valid_product(self, client_user):
        product = ProductFactory(stock=5)
        response = client_user.post(reverse("checkout-cart-add", args=[product.pk]), {"qty": "2"})
        assert response.status_code == 302
        assert response.url == reverse("checkout-cart")
        session_cart = client_user.session.get("cart", {})
        assert str(product.pk) in session_cart
        assert session_cart[str(product.pk)]["qty"] == 2

    def test_invalid_qty_does_not_crash(self, client_user):
        product = ProductFactory(stock=5)
        response = client_user.post(reverse("checkout-cart-add", args=[product.pk]), {"qty": "abc"})
        assert response.status_code == 302

    def test_negative_qty_rejected(self, client_user):
        product = ProductFactory(stock=5)
        response = client_user.post(reverse("checkout-cart-add", args=[product.pk]), {"qty": "-3"})
        assert response.status_code == 302
        assert client_user.session.get("cart", {}) == {}

    def test_qty_above_stock_rejected(self, client_user):
        product = ProductFactory(stock=3)
        response = client_user.post(reverse("checkout-cart-add", args=[product.pk]), {"qty": "10"})
        assert response.status_code == 302
        assert client_user.session.get("cart", {}) == {}

    def test_zero_qty_rejected(self, client_user):
        product = ProductFactory(stock=5)
        response = client_user.post(reverse("checkout-cart-add", args=[product.pk]), {"qty": "0"})
        assert response.status_code == 302
        assert client_user.session.get("cart", {}) == {}


class TestCheckoutView:
    def _with_cart(self, client_user, product, qty=1):
        client_user.post(reverse("checkout-cart-add", args=[product.pk]), {"qty": str(qty)})

    def test_checkout_creates_order_with_items(self, client_user, user):
        product = ProductFactory(stock=10)
        self._with_cart(client_user, product, qty=2)
        response = client_user.post(reverse("checkout"))
        assert response.status_code == 302
        order = Order.objects.filter(user=user).latest("created_at")
        assert order.status == Order.Status.AWAITING_PAYMENT
        assert order.items.count() == 1
        assert order.items.first().qty == 2

    def test_checkout_uses_db_price(self, client_user, user):
        product = ProductFactory(stock=10, price=100)
        self._with_cart(client_user, product, qty=1)
        session = client_user.session
        cart = session.get("cart", {})
        cart[str(product.pk)]["price"] = 1.0  # tenta manipular preco na sessao
        session["cart"] = cart
        session.save()
        client_user.post(reverse("checkout"))
        order = Order.objects.filter(user=user).latest("created_at")
        assert order.items.first().unit_price == 100

    def test_checkout_empty_cart_redirects(self, client_user):
        response = client_user.post(reverse("checkout"))
        assert response.status_code == 302
        assert response.url == reverse("shop-list")

    def test_checkout_get_empty_cart_redirects(self, client_user):
        response = client_user.get(reverse("checkout"))
        assert response.status_code == 302
        assert response.url == reverse("shop-list")

    def test_self_referral_blocked(self, user, client):
        affil, _ = AffiliateProfile.objects.get_or_create(user=user)
        user.role = user.Role.AFILIADO
        user.save()
        client.force_login(user)
        client.cookies[settings.AFFILIATE_COOKIE_NAME] = affil.code
        product = ProductFactory(stock=10)
        client.post(reverse("checkout-cart-add", args=[product.pk]), {"qty": "1"})
        client.post(reverse("checkout"))
        assert Referral.objects.filter(affiliate=affil).count() == 0

    def test_checkout_credit_card_graceful_on_manual_provider(self, client_user, user):
        with override_settings(PAYMENT_PROVIDER="manual"):
            product = ProductFactory(stock=10)
            self._with_cart(client_user, product, qty=1)
            response = client_user.post(reverse("checkout"), {"payment_method": "CREDIT_CARD"})
            assert response.status_code == 302
            assert response.url == reverse("checkout-cart")
            order = Order.objects.filter(user=user).latest("created_at")
            assert order.status == Order.Status.CANCELED


class TestReferralCreation:
    def test_checkout_creates_referral_with_cookie(self, user, client, affiliate_profile):
        client.force_login(user)
        client.cookies[settings.AFFILIATE_COOKIE_NAME] = affiliate_profile.code
        product = ProductFactory(stock=10, price=100)
        client.post(reverse("checkout-cart-add", args=[product.pk]), {"qty": "1"})
        client.post(reverse("checkout"))

        order = Order.objects.filter(user=user).latest("created_at")
        referral = Referral.objects.get(affiliate=affiliate_profile, order=order)
        assert referral.referred == user
        assert referral.commission_amount == order.total * affiliate_profile.commission_rate

    def test_no_referral_without_cookie(self, user, client, affiliate_profile):
        client.force_login(user)
        product = ProductFactory(stock=10)
        client.post(reverse("checkout-cart-add", args=[product.pk]), {"qty": "1"})
        client.post(reverse("checkout"))
        assert Referral.objects.filter(affiliate=affiliate_profile).count() == 0
