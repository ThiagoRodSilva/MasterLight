"""Testes do middleware de afiliado (cookie secure)."""

from django.test import TestCase, override_settings

from apps.tests.helpers import make_affiliate


class TestAffiliateMiddlewareSecureCookie(TestCase):
    @override_settings(DEBUG=False)
    def test_cookie_secure_true_when_debug_false(self):
        """Com DEBUG=False, cookie 'ref' deve ter secure=True."""
        affiliate = make_affiliate()
        response = self.client.get(f"/?ref={affiliate.code}")
        self.assertEqual(response.status_code, 200)
        cookie = response.cookies.get("ref")
        self.assertIsNotNone(cookie)
        self.assertTrue(cookie["secure"])

    @override_settings(DEBUG=True)
    def test_cookie_secure_false_when_debug_true(self):
        """Com DEBUG=True, cookie 'ref' pode ter secure=False (dev)."""
        affiliate = make_affiliate()
        response = self.client.get(f"/?ref={affiliate.code}")
        self.assertEqual(response.status_code, 200)
        cookie = response.cookies.get("ref")
        self.assertIsNotNone(cookie)
        # Em dev, secure pode ser False
        self.assertFalse(cookie["secure"])
