"""Integração ponta a ponta: Social Login (Google/Facebook/Apple via allauth).

Fluxo real do app (apps/accounts/adapters.py + SocialSignupCompleteView):
1. O callback OAuth completa e `pre_social_login` guarda o sociallogin na sessão
   (novo usuário) ou conecta a conta existente por email (login direto).
2. Usuário novo é redirecionado para o signup do allauth (`socialaccount_signup`);
   ao submeter, o usuário é criado (role=cliente) e logado.
3. O redirecionamento pós-signup aponta para a tela de completamento
   (`social_signup_complete`); ao submeter o form (role/CPF/telefone/endereço)
   o usuário recebe os dados, o Address é criado, a SocialAccount é vinculada
   definitivamente e o usuário permanece logado.
"""

from unittest import mock

from allauth.socialaccount.internal import statekit
from allauth.socialaccount.models import (
    EmailAddress,
    SocialAccount,
    SocialApp,
    SocialLogin,
    SocialToken,
)
from django.test import RequestFactory, TestCase, override_settings
from django.urls import resolve, reverse

from apps.accounts.models import CustomUser
from apps.checkout.models import Address
from apps.core.models import SiteSettings
from apps.tests.helpers import make_user

# Os apps (SocialApp) vêm do banco (criados nos testes). O allauth mescla
# o APP de settings com os do DB; por isso os dicionários APP não são definidos
# aqui — evita MultipleObjectsReturned no `get_app`.
SOCIAL_SETTINGS = {
    "ACCOUNT_EMAIL_VERIFICATION": "none",
    "SOCIALACCOUNT_LOGIN_ON_GET": True,
}

_ADAPTER_PATHS = {
    "google": "allauth.socialaccount.providers.google.views.GoogleOAuth2Adapter",
    "facebook": "allauth.socialaccount.providers.facebook.views.FacebookOAuth2Adapter",
    "apple": "allauth.socialaccount.providers.apple.views.AppleOAuth2Adapter",
}


def _build_social_login(provider_id, email, name, uid):
    """Monta um SocialLogin com usuário ainda não persistido (pk=None)."""
    first, _, last = name.partition(" ")
    user = CustomUser(
        username=uid,
        email=email,
        first_name=first,
        last_name=last,
    )
    account = SocialAccount(provider=provider_id, uid=uid, extra_data={"email": email})
    token = SocialToken(token="fake-token")
    token.account = account
    login = SocialLogin(user=user, account=account, token=token)
    login.email_addresses = [EmailAddress(email=email, verified=True, primary=True)]
    return login


def complete_provider_callback(client, provider_id, email, name, uid):
    """Dispara o callback OAuth do provider (state+code) e retorna a resposta.

    Mocks: `complete_login` retorna um SocialLogin pronto e o token exchange é
    simulado via `get_access_token_data` (e `parse_token` no caso da Apple).
    """
    request = RequestFactory().get("/")
    request.session = client.session
    state_id = statekit.stash_state(request, {"id": "test"})
    request.session.save()

    login = _build_social_login(provider_id, email, name, uid)
    adapter = _ADAPTER_PATHS[provider_id]
    patches = [
        mock.patch(f"{adapter}.complete_login", return_value=login),
        mock.patch(
            f"{adapter}.get_access_token_data",
            return_value={"access_token": "fake-token", "expires_in": 3600},
        ),
    ]
    if provider_id == "apple":
        patches.append(mock.patch(f"{adapter}.parse_token", return_value=login.token))

    for p in patches:
        p.start()
    try:
        if provider_id == "apple":
            # Apple usa `form_post`: POST em apple_callback redireciona para o
            # finish callback (que roda o fluxo OAuth2 padrão).
            client.post(
                reverse("apple_callback"),
                {"code": "fake-code", "state": state_id},
                follow=False,
            )
            resp = client.get(
                reverse("apple_finish_callback") + f"?code=fake-code&state={state_id}",
                follow=False,
            )
        else:
            resp = client.get(
                reverse(f"{provider_id}_callback") + f"?code=fake-code&state={state_id}",
                follow=False,
            )
        return resp
    finally:
        for p in patches:
            p.stop()


@override_settings(**SOCIAL_SETTINGS)
class TestSocialLoginFlow(TestCase):
    """Callback social: novo usuário -> signup allauth; usuário existente -> login."""

    def setUp(self):
        # Limpa SocialApps existentes para evitar MultipleObjectsReturned
        SocialApp.objects.all().delete()

        settings = SiteSettings.objects.get(pk=1)
        settings.provider_registration_enabled = True
        settings.save()

        self.google_app, _ = SocialApp.objects.get_or_create(
            provider="google",
            defaults={"name": "Google Test", "client_id": "test-google-id", "secret": "test-google-secret"},
        )
        self.google_app.sites.add(SiteSettings.objects.get(pk=1).pk)

    def test_google_new_user_goes_to_allauth_signup(self):
        """Novo usuário Google é redirecionado para o signup do allauth e nada é criado ainda."""
        response = complete_provider_callback(
            self.client, "google", "social@test.com", "Social User", "google-123"
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(resolve(response.url).url_name, "socialaccount_signup")
        self.assertFalse(CustomUser.objects.filter(email="social@test.com").exists())
        # Sessão guarda o signup pendente (allauth) e o sociallogin do app
        self.assertIn("socialaccount_sociallogin", self.client.session)
        self.assertIn("sociallogin", self.client.session)

    def test_google_existing_user_links_and_logs_in(self):
        """Login Google em email existente vincula SocialAccount e loga direto."""
        existing_user = make_user(email="social@test.com", role="cliente")

        response = complete_provider_callback(
            self.client, "google", "social@test.com", "Social User", "google-123"
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")

        user = CustomUser.objects.get(email="social@test.com")
        self.assertEqual(user.pk, existing_user.pk)
        account = SocialAccount.objects.get(user=user, provider="google")
        self.assertEqual(account.uid, "google-123")
        self.assertIn("_auth_user_id", self.client.session)

    def test_facebook_new_user_flow(self):
        """Login Facebook segue o mesmo fluxo de novo usuário (Google)."""
        fb_app, _ = SocialApp.objects.get_or_create(
            provider="facebook",
            defaults={"name": "Facebook Test", "client_id": "test-fb-id", "secret": "test-fb-secret"},
        )
        fb_app.sites.add(SiteSettings.objects.get(pk=1).pk)

        response = complete_provider_callback(
            self.client, "facebook", "fb@test.com", "Facebook User", "fb-123"
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(resolve(response.url).url_name, "socialaccount_signup")
        self.assertFalse(CustomUser.objects.filter(email="fb@test.com").exists())

    def test_apple_new_user_flow(self):
        """Login Apple (form_post) segue o mesmo fluxo de novo usuário."""
        apple_app, _ = SocialApp.objects.get_or_create(
            provider="apple",
            defaults={"name": "Apple Test", "client_id": "test-apple-id", "secret": "test-apple-secret"},
        )
        apple_app.sites.add(SiteSettings.objects.get(pk=1).pk)

        response = complete_provider_callback(
            self.client, "apple", "apple@test.com", "Apple User", "apple-123"
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(resolve(response.url).url_name, "socialaccount_signup")
        self.assertFalse(CustomUser.objects.filter(email="apple@test.com").exists())


@override_settings(**SOCIAL_SETTINGS)
class TestSocialSignupFlow(TestCase):
    """Callback + signup allauth + completamento obrigatório (SocialSignupCompleteView)."""

    def setUp(self):
        SocialApp.objects.all().delete()

        settings = SiteSettings.objects.get(pk=1)
        settings.provider_registration_enabled = True
        settings.save()

        self.google_app, _ = SocialApp.objects.get_or_create(
            provider="google",
            defaults={"name": "Google Test", "client_id": "test-google-id", "secret": "test-google-secret"},
        )
        self.google_app.sites.add(SiteSettings.objects.get(pk=1).pk)

    def _complete_signup(self, email, name, uid, role="cliente"):
        """Executa callback -> signup allauth -> completamento e retorna a resposta final."""
        response = complete_provider_callback(self.client, "google", email, name, uid)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(resolve(response.url).url_name, "socialaccount_signup")

        # Passo intermediário: form de signup do allauth. Ele herda os campos
        # de CustomSignupForm (role/CPF/telefone/endereço) e já cria o usuário
        # com esses dados + Address. A role final é decidida no completamento.
        response = self.client.post(
            reverse("socialaccount_signup"),
            {
                "email": email,
                "role": "cliente",
                "cpf": "123.456.789-09",
                "telefone": "11999999999",
                "bio": "",
                "street": "Rua Teste",
                "number": "123",
                "city": "São Paulo",
                "state": "SP",
                "zip_code": "01234567",
                "country": "Brasil",
            },
            follow=False,
        )
        self.assertEqual(response.status_code, 302)

        # Tela de completamento (GET) e submissão do form
        response = self.client.get(reverse("social_signup_complete"))
        self.assertEqual(response.status_code, 200)

        return self.client.post(
            reverse("social_signup_complete"),
            {
                "role": role,
                "cpf": "123.456.789-09",
                "telefone": "11999999999",
                "street": "Rua Teste",
                "number": "123",
                "city": "São Paulo",
                "state": "SP",
                "zip_code": "01234567",
                "country": "Brasil",
            },
            follow=True,
        )

    def test_social_signup_creates_user_and_logs_in(self):
        """Completamento cria usuário, Address, SocialAccount e loga."""
        response = self._complete_signup("social@test.com", "Social User", "google-123")
        self.assertEqual(response.status_code, 200)

        user = CustomUser.objects.get(email="social@test.com")
        self.assertEqual(user.role, CustomUser.Role.CLIENTE)
        self.assertEqual(user.cpf, "12345678909")
        self.assertEqual(user.telefone, "11999999999")
        self.assertTrue(Address.objects.filter(user=user, is_active=True).exists())
        self.assertTrue(SocialAccount.objects.filter(user=user, provider="google").exists())
        self.assertIn("_auth_user_id", self.client.session)

    def test_social_signup_role_defaults_to_cliente(self):
        """Sem role explícita, o padrão é cliente."""
        self._complete_signup("default-social@test.com", "Default Social", "google-default")
        user = CustomUser.objects.get(email="default-social@test.com")
        self.assertEqual(user.role, CustomUser.Role.CLIENTE)

    def test_social_signup_with_prestador_role(self):
        """Completamento permite escolher role prestador (se habilitado)."""
        self._complete_signup(
            "prestador-social@test.com", "Prestador Social", "google-prestador", role="prestador"
        )
        user = CustomUser.objects.get(email="prestador-social@test.com")
        self.assertEqual(user.role, CustomUser.Role.PRESTADOR)

    def test_social_signup_with_affiliate_role(self):
        """Completamento permite escolher role afiliado (se habilitado)."""
        self._complete_signup(
            "afiliado-social@test.com", "Afiliado Social", "google-afiliado", role="afiliado"
        )
        user = CustomUser.objects.get(email="afiliado-social@test.com")
        self.assertEqual(user.role, CustomUser.Role.AFILIADO)


@override_settings(**SOCIAL_SETTINGS)
class TestSocialLoginSectionToggle(TestCase):
    """Login social desativado por SiteSettings."""

    def test_social_login_buttons_hidden_when_disabled(self):
        settings = SiteSettings.objects.get(pk=1)
        settings.provider_registration_enabled = False
        settings.save()

        response = self.client.get(reverse("account_login"))
        self.assertEqual(response.status_code, 200)
        # O bloco de providers não é renderizado quando desabilitado
        self.assertNotContains(response, "provider_login_url")

    def test_social_signup_option_hidden_when_disabled(self):
        settings = SiteSettings.objects.get(pk=1)
        settings.provider_registration_enabled = False
        settings.save()

        response = self.client.get(reverse("account_signup"))
        self.assertEqual(response.status_code, 200)
        # Prestador deve sumir quando provider_registration_enabled=False
        self.assertNotContains(response, "Prestador")
        # Afiliado é controlado por affiliates_enabled (default True) -> permanece
        self.assertContains(response, "Afiliado")
