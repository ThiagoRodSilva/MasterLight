"""Testes do carrinho/checkout."""

from django.conf import settings
from django.shortcuts import reverse
from django.test import TestCase, override_settings

from apps.affiliate.models import AffiliateProfile, Referral
from apps.checkout.models import Order
from apps.tests.helpers import make_affiliate, make_product, make_user, mock_asaas

ASAAS_SETTINGS = {
    "PAYMENT_PROVIDER": "asaas",
    "ASAAS_API_KEY": "teste-key",
    "ASAAS_SANDBOX": True,
    "ASAAS_WEBHOOK_TOKEN": "segredo",
}


class TestCartAddView(TestCase):
    def test_add_valid_product(self):
        product = make_product(stock=5)
        user = make_user()
        self.client.force_login(user)
        response = self.client.post(reverse("checkout-cart-add", args=[product.pk]), {"qty": "2"})
        assert response.status_code == 302
        assert response.url == reverse("checkout-cart")
        session_cart = self.client.session.get("cart", {})
        assert str(product.pk) in session_cart
        assert session_cart[str(product.pk)]["qty"] == 2

    def test_invalid_qty_does_not_crash(self):
        product = make_product(stock=5)
        user = make_user()
        self.client.force_login(user)
        response = self.client.post(reverse("checkout-cart-add", args=[product.pk]), {"qty": "abc"})
        assert response.status_code == 302

    def test_negative_qty_rejected(self):
        product = make_product(stock=5)
        user = make_user()
        self.client.force_login(user)
        response = self.client.post(reverse("checkout-cart-add", args=[product.pk]), {"qty": "-3"})
        assert response.status_code == 302
        assert self.client.session.get("cart", {}) == {}

    def test_qty_above_stock_rejected(self):
        product = make_product(stock=3)
        user = make_user()
        self.client.force_login(user)
        response = self.client.post(reverse("checkout-cart-add", args=[product.pk]), {"qty": "10"})
        assert response.status_code == 302
        assert self.client.session.get("cart", {}) == {}

    def test_zero_qty_rejected(self):
        product = make_product(stock=5)
        user = make_user()
        self.client.force_login(user)
        response = self.client.post(reverse("checkout-cart-add", args=[product.pk]), {"qty": "0"})
        assert response.status_code == 302
        assert self.client.session.get("cart", {}) == {}

    def test_get_add_redirects_to_shop_list(self):
        product = make_product()
        user = make_user()
        self.client.force_login(user)
        response = self.client.get(reverse("checkout-cart-add", args=[product.pk]))
        assert response.status_code == 302
        assert response.url == reverse("shop-list")

    def test_add_blocked_when_store_disabled(self):
        from apps.core.models import SiteSettings

        settings = SiteSettings.load()
        settings.store_enabled = False
        settings.save(update_fields=["store_enabled"])
        user = make_user()
        self.client.force_login(user)
        product = make_product()
        response = self.client.post(reverse("checkout-cart-add", args=[product.pk]), {"qty": "1"})
        assert response.status_code == 302
        assert response.url == reverse("home")

    def test_cart_page_and_remove(self):
        product = make_product(stock=5)
        user = make_user()
        self.client.force_login(user)
        self.client.post(reverse("checkout-cart-add", args=[product.pk]), {"qty": "2"})
        response = self.client.get(reverse("checkout-cart"))
        assert response.status_code == 200
        assert product.name.encode() in response.content
        response = self.client.post(reverse("checkout-cart-remove", args=[product.pk]))
        assert response.status_code == 302
        assert self.client.session.get("cart", {}) == {}


class TestCheckoutView(TestCase):
    def _login(self):
        self.user = make_user()
        self.client.force_login(self.user)
        return self.user

    def _with_cart(self, product, qty=1):
        self.client.post(reverse("checkout-cart-add", args=[product.pk]), {"qty": str(qty)})

    def test_checkout_creates_order_with_items(self):
        user = self._login()
        product = make_product(stock=10)
        self._with_cart(product, qty=2)
        response = self.client.post(reverse("checkout"))
        assert response.status_code == 302
        order = Order.objects.filter(user=user).latest("created_at")
        assert order.status == Order.Status.AWAITING_PAYMENT
        assert order.items.count() == 1
        assert order.items.first().qty == 2

    def test_checkout_uses_db_price(self):
        user = self._login()
        product = make_product(stock=10, price=100)
        self._with_cart(product, qty=1)
        session = self.client.session
        cart = session.get("cart", {})
        cart[str(product.pk)]["price"] = 1.0  # tenta manipular preco na sessao
        session["cart"] = cart
        session.save()
        self.client.post(reverse("checkout"))
        order = Order.objects.filter(user=user).latest("created_at")
        assert order.items.first().unit_price == 100

    def test_checkout_empty_cart_redirects(self):
        self._login()
        response = self.client.post(reverse("checkout"))
        assert response.status_code == 302
        assert response.url == reverse("shop-list")

    def test_checkout_get_empty_cart_redirects(self):
        self._login()
        response = self.client.get(reverse("checkout"))
        assert response.status_code == 302
        assert response.url == reverse("shop-list")

    def test_checkout_get_with_items_renders(self):
        self._login()
        product = make_product(stock=10)
        self._with_cart(product, qty=1)
        response = self.client.get(reverse("checkout"))
        assert response.status_code == 200

    def test_checkout_stock_changed_cancels_order(self):
        user = self._login()
        product = make_product(stock=5)
        session = self.client.session
        session["cart"] = {
            str(product.pk): {"qty": 10, "price": float(product.price), "name": product.name}
        }
        session.save()
        response = self.client.post(reverse("checkout"))
        assert response.status_code == 302
        assert response.url == reverse("checkout-cart")
        order = Order.objects.filter(user=user).latest("created_at")
        assert order.status == Order.Status.CANCELED

    def test_self_referral_blocked(self):
        user = make_user()
        affil, _ = AffiliateProfile.objects.get_or_create(user=user)
        user.role = user.Role.AFILIADO
        user.save()
        self.client.force_login(user)
        self.client.cookies[settings.AFFILIATE_COOKIE_NAME] = affil.code
        product = make_product(stock=10)
        self.client.post(reverse("checkout-cart-add", args=[product.pk]), {"qty": "1"})
        self.client.post(reverse("checkout"))
        assert Referral.objects.filter(affiliate=affil).count() == 0

    def test_checkout_credit_card_graceful_on_manual_provider(self):
        user = self._login()
        with override_settings(PAYMENT_PROVIDER="manual"):
            product = make_product(stock=10)
            self._with_cart(product, qty=1)
            response = self.client.post(reverse("checkout"), {"payment_method": "CREDIT_CARD"})
            assert response.status_code == 302
            assert response.url == reverse("checkout-cart")
            order = Order.objects.filter(user=user).latest("created_at")
            assert order.status == Order.Status.CANCELED

    @override_settings(**ASAAS_SETTINGS)
    def test_checkout_asaas_redirects_to_hosted_checkout(self):
        from apps.payments.models import Transaction

        user = self._login()
        with mock_asaas() as _fake:
            product = make_product(stock=10)
            self._with_cart(product, qty=1)
            response = self.client.post(reverse("checkout"), {"payment_method": "PIX"})
        assert response.status_code == 302
        order = Order.objects.filter(user=user).latest("created_at")
        assert response.url == _fake.checkout_url
        tx = Transaction.objects.get(order=order)
        assert tx.provider == "asaas"
        assert tx.external_id == _fake.checkout_id
        assert tx.status == Transaction.Status.PENDING

    @override_settings(**ASAAS_SETTINGS)
    def test_checkout_asaas_paid_webhook_confirms(self):
        from apps.payments.models import Transaction

        user = self._login()
        with mock_asaas() as _fake:
            product = make_product(stock=10)
            self._with_cart(product, qty=1)
            self.client.post(reverse("checkout"))
        order = Order.objects.filter(user=user).latest("created_at")
        tx = Transaction.objects.get(order=order)

        import json

        from apps.payments.services import AsaasGateway

        payload = json.dumps(
            {
                "event": "CHECKOUT_PAID",
                "checkout": {"id": _fake.checkout_id, "externalReference": str(order.pk)},
            }
        )
        AsaasGateway().webhook(payload, {"x-webhook-token": "segredo"})

        tx.refresh_from_db()
        order.refresh_from_db()
        assert tx.status == Transaction.Status.PAID
        assert order.status == Order.Status.PAID

    @override_settings(**ASAAS_SETTINGS)
    def test_checkout_credit_card_missing_cpf_still_checkout_hosted(self):
        from apps.payments.models import Transaction

        user = self._login()
        with mock_asaas() as _fake:
            product = make_product(stock=10)
            self._with_cart(product, qty=1)
            self.client.post(
                reverse("checkout"),
                {
                    "payment_method": "CREDIT_CARD",
                    "card_number": "4111111111111111",
                    "card_expiry_month": "12",
                    "card_expiry_year": "2035",
                    "card_ccv": "123",
                },
            )
        order = Order.objects.filter(user=user).latest("created_at")
        assert order.status == Order.Status.AWAITING_PAYMENT
        tx = Transaction.objects.get(order=order)
        assert tx.provider == "asaas"
        assert tx.external_id == _fake.checkout_id


class TestReferralCreation(TestCase):
    def test_checkout_creates_referral_with_cookie(self):
        user = make_user()
        affiliate = make_affiliate()
        self.client.force_login(user)
        self.client.cookies[settings.AFFILIATE_COOKIE_NAME] = affiliate.code
        product = make_product(stock=10, price=100)
        self.client.post(reverse("checkout-cart-add", args=[product.pk]), {"qty": "1"})
        self.client.post(reverse("checkout"))

        order = Order.objects.filter(user=user).latest("created_at")
        referral = Referral.objects.get(affiliate=affiliate, order=order)
        assert referral.referred == user
        assert referral.commission_amount == order.total * affiliate.commission_rate

    def test_no_referral_without_cookie(self):
        user = make_user()
        affiliate = make_affiliate()
        self.client.force_login(user)
        product = make_product(stock=10)
        self.client.post(reverse("checkout-cart-add", args=[product.pk]), {"qty": "1"})
        self.client.post(reverse("checkout"))
        assert Referral.objects.filter(affiliate=affiliate).count() == 0


class TestCheckoutRoleSeparation(TestCase):
    def test_checkout_restrito_a_cliente(self):
        from apps.accounts.models import CustomUser

        for role in (CustomUser.Role.PRESTADOR, CustomUser.Role.AFILIADO):
            with self.subTest(role=role):
                user = make_user(role=role)
                self.client.force_login(user)
                response = self.client.get(reverse("checkout"))
                assert response.status_code == 403

    def test_address_restrito_a_cliente(self):
        from apps.accounts.models import CustomUser

        user = make_user(role=CustomUser.Role.AFILIADO)
        self.client.force_login(user)
        response = self.client.get(reverse("checkout-address"))
        assert response.status_code == 403

    def test_admin_pode_acessar_checkout(self):
        from apps.accounts.models import CustomUser

        admin = make_user(role=CustomUser.Role.ADMIN)
        self.client.force_login(admin)
        response = self.client.get(reverse("checkout"))
        assert response.status_code in (200, 302)
