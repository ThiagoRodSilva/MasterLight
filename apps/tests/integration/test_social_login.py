"""Integração ponta a ponta: Social Login completo (Google/Facebook/Apple via allauth)."""

from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from allauth.socialaccount.models import SocialAccount, SocialApp, SocialToken
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client

from apps.accounts.models import CustomUser
from apps.core.models import SiteSettings
from apps.tests.helpers import make_user


SOCIAL_SETTINGS = {
    "SOCIALACCOUNT_PROVIDERS": {
        "google": {
            "APP": {"client_id": "test-google-id", "secret": "test-google-secret"},
            "SCOPE": ["profile", "email"],
            "AUTH_PARAMS": {"access_type": "online"},
        },
        "facebook": {
            "APP": {"client_id": "test-fb-id", "secret": "test-fb-secret"},
            "SCOPE": ["email", "public_profile"],
            "AUTH_PARAMS": {"auth_type": "reauthenticate"},
        },
        "apple": {
            "APP": {"client_id": "test-apple-id", "secret": "test-apple-secret"},
            "SCOPE": ["name", "email"],
        },
    },
    "ACCOUNT_EMAIL_VERIFICATION": "none",
    "SOCIALACCOUNT_LOGIN_ON_GET": True,
    "SOCIALACCOUNT_AUTO_SIGNUP": True,
}


@override_settings(**SOCIAL_SETTINGS)
class TestSocialLoginFlow(TestCase):
    """Fluxo completo: login social -> criação de usuário -> perfil incompleto -> completamento."""

    def setUp(self):
        # Limpa SocialApps existentes para evitar MultipleObjectsReturned
        SocialApp.objects.all().delete()
        
        SiteSettings.objects.get(pk=1).provider_registration_enabled = True
        SiteSettings.objects.get(pk=1).save()

        self.google_app, _ = SocialApp.objects.get_or_create(
            provider="google",
            defaults={"name": "Google Test", "client_id": "test-google-id", "secret": "test-google-secret"},
        )
        self.google_app.sites.add(SiteSettings.objects.get(pk=1).pk)

    def _mock_google_login(self, email="social@test.com", name="Social User", uid="google-123"):
        """Mock do fluxo OAuth2 do Google."""
        with mock.patch("allauth.socialaccount.providers.oauth2.views.OAuth2Adapter.complete_login") as mock_complete:
            mock_user = mock.MagicMock()
            mock_user.email = email
            mock_user.first_name = name.split()[0] if name else ""
            mock_user.last_name = name.split()[-1] if len(name.split()) > 1 else ""
            mock_complete.return_value.get_user.return_value = mock_user

            with mock.patch("allauth.socialaccount.providers.oauth2.views.OAuth2Client") as mock_client:
                mock_client_instance = mock.MagicMock()
                mock_client_instance.get_access_token.return_value = "fake-token"
                mock_client_instance.get_user_info.return_value = {
                    "sub": uid,
                    "email": email,
                    "name": name,
                    "given_name": name.split()[0] if name else "",
                    "family_name": name.split()[-1] if len(name.split()) > 1 else "",
                    "email_verified": True,
                }
                mock_client.return_value = mock_client_instance

                response = self.client.get(reverse("google_login") + "?code=fake-code", follow=True)
                return response

    def test_google_login_creates_user_and_logs_in(self):
        """Login Google cria usuário e loga automaticamente (email verification none)."""
        response = self._mock_google_login()
        self.assertEqual(response.status_code, 200)

        user = CustomUser.objects.get(email="social@test.com")
        self.assertTrue(user.is_active)
        self.assertEqual(user.role, CustomUser.Role.CLIENTE)

        social_account = SocialAccount.objects.get(user=user, provider="google")
        self.assertEqual(social_account.uid, "google-123")
        self.assertEqual(social_account.extra_data["email"], "social@test.com")

        self.assertTrue("_auth_user_id" in self.client.session)

    def test_google_login_existing_user_links_account(self):
        """Login Google em email existente vincula SocialAccount."""
        existing_user = make_user(email="social@test.com", role="cliente")
        existing_user.set_unusable_password()
        existing_user.save()

        response = self._mock_google_login()
        self.assertEqual(response.status_code, 200)

        user = CustomUser.objects.get(email="social@test.com")
        self.assertEqual(user.pk, existing_user.pk)
        social_account = SocialAccount.objects.get(user=user, provider="google")
        self.assertIsNotNone(social_account)

    def test_google_login_incomplete_profile_redirects(self):
        """Usuário social sem CPF/telefone/endereço é redirecionado para completamento."""
        response = self._mock_google_login()
        self.assertEqual(response.status_code, 200)

        user = CustomUser.objects.get(email="social@test.com")
        self.assertFalse(user.cpf)
        self.assertFalse(user.telefone)
        self.assertFalse(user.addresses.filter(is_active=True).exists())

        response = self.client.get(reverse("dashboard"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Complete seu cadastro")

    def test_social_user_complete_profile(self):
        """Usuário social completa perfil com CPF, telefone e endereço."""
        self._mock_google_login()

        user = CustomUser.objects.get(email="social@test.com")
        self.client.force_login(user)

        response = self.client.post(
            reverse("account_profile"),
            {
                "cpf": "12345678901",
                "telefone": "11999999999",
                "cep": "01000-000",
                "logradouro": "Rua Teste",
                "numero": "123",
                "bairro": "Centro",
                "cidade": "São Paulo",
                "estado": "SP",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        user.refresh_from_db()
        self.assertEqual(user.cpf, "12345678901")
        self.assertEqual(user.telefone, "11999999999")
        self.assertTrue(user.addresses.filter(is_active=True).exists())

        response = self.client.get(reverse("dashboard"), follow=True)
        self.assertNotContains(response, "Complete seu cadastro")

    def test_facebook_login_flow(self):
        """Login Facebook segue mesmo fluxo."""
        fb_app, _ = SocialApp.objects.get_or_create(
            provider="facebook",
            defaults={"name": "Facebook Test", "client_id": "test-fb-id", "secret": "test-fb-secret"},
        )
        fb_app.sites.add(SiteSettings.objects.get(pk=1).pk)

        with mock.patch("allauth.socialaccount.providers.facebook.views.FacebookOAuth2Adapter.complete_login") as mock_complete:
            mock_user = mock.MagicMock()
            mock_user.email = "fb@test.com"
            mock_user.first_name = "Facebook"
            mock_user.last_name = "User"
            mock_complete.return_value.get_user.return_value = mock_user

            with mock.patch("allauth.socialaccount.providers.oauth2.views.OAuth2Client") as mock_client:
                mock_client_instance = mock.MagicMock()
                mock_client_instance.get_access_token.return_value = "fake-fb-token"
                mock_client_instance.get_user_info.return_value = {
                    "id": "fb-123",
                    "email": "fb@test.com",
                    "name": "Facebook User",
                    "first_name": "Facebook",
                    "last_name": "User",
                }
                mock_client.return_value = mock_client_instance

                response = self.client.get(reverse("facebook_login") + "?code=fake-code", follow=True)
                self.assertEqual(response.status_code, 200)

        user = CustomUser.objects.get(email="fb@test.com")
        social_account = SocialAccount.objects.get(user=user, provider="facebook")
        self.assertEqual(social_account.uid, "fb-123")

    def test_apple_login_flow(self):
        """Login Apple segue mesmo fluxo."""
        apple_app, _ = SocialApp.objects.get_or_create(
            provider="apple",
            defaults={"name": "Apple Test", "client_id": "test-apple-id", "secret": "test-apple-secret"},
        )
        apple_app.sites.add(SiteSettings.objects.get(pk=1).pk)

        with mock.patch("allauth.socialaccount.providers.apple.views.AppleOAuth2Adapter.complete_login") as mock_complete:
            mock_user = mock.MagicMock()
            mock_user.email = "apple@test.com"
            mock_user.first_name = "Apple"
            mock_user.last_name = "User"
            mock_complete.return_value.get_user.return_value = mock_user

            with mock.patch("allauth.socialaccount.providers.oauth2.views.OAuth2Client") as mock_client:
                mock_client_instance = mock.MagicMock()
                mock_client_instance.get_access_token.return_value = "fake-apple-token"
                mock_client_instance.get_user_info.return_value = {
                    "sub": "apple-123",
                    "email": "apple@test.com",
                    "name": "Apple User",
                }
                mock_client.return_value = mock_client_instance

                response = self.client.get(reverse("apple_login") + "?code=fake-code", follow=True)
                self.assertEqual(response.status_code, 200)

        user = CustomUser.objects.get(email="apple@test.com")
        social_account = SocialAccount.objects.get(user=user, provider="apple")
        self.assertEqual(social_account.uid, "apple-123")


@override_settings(**SOCIAL_SETTINGS)
class TestSocialLoginRoleSelection(TestCase):
    """Login social com seleção de role (cliente/prestador/afiliado)."""

    def setUp(self):
        # Limpa SocialApps existentes para evitar MultipleObjectsReturned
        SocialApp.objects.all().delete()
        
        SiteSettings.objects.get(pk=1).provider_registration_enabled = True
        SiteSettings.objects.get(pk=1).save()

        self.google_app, _ = SocialApp.objects.get_or_create(
            provider="google",
            defaults={"name": "Google Test", "client_id": "test-google-id", "secret": "test-google-secret"},
        )
        self.google_app.sites.add(SiteSettings.objects.get(pk=1).pk)

    def test_social_signup_with_prestador_role(self):
        """Signup social permite escolher role prestador (se habilitado)."""
        with mock.patch("allauth.socialaccount.providers.oauth2.views.OAuth2Adapter.complete_login") as mock_complete:
            mock_user = mock.MagicMock()
            mock_user.email = "prestador-social@test.com"
            mock_user.first_name = "Prestador"
            mock_user.last_name = "Social"
            mock_complete.return_value.get_user.return_value = mock_user

            with mock.patch("allauth.socialaccount.providers.oauth2.views.OAuth2Client") as mock_client:
                mock_client_instance = mock.MagicMock()
                mock_client_instance.get_access_token.return_value = "fake-token"
                mock_client_instance.get_user_info.return_value = {
                    "sub": "google-prestador",
                    "email": "prestador-social@test.com",
                    "name": "Prestador Social",
                }
                mock_client.return_value = mock_client_instance

                session = self.client.session
                session["social_role"] = "prestador"
                session.save()

                response = self.client.get(reverse("google_login") + "?code=fake-code", follow=True)
                self.assertEqual(response.status_code, 200)

        user = CustomUser.objects.get(email="prestador-social@test.com")
        self.assertEqual(user.role, CustomUser.Role.PRESTADOR)

    def test_social_signup_with_affiliate_role(self):
        """Signup social permite escolher role afiliado (se habilitado)."""
        with mock.patch("allauth.socialaccount.providers.oauth2.views.OAuth2Adapter.complete_login") as mock_complete:
            mock_user = mock.MagicMock()
            mock_user.email = "afiliado-social@test.com"
            mock_user.first_name = "Afiliado"
            mock_user.last_name = "Social"
            mock_complete.return_value.get_user.return_value = mock_user

            with mock.patch("allauth.socialaccount.providers.oauth2.views.OAuth2Client") as mock_client:
                mock_client_instance = mock.MagicMock()
                mock_client_instance.get_access_token.return_value = "fake-token"
                mock_client_instance.get_user_info.return_value = {
                    "sub": "google-afiliado",
                    "email": "afiliado-social@test.com",
                    "name": "Afiliado Social",
                }
                mock_client.return_value = mock_client_instance

                session = self.client.session
                session["social_role"] = "afiliado"
                session.save()

                response = self.client.get(reverse("google_login") + "?code=fake-code", follow=True)
                self.assertEqual(response.status_code, 200)

        user = CustomUser.objects.get(email="afiliado-social@test.com")
        self.assertEqual(user.role, CustomUser.Role.AFILIADO)

    def test_social_signup_role_defaults_to_cliente(self):
        """Sem role na sessão, padrão é cliente."""
        with mock.patch("allauth.socialaccount.providers.oauth2.views.OAuth2Adapter.complete_login") as mock_complete:
            mock_user = mock.MagicMock()
            mock_user.email = "default-social@test.com"
            mock_user.first_name = "Default"
            mock_user.last_name = "Social"
            mock_complete.return_value.get_user.return_value = mock_user

            with mock.patch("allauth.socialaccount.providers.oauth2.views.OAuth2Client") as mock_client:
                mock_client_instance = mock.MagicMock()
                mock_client_instance.get_access_token.return_value = "fake-token"
                mock_client_instance.get_user_info.return_value = {
                    "sub": "google-default",
                    "email": "default-social@test.com",
                    "name": "Default Social",
                }
                mock_client.return_value = mock_client_instance

                response = self.client.get(reverse("google_login") + "?code=fake-code", follow=True)
                self.assertEqual(response.status_code, 200)

        user = CustomUser.objects.get(email="default-social@test.com")
        self.assertEqual(user.role, CustomUser.Role.CLIENTE)


@override_settings(**SOCIAL_SETTINGS)
class TestSocialLoginSectionToggle(TestCase):
    """Login social desativado por SiteSettings."""

    def test_social_login_buttons_hidden_when_disabled(self):
        from apps.core.models import SiteSettings

        settings = SiteSettings.objects.get(pk=1)
        settings.provider_registration_enabled = False
        settings.save()

        response = self.client.get(reverse("account_login"))
        self.assertEqual(response.status_code, 200)
        # Check that provider login buttons are hidden (look for "Continuar com" which is in the button text)
        self.assertNotContains(response, "Continuar com")
        # Also check that the provider section is not rendered
        self.assertNotContains(response, "provider_login_url")

    def test_social_signup_option_hidden_when_disabled(self):
        from apps.core.models import SiteSettings

        settings = SiteSettings.objects.get(pk=1)
        settings.provider_registration_enabled = False
        settings.save()

        response = self.client.get(reverse("account_signup"))
        self.assertEqual(response.status_code, 200)
        # Prestador should be hidden when provider_registration_enabled=False
        self.assertNotContains(response, "Prestador")
        # Afiliado is controlled by affiliates_enabled, not provider_registration_enabled
        # So it should still be visible (affiliates_enabled defaults to True)
        self.assertContains(response, "Afiliado")