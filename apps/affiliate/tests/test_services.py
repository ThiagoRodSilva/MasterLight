"""Testes do programa de afiliados (middleware + services)."""

from django.conf import settings
from django.test import Client, TestCase

from apps.affiliate.services import create_payout_request
from apps.checkout.models import Order
from apps.tests.helpers import create_order, make_affiliate, make_user


class TestAffiliateReferralMiddleware(TestCase):
    def test_cookie_set_on_valid_ref(self):
        affiliate = make_affiliate()
        response = Client().get(f"/?ref={affiliate.code}")
        assert settings.AFFILIATE_COOKIE_NAME in response.cookies
        cookie = response.cookies[settings.AFFILIATE_COOKIE_NAME]
        assert cookie.value == affiliate.code
        assert int(cookie["max-age"]) == settings.AFFILIATE_COOKIE_MAX_AGE

    def test_no_cookie_on_invalid_ref(self):
        response = Client().get("/?ref=CODIGO-INVALIDO")
        assert settings.AFFILIATE_COOKIE_NAME not in response.cookies

    def test_no_cookie_without_ref_param(self):
        response = Client().get("/")
        assert settings.AFFILIATE_COOKIE_NAME not in response.cookies


class TestApproveReferral(TestCase):
    def test_order_paid_without_referral(self):
        user = make_user()
        order = create_order(user, with_referral=False)
        tx = order.transactions.first()
        tx.status = "paid"
        tx.save(update_fields=["status", "updated_at"])
        order.refresh_from_db()
        assert order.status == Order.Status.PAID

    def test_paid_order_decrements_stock(self):
        user = make_user()
        order = create_order(user, with_referral=False, qty=3)
        product = order.items.first().product
        initial_stock = product.stock
        tx = order.transactions.first()
        tx.status = "paid"
        tx.save(update_fields=["status", "updated_at"])
        product.refresh_from_db()
        assert product.stock == initial_stock - 3

    def test_unpaid_order_does_not_decrement_stock(self):
        user = make_user()
        order = create_order(user, with_referral=False, qty=3)
        product = order.items.first().product
        initial_stock = product.stock
        product.refresh_from_db()
        assert product.stock == initial_stock

    def test_order_paid_and_balance_credited_with_referral(self):
        user = make_user()
        order = create_order(user, with_referral=True)
        referral = order.referrals.first()
        tx = order.transactions.first()
        tx.status = "paid"
        tx.save(update_fields=["status", "updated_at"])
        order.refresh_from_db()
        referral.refresh_from_db()
        affiliate = referral.affiliate
        affiliate.refresh_from_db()
        assert order.status == Order.Status.PAID
        assert referral.status == referral.Status.APPROVED
        assert affiliate.balance == referral.commission_amount

    def test_refund_does_not_touch_order(self):
        user = make_user()
        order = create_order(user, with_referral=True)
        tx = order.transactions.first()
        tx.status = "refunded"
        tx.save(update_fields=["status", "updated_at"])
        order.refresh_from_db()
        assert order.status == Order.Status.AWAITING_PAYMENT


class TestCreatePayoutRequest(TestCase):
    def test_requires_pix_key(self):
        affiliate = make_affiliate()
        affiliate.balance = 100
        affiliate.save(update_fields=["balance"])
        with self.assertRaisesRegex(ValueError, "chave Pix"):
            create_payout_request(affiliate)

    def test_insufficient_balance_raises(self):
        affiliate = make_affiliate()
        affiliate.balance = 0
        affiliate.pix_key = "email@exemplo.com"
        affiliate.save(update_fields=["balance", "pix_key"])
        with self.assertRaises(ValueError):
            create_payout_request(affiliate)

    def test_payout_zeroes_balance(self):
        affiliate = make_affiliate()
        affiliate.balance = 100
        affiliate.pix_key = "email@exemplo.com"
        affiliate.save(update_fields=["balance", "pix_key"])
        payout = create_payout_request(affiliate)
        assert payout.amount == 100
        affiliate.refresh_from_db()
        assert affiliate.balance == 0
