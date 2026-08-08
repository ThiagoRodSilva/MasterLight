"""Testes de accounts (signals de perfil)."""
import pytest

from apps.accounts.models import CustomUser, PublicProfile
from apps.affiliate.models import AffiliateProfile
from conftest import UserFactory

pytestmark = pytest.mark.django_db


class TestSignals:
    def test_new_user_gets_affiliate_profile(self):
        user = UserFactory()
        assert AffiliateProfile.objects.filter(user=user).exists()

    def test_afiliado_gets_public_profile(self):
        user = UserFactory(role=CustomUser.Role.AFILIADO)
        assert PublicProfile.objects.filter(user=user).exists()

    def test_prestador_gets_public_profile(self):
        user = UserFactory(role=CustomUser.Role.PRESTADOR)
        assert PublicProfile.objects.filter(user=user).exists()

    def test_cliente_does_not_get_public_profile(self):
        user = UserFactory(role=CustomUser.Role.CLIENTE)
        assert not PublicProfile.objects.filter(user=user).exists()

    def test_role_change_to_afiliado_creates_public_profile(self):
        user = UserFactory(role=CustomUser.Role.CLIENTE)
        assert not PublicProfile.objects.filter(user=user).exists()
        user.role = CustomUser.Role.AFILIADO
        user.save()
        assert PublicProfile.objects.filter(user=user).exists()


class TestCustomUser:
    def test_is_prestador_admin(self):
        admin = UserFactory(is_superuser=True)
        assert admin.is_prestador

    def test_is_afiliado(self):
        user = UserFactory(role=CustomUser.Role.AFILIADO)
        assert user.is_afiliado
