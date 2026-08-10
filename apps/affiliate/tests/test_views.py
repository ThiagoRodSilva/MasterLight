"""Testes de views do app affiliate (landing + dashboard + saque)."""

import pytest
from django.urls import reverse

from apps.affiliate.models import PayoutRequest

pytestmark = pytest.mark.django_db


class TestAffiliateLanding:
    def test_landing_public_200(self, client):
        response = client.get(reverse("affiliate-landing"))
        assert response.status_code == 200

    def test_landing_shows_join_cta_for_anonymous(self, client):
        response = client.get(reverse("affiliate-landing"))
        assert b"Cadastre-se" in response.content or b"Come" in response.content

    def test_landing_shows_link_for_afiliado(self, affiliate_profile, client):
        client.force_login(affiliate_profile.user)
        response = client.get(reverse("affiliate-landing"))
        assert response.status_code == 200
        assert affiliate_profile.code in response.content.decode()


class TestAffiliateDashboard:
    def test_dashboard_requires_afiliado(self, user, client):
        client.force_login(user)
        response = client.get(reverse("affiliate-dashboard"))
        assert response.status_code in (302, 403)

    def test_dashboard_ok_for_afiliado(self, affiliate_profile, client):
        client.force_login(affiliate_profile.user)
        response = client.get(reverse("affiliate-dashboard"))
        assert response.status_code == 200

    def test_dashboard_404_when_profile_missing(self, client):
        from apps.accounts.models import CustomUser
        from apps.affiliate.models import AffiliateProfile
        from conftest import UserFactory

        user = UserFactory(role=CustomUser.Role.AFILIADO)
        AffiliateProfile.objects.filter(user=user).delete()
        client.force_login(user)
        response = client.get(reverse("affiliate-dashboard"))
        assert response.status_code == 404


class TestPixKeyView:
    def test_pix_key_requires_afiliado(self, user, client):
        client.force_login(user)
        response = client.post(reverse("affiliate-pix-key"), {"pix_key": "email@ex.com"})
        assert response.status_code in (302, 403)

    def test_pix_key_saved(self, affiliate_profile, client):
        client.force_login(affiliate_profile.user)
        response = client.post(reverse("affiliate-pix-key"), {"pix_key": "email@exemplo.com"})
        assert response.status_code == 302
        affiliate_profile.refresh_from_db()
        assert affiliate_profile.pix_key == "email@exemplo.com"

    def test_pix_key_blank_rejected(self, affiliate_profile, client):
        client.force_login(affiliate_profile.user)
        response = client.post(reverse("affiliate-pix-key"), {"pix_key": "   "})
        assert response.status_code == 302
        affiliate_profile.refresh_from_db()
        assert affiliate_profile.pix_key == ""

    def test_pix_key_updated(self, affiliate_profile, client):
        affiliate_profile.pix_key = "12345678901"
        affiliate_profile.save(update_fields=["pix_key"])
        client.force_login(affiliate_profile.user)
        client.post(reverse("affiliate-pix-key"), {"pix_key": "11999999999"})
        affiliate_profile.refresh_from_db()
        assert affiliate_profile.pix_key == "11999999999"

    def test_pix_key_blocked_when_affiliates_disabled(self, affiliate_profile, client):
        from apps.core.models import SiteSettings

        settings = SiteSettings.load()
        settings.affiliates_enabled = False
        settings.save(update_fields=["affiliates_enabled"])
        client.force_login(affiliate_profile.user)
        response = client.post(reverse("affiliate-pix-key"), {"pix_key": "email@ex.com"})
        assert response.status_code == 404


class TestPayoutView:
    def test_payout_zero_saldo_locked(self, affiliate_profile, client):
        client.force_login(affiliate_profile.user)
        response = client.post(reverse("affiliate-payout"))
        assert response.status_code == 302
        assert not PayoutRequest.objects.filter(affiliate=affiliate_profile).exists()

    def test_payout_requires_afiliado(self, user, client):
        client.force_login(user)
        response = client.post(reverse("affiliate-payout"))
        assert response.status_code in (302, 403)
        assert not PayoutRequest.objects.exists()

    def test_payout_blocked_when_affiliates_disabled(self, affiliate_profile, client):
        from apps.core.models import SiteSettings

        settings = SiteSettings.load()
        settings.affiliates_enabled = False
        settings.save(update_fields=["affiliates_enabled"])
        client.force_login(affiliate_profile.user)
        response = client.post(reverse("affiliate-payout"))
        assert response.status_code == 404
