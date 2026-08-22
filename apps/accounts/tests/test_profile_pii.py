"""Testes de vazamento de PII no ProfileDetailView."""

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import CustomUser, PublicProfile
from apps.tests.helpers import make_user


class TestProfileDetailViewPII(TestCase):
    def setUp(self):
        self.client_user = make_user(role=CustomUser.Role.CLIENTE, email="cliente@exemplo.com")
        self.prestador_user = make_user(role=CustomUser.Role.PRESTADOR, email="prestador@exemplo.com")
        self.afiliado_user = make_user(role=CustomUser.Role.AFILIADO, email="afiliado@exemplo.com")
        # Atualiza PublicProfile criado pelo signal para is_active=True
        PublicProfile.objects.filter(user=self.prestador_user).update(is_active=True)
        PublicProfile.objects.filter(user=self.afiliado_user).update(is_active=True)

    def test_client_profile_returns_404(self):
        """Perfil de cliente (role=cliente) retorna 404."""
        url = reverse("accounts-profile", kwargs={"username": self.client_user.username})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_prestador_with_public_profile_returns_200(self):
        """Prestador com public_profile ativo retorna 200."""
        url = reverse("accounts-profile", kwargs={"username": self.prestador_user.username})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_afiliado_with_public_profile_returns_200(self):
        """Afiliado com public_profile ativo retorna 200."""
        url = reverse("accounts-profile", kwargs={"username": self.afiliado_user.username})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_html_does_not_contain_full_email_when_no_name(self):
        """HTML não contém email completo quando usuário não tem nome."""
        # Prestador sem first_name/last_name
        self.prestador_user.first_name = ""
        self.prestador_user.last_name = ""
        self.prestador_user.save()
        url = reverse("accounts-profile", kwargs={"username": self.prestador_user.username})
        response = self.client.get(url)
        content = response.content.decode()
        # Não deve vazar o email completo
        self.assertNotIn("prestador@exemplo.com", content)
        # Deve mostrar versão mascarada do email (primeiras 3 letras + ***)
        masked = self.prestador_user.username.split("@")[0][:3] + "***"
        self.assertIn(masked, content)

    def test_prestador_without_public_profile_returns_404(self):
        """Prestador sem public_profile ativo retorna 404."""
        PublicProfile.objects.filter(user=self.prestador_user).update(is_active=False)
        url = reverse("accounts-profile", kwargs={"username": self.prestador_user.username})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_inactive_user_returns_404(self):
        """Usuário inativo retorna 404."""
        self.prestador_user.is_active = False
        self.prestador_user.save()
        url = reverse("accounts-profile", kwargs={"username": self.prestador_user.username})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
