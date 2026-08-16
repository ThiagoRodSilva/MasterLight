"""Separação de contas em accounts: acesso ao dashboard e sync role->is_staff."""

from django.test import TestCase

from apps.accounts.models import CustomUser
from apps.tests.helpers import make_user


class TestMeViewRequiresLogin(TestCase):
    def test_me_requires_login(self):
        response = self.client.get("/accounts/me/")
        assert response.status_code in (301, 302)
        assert "/social/login/" in response.url

    def test_me_accessible_when_authenticated(self):
        user = make_user()
        self.client.force_login(user)
        response = self.client.get("/accounts/me/")
        assert response.status_code == 200


class TestRoleStaffSync(TestCase):
    def test_role_admin_concede_is_staff(self):
        user = make_user(role=CustomUser.Role.CLIENTE)
        assert user.is_staff is False
        user.role = CustomUser.Role.ADMIN
        user.save()
        user.refresh_from_db()
        assert user.is_staff is True

    def test_rebaixar_admin_remove_is_staff(self):
        user = make_user(role=CustomUser.Role.ADMIN)
        assert user.is_staff is True
        user.role = CustomUser.Role.CLIENTE
        user.save()
        user.refresh_from_db()
        assert user.is_staff is False

    def test_superuser_mantem_staff_com_outra_role(self):
        user = make_user(role=CustomUser.Role.CLIENTE, is_superuser=True)
        user.save()
        user.refresh_from_db()
        assert user.is_staff is True

    def test_role_prestador_nao_concede_is_staff(self):
        user = make_user(role=CustomUser.Role.PRESTADOR)
        assert user.is_staff is False


class TestRoleProperties(TestCase):
    def test_admin_enxerga_como_todos_os_perfis(self):
        admin = make_user(role=CustomUser.Role.ADMIN)
        assert admin.is_cliente
        assert admin.is_prestador
        assert admin.is_afiliado
        assert admin.is_admin

    def test_superuser_enxerga_como_admin(self):
        superuser = make_user(is_superuser=True)
        assert superuser.is_cliente
        assert superuser.is_prestador
        assert superuser.is_afiliado
        assert superuser.is_admin

    def test_roles_exclusivas_nao_se_sobrepoem(self):
        cliente = make_user(role=CustomUser.Role.CLIENTE)
        prestador = make_user(role=CustomUser.Role.PRESTADOR)
        afiliado = make_user(role=CustomUser.Role.AFILIADO)
        assert cliente.is_cliente and not cliente.is_prestador and not cliente.is_afiliado
        assert prestador.is_prestador and not prestador.is_cliente and not prestador.is_afiliado
        assert afiliado.is_afiliado and not afiliado.is_cliente and not afiliado.is_prestador
