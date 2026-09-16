"""Testes do middleware de completamento social."""

from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.accounts.middleware import SocialSignupRequiredMiddleware
from apps.accounts.models import CustomUser
from apps.checkout.models import Address

User = get_user_model()


class SocialSignupRequiredMiddlewareTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = SocialSignupRequiredMiddleware(lambda r: None)
        self.url = "/some-protected-page/"

    def _add_middleware(self, request):
        SessionMiddleware(lambda r: None).process_request(request)
        MessageMiddleware(lambda r: None).process_request(request)
        request.session.save()

    def _create_social_user(self, **kwargs):
        """Cria usuário com SocialAccount (simula login social)."""
        defaults = {
            "username": "social@test.com",
            "email": "social@test.com",
            "password": "testpass123",
            "role": CustomUser.Role.CLIENTE,
            "cpf": "",
            "telefone": "",
        }
        defaults.update(kwargs)
        user = User.objects.create_user(**defaults)
        SocialAccount.objects.create(user=user, provider="google", uid="12345")
        return user

    def test_allows_access_with_complete_profile(self):
        """Usuário social com perfil completo acessa página normalmente."""
        user = self._create_social_user(cpf="12345678901", telefone="11999999999")
        Address.objects.create(
            user=user,
            street="Rua Teste",
            number="123",
            city="São Paulo",
            state="SP",
            zip_code="01234567",
            country="Brasil",
        )
        request = self.factory.get(self.url)
        self._add_middleware(request)
        request.user = user

        response = self.middleware(request)
        # Não deve redirecionar (retorna None ou response do get_response)
        self.assertIsNone(response)

    def test_redirects_incomplete_profile(self):
        """Usuário social sem CPF/telefone/endereço é redirecionado."""
        user = self._create_social_user()
        request = self.factory.get(self.url)
        self._add_middleware(request)
        request.user = user

        response = self.middleware(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/social/completar-cadastro/", response.url)

    def test_allows_exempt_urls(self):
        """URLs isentas (como login, home) são acessíveis mesmo com perfil incompleto."""
        user = self._create_social_user()
        for url_name in ["account_login", "home", "social_signup_complete", "accounts-me"]:
            with self.subTest(url=url_name):
                url = reverse(url_name)
                request = self.factory.get(url)
                self._add_middleware(request)
                request.user = user

                response = self.middleware(request)
                self.assertIsNone(response, f"URL {url_name} deveria ser isenta")

    def test_allows_non_social_users(self):
        """Usuários cadastrados por email/senha (sem SocialAccount) não são bloqueados."""
        user = User.objects.create_user(
            username="normal@test.com",
            email="normal@test.com",
            password="testpass123",
            role=CustomUser.Role.CLIENTE,
            cpf="",
            telefone="",
        )
        request = self.factory.get(self.url)
        self._add_middleware(request)
        request.user = user

        response = self.middleware(request)
        self.assertIsNone(response)

    def test_allows_superuser(self):
        """Superuser nunca é bloqueado."""
        user = User.objects.create_superuser(
            username="admin@test.com", email="admin@test.com", password="testpass123"
        )
        request = self.factory.get(self.url)
        self._add_middleware(request)
        request.user = user

        response = self.middleware(request)
        self.assertIsNone(response)

    def test_allows_admin_urls(self):
        """URLs do admin são isentas."""
        user = self._create_social_user()
        request = self.factory.get("/admin/")
        self._add_middleware(request)
        request.user = user

        response = self.middleware(request)
        self.assertIsNone(response)
