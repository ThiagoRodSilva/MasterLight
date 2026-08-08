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


class TestPayoutView:
    def test_payout_zero_saldo_locked(self, affiliate_profile, client):
        client.force_login(affiliate_profile.user)
        response = client.post(reverse("affiliate-payout"))
        assert response.status_code == 302
        assert not PayoutRequest.objects.filter(affiliate=affiliate_profile).exists()
