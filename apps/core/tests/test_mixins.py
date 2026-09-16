"""Testes dos role-mixins: separação estrita de contas.

Matriz esperada:
    cliente   -> só áreas de cliente
    prestador -> só áreas de prestador
    afiliado  -> só áreas de afiliado
    admin     -> todas as áreas
    superuser -> todas as áreas
    anônimo   -> redireciona para login
"""

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.core.models import SiteSettings
from apps.tests.helpers import make_user


class TestRoleMixinsAnonymous(TestCase):
    def test_provider_mixin_redirects_anonymous(self):
        response = self.client.get(reverse("services-create"))
        assert response.status_code in (302, 403)
        assert self.client.session.get("_auth_user_id") is None

    def test_affiliate_mixin_redirects_anonymous(self):
        response = self.client.get(reverse("affiliate-dashboard"))
        assert response.status_code in (302, 403)

    def test_cliente_mixin_redirects_anonymous(self):
        response = self.client.get(reverse("checkout-address"))
        assert response.status_code in (302, 403)
        assert self.client.session.get("_auth_user_id") is None


class TestRoleSeparation(TestCase):
    def setUp(self):
        super().setUp()
        settings = SiteSettings.load()
        settings.services_enabled = True
        settings.affiliates_enabled = True
        settings.save(
            update_fields=[
                "services_enabled",
                "affiliates_enabled",
            ]
        )

    def _access(self, user, url_name):
        if user is None:
            self.client.logout()
        else:
            self.client.force_login(user)
        return self.client.get(reverse(url_name))

    def _assert_allowed(self, user):
        for url_name in ("services-create", "affiliate-dashboard", "checkout-address"):
            with self.subTest(user=user.role, url_name=url_name):
                assert self._access(user, url_name).status_code in (200, 302)

    def _assert_blocked(self, user):
        for url_name in ("services-create", "affiliate-dashboard", "checkout-address"):
            with self.subTest(user=user.role, url_name=url_name):
                assert self._access(user, url_name).status_code == 403

    def test_cliente_só_na_área_de_cliente(self):
        cliente = make_user(
            role=CustomUser.Role.CLIENTE,
            cpf="12345678901",
            telefone="11999999999",
            address={
                "street": "Rua Teste",
                "number": "123",
                "city": "São Paulo",
                "state": "SP",
                "zip_code": "01234567",
            },
        )
        assert self._access(cliente, "checkout-address").status_code in (200, 302)
        assert self._access(cliente, "services-create").status_code == 403
        assert self._access(cliente, "affiliate-dashboard").status_code == 403

    def test_prestador_só_na_área_de_prestador(self):
        prestador = make_user(
            role=CustomUser.Role.PRESTADOR,
            cpf="12345678902",
            telefone="11999999998",
            address={
                "street": "Rua Teste",
                "number": "123",
                "city": "São Paulo",
                "state": "SP",
                "zip_code": "01234567",
            },
        )
        assert self._access(prestador, "services-create").status_code in (200, 302)
        assert self._access(prestador, "checkout-address").status_code == 403
        assert self._access(prestador, "affiliate-dashboard").status_code == 403

    def test_afiliado_só_na_área_de_afiliado(self):
        afiliado = make_user(
            role=CustomUser.Role.AFILIADO,
            cpf="12345678903",
            telefone="11999999997",
            address={
                "street": "Rua Teste",
                "number": "123",
                "city": "São Paulo",
                "state": "SP",
                "zip_code": "01234567",
            },
        )
        assert self._access(afiliado, "affiliate-dashboard").status_code in (200, 302)
        assert self._access(afiliado, "checkout-address").status_code == 403
        assert self._access(afiliado, "services-create").status_code == 403

    def test_admin_acessa_todas_as_áreas(self):
        admin = make_user(role=CustomUser.Role.ADMIN, is_superuser=True)
        self._assert_allowed(admin)

    def test_superuser_acessa_todas_as_áreas(self):
        superuser = make_user(is_superuser=True)
        self._assert_allowed(superuser)


class TestOwnerRequiredMixin(TestCase):
    def test_admin_bypassa_a_posse(self):
        from apps.services.models import Service, ServiceCategory

        category = ServiceCategory.objects.create(name="Elétrica", slug="eletrica")
        owner = make_user(
            role=CustomUser.Role.PRESTADOR,
            cpf="12345678904",
            telefone="11999999996",
            address={
                "street": "Rua Teste",
                "number": "123",
                "city": "São Paulo",
                "state": "SP",
                "zip_code": "01234567",
            },
        )
        service = Service.objects.create(
            name="Serviço do outro",
            slug="servico-do-outro",
            base_price=10,
            category=category,
            created_by=owner,
        )
        admin = make_user(role=CustomUser.Role.ADMIN, is_superuser=True)
        self.client.force_login(admin)
        response = self.client.get(reverse("services-update", kwargs={"slug": service.slug}))
        assert response.status_code == 200

    def test_nao_dono_sem_role_admin_nao_acessa(self):
        from apps.services.models import Service, ServiceCategory

        category = ServiceCategory.objects.create(name="Elétrica", slug="eletrica-2")
        owner = make_user(
            role=CustomUser.Role.PRESTADOR,
            cpf="12345678905",
            telefone="11999999995",
            address={
                "street": "Rua Teste",
                "number": "123",
                "city": "São Paulo",
                "state": "SP",
                "zip_code": "01234567",
            },
        )
        service = Service.objects.create(
            name="Serviço privado",
            slug="servico-privado",
            base_price=10,
            category=category,
            created_by=owner,
        )
        outro = make_user(
            role=CustomUser.Role.PRESTADOR,
            cpf="12345678906",
            telefone="11999999994",
            address={
                "street": "Rua Teste",
                "number": "456",
                "city": "São Paulo",
                "state": "SP",
                "zip_code": "01234567",
            },
        )
        self.client.force_login(outro)
        response = self.client.get(reverse("services-update", kwargs={"slug": service.slug}))
        assert response.status_code in (403, 404)
