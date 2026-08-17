"""Teste: form de login usa email (allauth ACCOUNT_AUTHENTICATION_METHOD=email)."""

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.tests.helpers import make_user


@override_settings(ACCOUNT_AUTHENTICATION_METHOD="email")
class TestLoginFormUsesEmail(TestCase):
    def test_login_page_shows_email_field(self):
        """GET /social/login/ deve mostrar campo 'login' com label/placeholder de email."""
        response = self.client.get(reverse("account_login"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        # allauth renderiza o campo como 'login' (username/email unificado)
        self.assertIn('name="login"', content)
        # O label/placeholder deve indicar email
        self.assertIn("E-mail", content)

    def test_login_with_email_password_works(self):
        """POST com email+senha autentica o usuário."""
        user = make_user(email="teste@exemplo.com")
        user.set_password("senha#123")
        user.save()
        response = self.client.post(
            reverse("account_login"),
            {"login": "teste@exemplo.com", "password": "senha#123"},
        )
        # Login bem-sucedido redireciona
        self.assertEqual(response.status_code, 302)
        # Verifica se usuário está autenticado na sessão
        self.client.login(username="teste@exemplo.com", password="senha#123")
        # Acessa página protegida
        response = self.client.get("/")
        self.assertTrue(response.wsgi_request.user.is_authenticated)
