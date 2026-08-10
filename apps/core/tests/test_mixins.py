"""Testes dos role-mixins para usuários anônimos (redireciona para login)."""

from django.test import TestCase
from django.urls import reverse


class TestRoleMixinsAnonymous(TestCase):
    def test_provider_mixin_redirects_anonymous(self):
        response = self.client.get(reverse("services-create"))
        assert response.status_code in (302, 403)
        assert self.client.session.get("_auth_user_id") is None

    def test_affiliate_mixin_redirects_anonymous(self):
        response = self.client.get(reverse("affiliate-dashboard"))
        assert response.status_code in (302, 403)

    def test_cliente_mixin_redirects_anonymous(self):
        response = self.client.get(reverse("services-plan-subscribe"))
        assert response.status_code in (302, 403)

    def test_cliente_mixin_redirects_prestador(self):
        from apps.accounts.models import CustomUser
        from apps.tests.helpers import make_user

        provider = make_user(role=CustomUser.Role.PRESTADOR)
        self.client.force_login(provider)
        response = self.client.get(reverse("services-plan-subscribe"))
        assert response.status_code in (302, 403)
