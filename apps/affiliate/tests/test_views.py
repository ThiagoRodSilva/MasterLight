"""Testes de views do app affiliate (landing + dashboard + saque)."""

from django.test import TestCase
from django.urls import reverse

from apps.affiliate.models import PayoutRequest
from apps.tests.helpers import make_affiliate, make_user


class TestAffiliateLanding(TestCase):
    def test_landing_public_200(self):
        response = self.client.get(reverse("affiliate-landing"))
        assert response.status_code == 200

    def test_landing_shows_join_cta_for_anonymous(self):
        response = self.client.get(reverse("affiliate-landing"))
        assert b"Cadastre-se" in response.content or b"Come" in response.content

    def test_landing_shows_link_for_afiliado(self):
        affiliate = make_affiliate()
        self.client.force_login(affiliate.user)
        response = self.client.get(reverse("affiliate-landing"))
        assert response.status_code == 200
        assert affiliate.code in response.content.decode()


class TestAffiliateDashboard(TestCase):
    def test_dashboard_requires_afiliado(self):
        user = make_user()
        self.client.force_login(user)
        response = self.client.get(reverse("affiliate-dashboard"))
        assert response.status_code in (302, 403)

    def test_dashboard_ok_for_afiliado(self):
        affiliate = make_affiliate()
        self.client.force_login(affiliate.user)
        response = self.client.get(reverse("affiliate-dashboard"))
        assert response.status_code == 200

    def test_dashboard_404_when_profile_missing(self):
        from apps.accounts.models import CustomUser
        from apps.affiliate.models import AffiliateProfile

        user = make_user(role=CustomUser.Role.AFILIADO)
        AffiliateProfile.objects.filter(user=user).delete()
        self.client.force_login(user)
        response = self.client.get(reverse("affiliate-dashboard"))
        assert response.status_code == 404


class TestPixKeyView(TestCase):
    def _login(self, affiliate):
        self.client.force_login(affiliate.user)
        return affiliate

    def test_pix_key_requires_afiliado(self):
        user = make_user()
        self.client.force_login(user)
        response = self.client.post(reverse("affiliate-pix-key"), {"pix_key": "email@ex.com"})
        assert response.status_code in (302, 403)

    def test_pix_key_saved(self):
        affiliate = self._login(make_affiliate())
        response = self.client.post(reverse("affiliate-pix-key"), {"pix_key": "email@exemplo.com"})
        assert response.status_code == 302
        affiliate.refresh_from_db()
        assert affiliate.pix_key == "email@exemplo.com"

    def test_pix_key_blank_rejected(self):
        affiliate = self._login(make_affiliate())
        response = self.client.post(reverse("affiliate-pix-key"), {"pix_key": "   "})
        assert response.status_code == 302
        affiliate.refresh_from_db()
        assert affiliate.pix_key == ""

    def test_pix_key_updated(self):
        affiliate = make_affiliate()
        affiliate.pix_key = "12345678901"
        affiliate.save(update_fields=["pix_key"])
        self.client.force_login(affiliate.user)
        self.client.post(reverse("affiliate-pix-key"), {"pix_key": "11999999999"})
        affiliate.refresh_from_db()
        assert affiliate.pix_key == "11999999999"

    def test_pix_key_blocked_when_affiliates_disabled(self):
        from apps.core.models import SiteSettings

        settings = SiteSettings.load()
        settings.affiliates_enabled = False
        settings.save(update_fields=["affiliates_enabled"])
        self._login(make_affiliate())
        response = self.client.post(reverse("affiliate-pix-key"), {"pix_key": "email@ex.com"})
        assert response.status_code == 404


class TestPayoutView(TestCase):
    def test_payout_zero_saldo_locked(self):
        affiliate = make_affiliate()
        self.client.force_login(affiliate.user)
        response = self.client.post(reverse("affiliate-payout"))
        assert response.status_code == 302
        assert not PayoutRequest.objects.filter(affiliate=affiliate).exists()

    def test_payout_requires_afiliado(self):
        user = make_user()
        self.client.force_login(user)
        response = self.client.post(reverse("affiliate-payout"))
        assert response.status_code in (302, 403)
        assert not PayoutRequest.objects.exists()

    def test_payout_blocked_when_affiliates_disabled(self):
        from apps.core.models import SiteSettings

        settings = SiteSettings.load()
        settings.affiliates_enabled = False
        settings.save(update_fields=["affiliates_enabled"])
        affiliate = make_affiliate()
        self.client.force_login(affiliate.user)
        response = self.client.post(reverse("affiliate-payout"))
        assert response.status_code == 404
