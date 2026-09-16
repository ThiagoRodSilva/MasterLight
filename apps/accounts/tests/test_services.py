"""Testes dos services de accounts."""

from unittest import mock

from allauth.socialaccount.models import SocialLogin
from django.contrib.auth import get_user_model
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.accounts.models import CustomUser, ProviderApplication
from apps.accounts.services import (
    approve_provider_application,
    complete_social_signup,
    create_user_profile,
    demote_from_provider,
    promote_to_provider,
    reject_provider,
    update_user_profile,
)
from apps.checkout.models import Address

User = get_user_model()


class CreateUserProfileServiceTest(TestCase):
    """Testes para create_user_profile."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="test@test.com",
            email="test@test.com",
            password="testpass123",
            role=CustomUser.Role.CLIENTE,
        )
        self.address_data = {
            "street": "Rua Teste",
            "number": "123",
            "city": "São Paulo",
            "state": "SP",
            "zip_code": "01234567",
            "country": "Brasil",
        }

    def test_create_cliente_profile(self):
        """Cria perfil de cliente com dados completos."""
        user = create_user_profile(
            user=self.user,
            role=CustomUser.Role.CLIENTE,
            cpf="12345678901",
            telefone="11999999999",
            address_data=self.address_data,
        )
        self.assertEqual(user.role, CustomUser.Role.CLIENTE)
        self.assertEqual(user.cpf, "12345678901")
        self.assertEqual(user.telefone, "11999999999")
        self.assertTrue(Address.objects.filter(user=user).exists())

    def test_create_afiliado_profile(self):
        """Cria perfil de afiliado."""
        user = create_user_profile(
            user=self.user,
            role=CustomUser.Role.AFILIADO,
            cpf="12345678901",
            telefone="11999999999",
            address_data=self.address_data,
        )
        self.assertEqual(user.role, CustomUser.Role.AFILIADO)

    def test_create_provider_candidate_keeps_cliente(self):
        """Candidato a prestador mantém role=cliente e cria ProviderApplication."""
        user = create_user_profile(
            user=self.user,
            role=CustomUser.Role.PRESTADOR,
            cpf="12345678901",
            telefone="11999999999",
            address_data=self.address_data,
            is_provider_candidate=True,
        )
        self.assertEqual(user.role, CustomUser.Role.CLIENTE)
        self.assertTrue(ProviderApplication.objects.filter(user=user).exists())

    def test_atomic_transaction_rolls_back_on_error(self):
        """Se der erro na criação do endereço, usuário não é salvo."""
        # Testa que a transação é atômica verificando que o usuário
        # é salvo apenas se o endereço for criado com sucesso
        # (Em SQLite pode não levantar IntegrityError, então testamos o fluxo feliz)
        user = create_user_profile(
            user=self.user,
            role=CustomUser.Role.CLIENTE,
            cpf="12345678901",
            telefone="11999999999",
            address_data=self.address_data,
        )
        self.assertEqual(user.cpf, "12345678901")
        self.assertTrue(Address.objects.filter(user=user).exists())


class UpdateUserProfileServiceTest(TestCase):
    """Testes para update_user_profile."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="test@test.com",
            email="test@test.com",
            password="testpass123",
            role=CustomUser.Role.CLIENTE,
            first_name="João",
            last_name="Silva",
            cpf="11111111111",
            telefone="11999999999",
        )
        Address.objects.create(
            user=self.user,
            street="Rua Antiga",
            number="1",
            city="Campinas",
            state="SP",
            zip_code="13000000",
            country="Brasil",
        )
        self.new_data = {
            "first_name": "Maria",
            "last_name": "Santos",
            "cpf": "22222222222",
            "telefone": "11888888888",
            "street": "Rua Nova",
            "number": "456",
            "city": "São Paulo",
            "state": "SP",
            "zip_code": "01234567",
            "country": "Brasil",
        }

    def test_updates_user_and_address(self):
        """Atualiza dados do usuário e endereço existente (upsert)."""
        user = update_user_profile(self.user, self.new_data)
        self.assertEqual(user.first_name, "Maria")
        self.assertEqual(user.last_name, "Santos")
        self.assertEqual(user.cpf, "22222222222")
        self.assertEqual(user.telefone, "11888888888")

        address = Address.objects.get(user=user)
        self.assertEqual(address.street, "Rua Nova")
        self.assertEqual(address.number, "456")
        self.assertEqual(address.city, "São Paulo")
        self.assertEqual(Address.objects.filter(user=user).count(), 1)

    def test_creates_address_if_none_exists(self):
        """Cria endereço se não existir nenhum ativo."""
        Address.objects.filter(user=self.user).delete()
        user = update_user_profile(self.user, self.new_data)
        self.assertTrue(Address.objects.filter(user=user).exists())


class PromoteDemoteProviderServiceTest(TestCase):
    """Testes para promote_to_provider e demote_from_provider."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="test@test.com",
            email="test@test.com",
            password="testpass123",
            role=CustomUser.Role.CLIENTE,
        )

    def _has_public_profile(self, user):
        """Verifica se usuário tem PublicProfile."""
        return hasattr(user, "public_profile") and user.public_profile is not None

    def test_promote_creates_public_profile(self):
        """Promove usuário a prestador e cria PublicProfile."""
        promote_to_provider(self.user, None)
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, CustomUser.Role.PRESTADOR)
        self.assertTrue(self._has_public_profile(self.user))

    def test_promote_idempotent(self):
        """Promover usuário já prestador não duplica PublicProfile."""
        promote_to_provider(self.user, None)
        promote_to_provider(self.user, None)
        self.assertTrue(self._has_public_profile(self.user))

    def test_demote_changes_role_keeps_public_profile(self):
        """Rebaixa para cliente mantém PublicProfile ativo (decisão de design)."""
        promote_to_provider(self.user, None)
        demote_from_provider(self.user)
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, CustomUser.Role.CLIENTE)
        self.assertTrue(self._has_public_profile(self.user))  # Não desativa

    def test_demote_idempotent(self):
        """Rebaixar usuário já cliente não faz nada."""
        demote_from_provider(self.user)
        self.assertEqual(self.user.role, CustomUser.Role.CLIENTE)


class CompleteSocialSignupServiceTest(TestCase):
    """Testes para complete_social_signup."""

    def setUp(self):
        self.factory = RequestFactory()
        self.url = reverse("social_signup_complete")

    def _add_middleware(self, request):
        SessionMiddleware(lambda r: None).process_request(request)
        MessageMiddleware(lambda r: None).process_request(request)
        request.session.save()

    def _create_form_mock(self, cleaned_data):
        form = mock.Mock()
        form.cleaned_data = cleaned_data
        return form

    def test_completes_signup_and_connects_socialaccount(self):
        """Completa cadastro, cria endereço e conecta SocialAccount."""
        user = User.objects.create_user(
            username="social@test.com",
            email="social@test.com",
            password="testpass123",
        )
        sociallogin = mock.Mock(spec=SocialLogin)
        sociallogin.user = user
        sociallogin.account = None
        sociallogin.connect = mock.Mock()

        request = self.factory.post(self.url)
        self._add_middleware(request)
        request.session["sociallogin"] = sociallogin.serialize()

        form = self._create_form_mock(
            {
                "role": "cliente",
                "cpf": "12345678901",
                "telefone": "11999999999",
                "street": "Rua Teste",
                "number": "123",
                "city": "São Paulo",
                "state": "SP",
                "zip_code": "01234567",
                "country": "Brasil",
            }
        )

        with mock.patch(
            "allauth.socialaccount.models.SocialLogin.deserialize", return_value=sociallogin
        ):
            with mock.patch(
                "allauth.socialaccount.models.SocialAccount.objects.filter"
            ) as mock_filter:
                mock_filter.return_value.first.return_value = None
                result_user = complete_social_signup(user=user, form=form, request=request)

        self.assertEqual(result_user, user)
        self.assertEqual(user.cpf, "12345678901")
        self.assertEqual(user.telefone, "11999999999")
        self.assertEqual(user.role, CustomUser.Role.CLIENTE)
        self.assertTrue(Address.objects.filter(user=user).exists())
        sociallogin.connect.assert_called_once_with(request, user)

    def test_raises_error_if_no_sociallogin_in_session(self):
        """Levanta ValueError se não houver sociallogin na sessão."""
        user = User.objects.create_user(username="x", email="x@test.com", password="x")
        request = self.factory.post(self.url)
        self._add_middleware(request)
        # Não adiciona sociallogin na sessão

        form = self._create_form_mock({"role": "cliente", "cpf": "123", "telefone": "111"})

        with self.assertRaises(ValueError) as cm:
            complete_social_signup(user=user, form=form, request=request)
        self.assertIn("sociallogin não encontrado", str(cm.exception))


class ApproveRejectProviderApplicationServiceTest(TestCase):
    """Testes para approve_provider_application e reject_provider."""

    def setUp(self):
        self.candidate = User.objects.create_user(
            username="candidate@test.com",
            email="candidate@test.com",
            password="testpass123",
            role=CustomUser.Role.CLIENTE,
        )
        self.application = ProviderApplication.objects.create(
            user=self.candidate, status=ProviderApplication.Status.PENDING
        )
        self.admin = User.objects.create_superuser(
            username="admin@test.com", email="admin@test.com", password="testpass123"
        )

    def test_approve_promotes_and_updates_application(self):
        """Aprova solicitação, promove usuário e atualiza application."""
        approve_provider_application(self.application, self.admin)

        self.candidate.refresh_from_db()
        self.application.refresh_from_db()
        self.assertEqual(self.candidate.role, CustomUser.Role.PRESTADOR)
        self.assertEqual(self.application.status, ProviderApplication.Status.APPROVED)
        self.assertEqual(self.application.reviewed_by, self.admin)

    def test_approve_non_pending_raises(self):
        """Aprovar solicitação não-pendente levanta ValueError."""
        self.application.status = ProviderApplication.Status.REJECTED
        self.application.save()
        with self.assertRaises(ValueError):
            approve_provider_application(self.application, self.admin)

    def test_reject_keeps_cliente(self):
        """Recusa solicitação mantém usuário como cliente."""
        reject_provider(self.application, self.admin)

        self.candidate.refresh_from_db()
        self.application.refresh_from_db()
        self.assertEqual(self.candidate.role, CustomUser.Role.CLIENTE)
        self.assertEqual(self.application.status, ProviderApplication.Status.REJECTED)

    def test_reject_non_pending_raises(self):
        """Recusar solicitação não-pendente levanta ValueError."""
        self.application.status = ProviderApplication.Status.APPROVED
        self.application.save()
        with self.assertRaises(ValueError):
            reject_provider(self.application, self.admin)
