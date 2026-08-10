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
        response = self.client.post(
            reverse("services-create"),
            {
                "name": "Instalação de lâmpada",
                "slug": "instalacao-lampada",
                "category": self.category.pk,
                "description": "teste",
                "base_price": "50.00",
            },
        )
        assert response.status_code == 302
        service = Service.objects.get(slug="instalacao-lampada")
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
                "slug": service.slug,
                "category": self.category.pk,
                "description": "",
                "base_price": "20.00",
                "is_active": "on",
            },
        )
        assert response.status_code == 302
        service.refresh_from_db()
        assert service.name == "Serviço X atualizado"

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
            "apps.payments.services.charge_order", side_effect=ValueError("gateway fora")
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
        with mock.patch("apps.payments.services.charge_order", return_value=fake):
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
