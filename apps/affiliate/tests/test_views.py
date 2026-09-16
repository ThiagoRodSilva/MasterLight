"""Testes de views do app affiliate (landing + dashboard + saque)."""

from django.test import TestCase
from django.urls import reverse

from apps.affiliate.models import PayoutRequest, Referral
from apps.tests.helpers import make_affiliate, make_user


class TestAffiliateLanding(TestCase):
    def setUp(self):
        from apps.core.models import SiteSettings

        settings = SiteSettings.objects.get_or_create(pk=1)[0]
        settings.affiliates_enabled = True
        settings.save(update_fields=["affiliates_enabled"])

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

    def test_dashboard_shows_total_referral_count_not_page_length(self):
        """Dashboard mostra total de indicações (referral_count), não apenas a página atual."""
        affiliate = make_affiliate()
        self.client.force_login(affiliate.user)

        # Cria 25 referrals (paginate_by=20, então página 1 tem 20)
        for i in range(25):
            Referral.objects.create(
                affiliate=affiliate,
                referred=make_user(email=f"ref{i}@ex.com"),
                commission_amount=10.00,
                commission_rate=0.10,
                status=Referral.Status.APPROVED,
            )

        response = self.client.get(reverse("affiliate-dashboard"))
        content = response.content.decode()
        # Deve mostrar "25" (total), não "20" (página atual)
        self.assertIn("25", content)
        self.assertNotIn(">20<", content)  # não deve mostrar só 20 no card de totais

    def test_dashboard_shows_commission_rate_as_percentage(self):
        """Dashboard mostra taxa de comissão como porcentagem (ex.: 10%), não decimal (0.10%)."""
        affiliate = make_affiliate()
        # commission_rate default é 0.10 (10%)
        self.client.force_login(affiliate.user)

        response = self.client.get(reverse("affiliate-dashboard"))
        content = response.content.decode()
        # Deve mostrar "10%" (widthratio multiplica por 100)
        self.assertIn("10%", content)
        # Não deve mostrar "0.10%"
        self.assertNotIn("0.10%", content)

    def test_dashboard_prefetches_payouts(self):
        """Dashboard deve usar prefetch para payouts (referrals + payouts prefetched)."""
        affiliate = make_affiliate()
        self.client.force_login(affiliate.user)

        # Framework: session + user + socialaccount + sitesettings = 4
        # View: profile (1) + referrals (1) + payouts (1 via prefetch) + referral_count (1) + sitesettings again (1)
        # Total: 9
        with self.assertNumQueries(9):
            response = self.client.get(reverse("affiliate-dashboard"))
        assert response.status_code == 200


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
