"""Testes do CustomSocialAccountAdapter."""

from unittest import mock
from django.test import TestCase, RequestFactory
from allauth.socialaccount.models import SocialLogin

from apps.accounts.adapters import CustomSocialAccountAdapter
from apps.accounts.models import CustomUser


class CustomSocialAccountAdapterTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.adapter = CustomSocialAccountAdapter()
        self.request = self.factory.get("/")
        self.request.session = {}

    def test_is_auto_signup_allowed_false(self):
        """Nunca permite auto-signup direto."""
        sociallogin = mock.Mock(spec=SocialLogin)
        self.assertFalse(self.adapter.is_auto_signup_allowed(self.request, sociallogin))

    def test_pre_social_login_existing_user_connects(self):
        """Usuário existente -> conecta SocialAccount."""
        user = CustomUser.objects.create_user(
            username="existing", email="existing@test.com", password="x"
        )
        sociallogin = mock.Mock(spec=SocialLogin)
        sociallogin.user = mock.Mock()
        sociallogin.user.email = "existing@test.com"
        sociallogin.connect = mock.Mock()

        self.adapter.pre_social_login(self.request, sociallogin)
        sociallogin.connect.assert_called_once_with(self.request, user)

    def test_pre_social_login_new_user_stores_session(self):
        """Novo usuário -> guarda na sessão."""
        sociallogin = mock.Mock(spec=SocialLogin)
        sociallogin.user = mock.Mock()
        sociallogin.user.email = "new@test.com"
        sociallogin.serialize.return_value = {"serialized": "data"}

        self.adapter.pre_social_login(self.request, sociallogin)
        self.assertEqual(self.request.session["sociallogin"], {"serialized": "data"})

    def test_save_user_creates_cliente_role(self):
        """Cria usuário com role=cliente."""
        sociallogin = mock.Mock(spec=SocialLogin)
        user = CustomUser.objects.create_user(username="social", email="social@test.com", password="x")
        sociallogin.user = user
        result_user = self.adapter.save_user(self.request, sociallogin)
        self.assertEqual(result_user.role, CustomUser.Role.CLIENTE)

    def test_get_signup_redirect_url(self):
        """Redireciona para completamento."""
        url = self.adapter.get_signup_redirect_url(self.request)
        self.assertEqual(url, "/social/completar-cadastro/")