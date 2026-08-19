"""Testes das views de serviços (catálogo, self-service e solicitações)."""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.services.models import Service, ServiceCategory, ServiceRequest
from apps.tests.helpers import make_user


class TestServiceSelfService(TestCase):
    def setUp(self):
        super().setUp()
        self.provider = make_user(role=CustomUser.Role.PRESTADOR)
        self.cliente = make_user(role=CustomUser.Role.CLIENTE)
        self.category = ServiceCategory.objects.create(name="Elétrica", slug="eletrica")

    def test_provider_can_create_service_and_is_provider(self):
        self.client.force_login(self.provider)
        create_page = self.client.get(reverse("services-create"))
        assert "slug" not in create_page.context["form"].fields
        response = self.client.post(
            reverse("services-create"),
            {
                "name": "Instalação de lâmpada",
                "category": self.category.pk,
                "description": "teste",
                "base_price": "50.00",
            },
        )
        assert response.status_code == 302
        service = Service.objects.get(name="Instalação de lâmpada")
        assert service.slug
        assert service.created_by == self.provider
        assert self.provider in service.providers.all()

    def test_cliente_cannot_create_service(self):
        self.client.force_login(self.cliente)
        response = self.client.get(reverse("services-create"))
        assert response.status_code in (302, 403)

    def test_owner_can_edit_service(self):
        service = Service.objects.create(
            name="Serviço X",
            slug="servico-x",
            base_price=10,
            category=self.category,
            created_by=self.provider,
        )
        self.client.force_login(self.provider)
        response = self.client.post(
            reverse("services-update", kwargs={"slug": service.slug}),
            {
                "name": "Serviço X atualizado",
                "category": self.category.pk,
                "description": "",
                "base_price": "20.00",
                "is_active": "on",
            },
        )
        assert response.status_code == 302
        service.refresh_from_db()
        assert service.name == "Serviço X atualizado"
        assert service.slug == "servico-x"

    def test_non_owner_cannot_edit_service(self):
        owner = make_user(role=CustomUser.Role.PRESTADOR)
        service = Service.objects.create(
            name="Serviço Y",
            slug="servico-y",
            base_price=10,
            category=self.category,
            created_by=owner,
        )
        self.client.force_login(self.provider)
        response = self.client.get(reverse("services-update", kwargs={"slug": service.slug}))
        assert response.status_code in (302, 403, 404)

    def test_owner_can_soft_delete_service(self):
        service = Service.objects.create(
            name="Serviço Remover",
            slug="servico-remover",
            base_price=10,
            category=self.category,
            created_by=self.provider,
        )
        self.client.force_login(self.provider)
        response = self.client.post(reverse("services-delete", kwargs={"pk": service.pk}))
        assert response.status_code == 302
        service.refresh_from_db()
        assert service.is_active is False

    def test_my_services_lists_own_only(self):
        mine = Service.objects.create(
            name="Meu Serviço",
            slug="meu-servico",
            base_price=10,
            category=self.category,
            created_by=self.provider,
        )
        other = make_user(role=CustomUser.Role.PRESTADOR)
        Service.objects.create(
            name="De Outro",
            slug="de-outro",
            base_price=10,
            category=self.category,
            created_by=other,
        )
        self.client.force_login(self.provider)
        response = self.client.get(reverse("services-my"))
        assert response.status_code == 200
        assert mine.name in response.content.decode()
        assert "De Outro" not in response.content.decode()


class TestServiceRequestFlow(TestCase):
    def setUp(self):
        super().setUp()
        self.provider = make_user(role=CustomUser.Role.PRESTADOR)
        self.category = ServiceCategory.objects.create(name="Elétrica", slug="eletrica")

    def test_cliente_requests_service_with_provider(self):
        service = Service.objects.create(
            name="Serviço Z",
            slug="servico-z",
            base_price=10,
            category=self.category,
            created_by=self.provider,
        )
        service.providers.add(self.provider)
        cliente = make_user(role=CustomUser.Role.CLIENTE)
        self.client.force_login(cliente)
        response = self.client.post(
            reverse("services-request", kwargs={"slug": service.slug}),
            {"prestador": self.provider.pk, "address": "Rua A, 100", "notes": ""},
        )
        assert response.status_code == 302
        sr = ServiceRequest.objects.get(service=service)
        assert sr.cliente == cliente
        assert sr.prestador == self.provider

    def test_provider_sees_request_and_quotes(self):
        service = Service.objects.create(
            name="Serviço Q",
            slug="servico-q",
            base_price=10,
            category=self.category,
            created_by=self.provider,
        )
        cliente = make_user(role=CustomUser.Role.CLIENTE)
        sr = ServiceRequest.objects.create(cliente=cliente, service=service, prestador=self.provider)
        self.client.force_login(self.provider)
        response = self.client.get(reverse("services-provider-requests"))
        assert response.status_code == 200
        assert service.name in response.content.decode()

        response = self.client.post(
            reverse("services-request-quote", kwargs={"pk": sr.pk}),
            {"final_price": "99.90"},
        )
        assert response.status_code == 302
        sr.refresh_from_db()
        assert sr.status == ServiceRequest.Status.QUOTED
        assert sr.final_price == Decimal("99.90")

    def test_provider_member_without_creating_sees_request(self):
        owner = make_user(role=CustomUser.Role.PRESTADOR)
        service = Service.objects.create(
            name="Serviço Membro",
            slug="servico-membro",
            base_price=10,
            category=self.category,
            created_by=owner,
        )
        service.providers.add(owner, self.provider)
        cliente = make_user(role=CustomUser.Role.CLIENTE)
        ServiceRequest.objects.create(cliente=cliente, service=service, prestador=self.provider)
        self.client.force_login(self.provider)
        response = self.client.get(reverse("services-provider-requests"))
        assert response.status_code == 200
        assert service.name in response.content.decode()

    def test_cliente_can_cancel_request(self):
        service = Service.objects.create(
            name="Serviço C",
            slug="servico-c",
            base_price=10,
            category=self.category,
            created_by=self.provider,
        )
        cliente = make_user(role=CustomUser.Role.CLIENTE)
        sr = ServiceRequest.objects.create(cliente=cliente, service=service)
        self.client.force_login(cliente)
        response = self.client.post(reverse("services-request-cancel", kwargs={"pk": sr.pk}))
        assert response.status_code == 302
        sr.refresh_from_db()
        assert sr.status == ServiceRequest.Status.CANCELED

    def _quoted_request(self, cliente, provider, price="99.90"):
        service = Service.objects.create(
            name="Serviço Aprovar",
            slug="servico-aprovar",
            base_price=10,
            category=self.category,
            created_by=provider,
        )
        service.providers.add(provider)
        return ServiceRequest.objects.create(
            cliente=cliente,
            service=service,
            prestador=provider,
            status=ServiceRequest.Status.QUOTED,
            final_price=price,
        )

    def test_approve_charge_error_cancels_order(self):
        from unittest import mock

        from apps.checkout.models import Order

        provider = make_user(role=CustomUser.Role.PRESTADOR)
        cliente = make_user(role=CustomUser.Role.CLIENTE)
        sr = self._quoted_request(cliente, provider)
        self.client.force_login(cliente)
        with mock.patch(
            "apps.payments.services.charge.charge_order", side_effect=ValueError("gateway fora")
        ):
            response = self.client.post(reverse("services-request-approve", kwargs={"pk": sr.pk}))
        assert response.status_code == 302
        order = Order.objects.get(user=cliente)
        assert order.status == Order.Status.CANCELED

    def test_approve_charge_not_ok_cancels_order(self):
        from unittest import mock

        from apps.checkout.models import Order
        from apps.payments.services import ChargeResult

        provider = make_user(role=CustomUser.Role.PRESTADOR)
        cliente = make_user(role=CustomUser.Role.CLIENTE)
        sr = self._quoted_request(cliente, provider)
        self.client.force_login(cliente)
        fake = ChargeResult(ok=False, redirect_url="", message="falha ao gerar")
        with mock.patch("apps.payments.services.charge.charge_order", return_value=fake):
            response = self.client.post(reverse("services-request-approve", kwargs={"pk": sr.pk}))
        assert response.status_code == 302
        order = Order.objects.get(user=cliente)
        assert order.status == Order.Status.CANCELED


class TestCatalogo(TestCase):
    def setUp(self):
        super().setUp()
        self.category = ServiceCategory.objects.create(name="Elétrica", slug="eletrica")

    def test_list_public(self):
        Service.objects.create(
            name="Serviço Público",
            slug="servico-publico",
            base_price=5,
            category=self.category,
        )
        response = self.client.get(reverse("services-list"))
        assert response.status_code == 200
        assert b"Servi" in response.content

    def test_detail_public(self):
        service = Service.objects.create(
            name="Serviço Detalhe",
            slug="servico-detalhe",
            base_price=5,
            category=self.category,
        )
        response = self.client.get(reverse("services-detail", kwargs={"slug": service.slug}))
        assert response.status_code == 200

    def test_list_uses_select_related_and_prefetch(self):
        """ServiceListView deve usar select_related para category e prefetch para providers."""
        Service.objects.create(
            name="Serviço A", slug="servico-a", base_price=5, category=self.category
        )
        Service.objects.create(
            name="Serviço B", slug="servico-b", base_price=10, category=self.category
        )
        # Framework: session + user + socialaccount + sitesettings = 4
        # View: services (1) + categories (1) = 2
        # Total: 6
        with self.assertNumQueries(6):
            response = self.client.get(reverse("services-list"))
        assert response.status_code == 200

    def test_detail_uses_select_related_and_prefetch(self):
        """ServiceDetailView deve usar select_related para category/created_by e prefetch para providers."""
        service = Service.objects.create(
            name="Serviço Detalhe",
            slug="servico-detalhe",
            base_price=5,
            category=self.category,
        )
        # Framework: session + user + socialaccount + sitesettings = 4
        # View: service (1 query, includes category, created_by, providers via prefetch)
        # Total: 4
        with self.assertNumQueries(4):
            response = self.client.get(reverse("services-detail", kwargs={"slug": service.slug}))
        assert response.status_code == 200


class TestServiceRoleSeparation(TestCase):
    def setUp(self):
        super().setUp()
        self.category = ServiceCategory.objects.create(name="Elétrica", slug="eletrica-role")
        self.provider = make_user(role=CustomUser.Role.PRESTADOR)
        self.service = Service.objects.create(
            name="Serviço X",
            slug="servico-x-role",
            base_price=10,
            category=self.category,
            created_by=self.provider,
        )

    def test_my_requests_restrito_a_cliente(self):
        for role in (CustomUser.Role.PRESTADOR, CustomUser.Role.AFILIADO):
            with self.subTest(role=role):
                user = make_user(role=role)
                self.client.force_login(user)
                response = self.client.get(reverse("services-my-requests"))
                assert response.status_code == 403

    def test_cliente_acessa_minhas_solicitacoes(self):
        cliente = make_user(role=CustomUser.Role.CLIENTE)
        self.client.force_login(cliente)
        response = self.client.get(reverse("services-my-requests"))
        assert response.status_code == 200

    def test_editar_servico_restrito_a_prestador(self):
        cliente = make_user(role=CustomUser.Role.CLIENTE)
        self.client.force_login(cliente)
        response = self.client.get(reverse("services-update", kwargs={"slug": self.service.slug}))
        assert response.status_code == 403

    def test_excluir_servico_restrito_a_prestador(self):
        afiliado = make_user(role=CustomUser.Role.AFILIADO)
        self.client.force_login(afiliado)
        response = self.client.post(reverse("services-delete", kwargs={"pk": self.service.pk}))
        assert response.status_code == 403

    def test_admin_pode_editar_servico_de_outro(self):
        admin = make_user(role=CustomUser.Role.ADMIN)
        self.client.force_login(admin)
        response = self.client.get(reverse("services-update", kwargs={"slug": self.service.slug}))
        assert response.status_code == 200


class TestProviderRequestListQueries(TestCase):
    """Testes de contagem de queries para views de prestador."""

    def setUp(self):
        super().setUp()
        self.category = ServiceCategory.objects.create(name="Elétrica", slug="eletrica-query")
        self.provider = make_user(role=CustomUser.Role.PRESTADOR)
        self.cliente = make_user(role=CustomUser.Role.CLIENTE)
        self.service = Service.objects.create(
            name="Serviço Query",
            slug="servico-query",
            base_price=10,
            category=self.category,
            created_by=self.provider,
        )
        self.service.providers.add(self.provider)

    def test_provider_requests_uses_select_related(self):
        """ProviderServiceRequestListView deve usar select_related para service, cliente, prestador."""
        ServiceRequest.objects.create(cliente=self.cliente, service=self.service, prestador=self.provider)
        self.client.force_login(self.provider)
        # Framework: session + user + socialaccount = 3
        # Sitesettings: 1
        # View: count (1) + list with select_related (1) = 2
        # Total: 6
        with self.assertNumQueries(6):
            response = self.client.get(reverse("services-provider-requests"))
        assert response.status_code == 200


class TestMyRequestsQueries(TestCase):
    """Testes de contagem de queries para minhas solicitações."""

    def setUp(self):
        super().setUp()
        self.category = ServiceCategory.objects.create(name="Elétrica", slug="eletrica-myreq")
        self.provider = make_user(role=CustomUser.Role.PRESTADOR)
        self.cliente = make_user(role=CustomUser.Role.CLIENTE)
        self.service = Service.objects.create(
            name="Serviço MyReq",
            slug="servico-myreq",
            base_price=10,
            category=self.category,
            created_by=self.provider,
        )
        self.service.providers.add(self.provider)

    def test_my_requests_uses_select_related(self):
        """MyServiceRequestListView deve usar select_related para service, prestador."""
        ServiceRequest.objects.create(cliente=self.cliente, service=self.service, prestador=self.provider)
        self.client.force_login(self.cliente)
        # Framework: session + user + socialaccount = 3
        # Sitesettings: 1
        # View: count (1) + list with select_related (1) = 2
        # Total: 6
        with self.assertNumQueries(6):
            response = self.client.get(reverse("services-my-requests"))
        assert response.status_code == 200
