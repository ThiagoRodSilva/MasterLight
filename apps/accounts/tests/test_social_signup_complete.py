"""Testes da view de completamento social."""

from unittest import mock
from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.messages.middleware import MessageMiddleware
from allauth.socialaccount.models import SocialLogin

from apps.accounts.models import CustomUser
from apps.accounts.views import SocialSignupCompleteView
from apps.checkout.models import Address


class SocialSignupCompleteViewTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.view = SocialSignupCompleteView.as_view()
        self.url = reverse("social_signup_complete")

    def _add_middleware(self, request):
        """Adiciona session e messages middleware mock ao request."""
        SessionMiddleware(lambda r: None).process_request(request)
        MessageMiddleware(lambda r: None).process_request(request)
        request.session.save()

    def test_dispatch_without_sociallogin_redirects_login(self):
        """Sem sociallogin na sessão -> redirect login."""
        request = self.factory.get(self.url)
        self._add_middleware(request)
        request.user = CustomUser.objects.create_user(username="u", email="u@t.com", password="x")
        response = self.view(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn("social/login", response.url)

    def test_form_valid_creates_address_and_logs_in(self):
        """Form válido -> cria Address, conecta SocialAccount, loga usuário."""
        user = CustomUser.objects.create_user(username="social", email="social@test.com", password="x")
        sociallogin = mock.Mock(spec=SocialLogin)
        sociallogin.user = user
        sociallogin.connect = mock.Mock()

        request = self.factory.post(self.url, {
            "role": "cliente",
            "cpf": "123.456.789-09",
            "telefone": "11999999999",
            "street": "Rua Teste",
            "number": "123",
            "city": "São Paulo",
            "state": "SP",
            "zip_code": "01234567",
            "country": "Brasil",
        })
        self._add_middleware(request)
        request.session["sociallogin"] = {"mock": "data"}
        request.user = user

        with mock.patch("allauth.socialaccount.models.SocialLogin.deserialize", return_value=sociallogin):
            response = self.view(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")
        user.refresh_from_db()
        self.assertEqual(user.cpf, "12345678909")
        self.assertEqual(user.telefone, "11999999999")
        self.assertTrue(Address.objects.filter(user=user).exists())
        sociallogin.connect.assert_called_once()

    def test_form_invalid_renders_errors(self):
        """Form inválido -> re-render com erros."""
        request = self.factory.post(self.url, {})  # dados vazios
        self._add_middleware(request)
        request.session["sociallogin"] = {}
        request.user = CustomUser.objects.create_user(username="u", email="u@t.com", password="x")
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Este campo é obrigatório")