"""Testes do fluxo de aprovação de prestadores."""

import pytest
from django.contrib.auth import get_user_model

from apps.accounts.forms import CustomSignupForm
from apps.accounts.models import ProviderApplication, PublicProfile
from apps.accounts.services import approve_provider_application, reject_provider
from conftest import UserFactory

pytestmark = pytest.mark.django_db

CustomUser = get_user_model()


class TestCustomSignupFormProvider:
    @staticmethod
    def _signup(form, email, username, **user_kwargs):
        user = CustomUser(email=email, username=username, **user_kwargs)
        user.save()
        form.signup(None, user)
        user.refresh_from_db()
        return user

    def test_signup_as_provider_keeps_cliente_and_creates_application(self):
        form = CustomSignupForm(
            data={
                "role": CustomUser.Role.PRESTADOR,
                "cpf": "111.444.777-35",
                "telefone": "(11) 99999-0000",
                "bio": "Eletricista residencial",
            }
        )
        assert form.is_valid(), form.errors
        user = self._signup(form, "elet@example.com", "elet")
        application = user.provider_application
        assert user.role == CustomUser.Role.CLIENTE
        assert application.status == ProviderApplication.Status.PENDING
        assert application.bio == "Eletricista residencial"
        assert user.cpf == "11144477735"

    def test_signup_provider_requires_cpf_and_telefone(self):
        form = CustomSignupForm(
            data={
                "role": CustomUser.Role.PRESTADOR,
                "bio": "Eletricista",
            }
        )
        assert not form.is_valid()
        assert "cpf" in form.errors
        assert "telefone" in form.errors

    def test_signup_cliente_does_not_create_application(self):
        form = CustomSignupForm(data={"role": CustomUser.Role.CLIENTE})
        assert form.is_valid(), form.errors
        user = self._signup(form, "cli@example.com", "cli")
        assert user.role == CustomUser.Role.CLIENTE
        assert not hasattr(user, "provider_application")

    def test_option_hidden_when_provider_registration_disabled(self):
        from apps.core.models import SiteSettings

        settings = SiteSettings.load()
        settings.provider_registration_enabled = False
        settings.save()
        form = CustomSignupForm()
        choices = [value for value, _ in form.fields["role"].choices]
        assert CustomUser.Role.PRESTADOR not in choices
        assert CustomUser.Role.AFILIADO in choices


class TestProviderApprovalServices:
    def test_approve_promotes_user_and_copies_bio_to_public_profile(self):
        candidate = UserFactory(role=CustomUser.Role.CLIENTE)
        application = ProviderApplication.objects.create(
            user=candidate, status=ProviderApplication.Status.PENDING, bio="Eletricista predial"
        )
        admin = UserFactory(is_superuser=True)

        approve_provider_application(application, admin)

        candidate.refresh_from_db()
        application.refresh_from_db()
        assert candidate.role == CustomUser.Role.PRESTADOR
        assert candidate.is_prestador
        assert application.status == ProviderApplication.Status.APPROVED
        assert application.reviewed_by == admin
        assert application.reviewed_at is not None
        profile = PublicProfile.objects.get(user=candidate)
        assert profile.bio == "Eletricista predial"

    def test_approve_non_pending_raises(self):
        application = ProviderApplication.objects.create(user=UserFactory())
        application.status = ProviderApplication.Status.REJECTED
        application.save()
        with pytest.raises(ValueError):
            approve_provider_application(application, UserFactory(is_superuser=True))

    def test_reject_keeps_cliente(self):
        candidate = UserFactory(role=CustomUser.Role.CLIENTE)
        application = ProviderApplication.objects.create(user=candidate)
        admin = UserFactory(is_superuser=True)

        reject_provider(application, admin)

        candidate.refresh_from_db()
        application.refresh_from_db()
        assert candidate.role == CustomUser.Role.CLIENTE
        assert not candidate.is_prestador
        assert application.status == ProviderApplication.Status.REJECTED
        assert not PublicProfile.objects.filter(user=candidate).exists()


class TestPendingDashboardNotice:
    def test_me_shows_notice_when_pending(self, db):
        candidate = UserFactory(role=CustomUser.Role.CLIENTE)
        ProviderApplication.objects.create(user=candidate)
        from django.test import Client

        client = Client()
        client.force_login(candidate)
        response = client.get("/accounts/me/")
        assert response.status_code == 200
        assert "aguardando aprovação" in response.content.decode()
