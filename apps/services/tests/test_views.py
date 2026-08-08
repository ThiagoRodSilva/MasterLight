"""Testes das views de serviços (catálogo, self-service e solicitações)."""
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.services.models import Service, ServiceCategory, ServiceRequest
from conftest import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def provider():
    return UserFactory(role=CustomUser.Role.PRESTADOR)


@pytest.fixture
def cliente():
    return UserFactory(role=CustomUser.Role.CLIENTE)


@pytest.fixture
def category():
    return ServiceCategory.objects.create(name="Elétrica", slug="eletrica")


class TestServiceSelfService:
    def test_provider_can_create_service_and_is_provider(self, provider, category, client):
        client.force_login(provider)
        response = client.post(
            reverse("services-create"),
            {
                "name": "Instalação de lâmpada",
                "slug": "instalacao-lampada",
                "category": category.pk,
                "description": "teste",
                "base_price": "50.00",
            },
        )
        assert response.status_code == 302
        service = Service.objects.get(slug="instalacao-lampada")
        assert service.created_by == provider
        assert provider in service.providers.all()

    def test_cliente_cannot_create_service(self, cliente, category, client):
        client.force_login(cliente)
        response = client.get(reverse("services-create"))
        assert response.status_code in (302, 403)

    def test_owner_can_edit_service(self, provider, category, client):
        service = Service.objects.create(
            name="Serviço X",
            slug="servico-x",
            base_price=10,
            category=category,
            created_by=provider,
        )
        client.force_login(provider)
        response = client.post(
            reverse("services-update", kwargs={"slug": service.slug}),
            {
                "name": "Serviço X atualizado",
                "slug": service.slug,
                "category": category.pk,
                "description": "",
                "base_price": "20.00",
                "is_active": "on",
            },
        )
        assert response.status_code == 302
        service.refresh_from_db()
        assert service.name == "Serviço X atualizado"

    def test_non_owner_cannot_edit_service(self, provider, category, client):
        owner = UserFactory(role=CustomUser.Role.PRESTADOR)
        service = Service.objects.create(
            name="Serviço Y",
            slug="servico-y",
            base_price=10,
            category=category,
            created_by=owner,
        )
        client.force_login(provider)
        response = client.get(reverse("services-update", kwargs={"slug": service.slug}))
        assert response.status_code in (302, 403, 404)


class TestServiceRequestFlow:
    def test_cliente_requests_service_with_provider(self, provider, category, client):
        service = Service.objects.create(
            name="Serviço Z",
            slug="servico-z",
            base_price=10,
            category=category,
            created_by=provider,
        )
        service.providers.add(provider)
        cliente = UserFactory(role=CustomUser.Role.CLIENTE)
        client.force_login(cliente)
        response = client.post(
            reverse("services-request", kwargs={"slug": service.slug}),
            {"prestador": provider.pk, "address": "Rua A, 100", "notes": ""},
        )
        assert response.status_code == 302
        sr = ServiceRequest.objects.get(service=service)
        assert sr.cliente == cliente
        assert sr.prestador == provider

    def test_provider_sees_request_and_quotes(self, provider, category, client):
        service = Service.objects.create(
            name="Serviço Q",
            slug="servico-q",
            base_price=10,
            category=category,
            created_by=provider,
        )
        cliente = UserFactory(role=CustomUser.Role.CLIENTE)
        sr = ServiceRequest.objects.create(
            cliente=cliente, service=service, prestador=provider
        )
        client.force_login(provider)
        response = client.get(reverse("services-provider-requests"))
        assert response.status_code == 200
        assert service.name in response.content.decode()

        response = client.post(
            reverse("services-request-quote", kwargs={"pk": sr.pk}),
            {"final_price": "99.90"},
        )
        assert response.status_code == 302
        sr.refresh_from_db()
        assert sr.status == ServiceRequest.Status.QUOTED
        assert sr.final_price == Decimal("99.90")

    def test_cliente_can_cancel_request(self, provider, category, client):
        service = Service.objects.create(
            name="Serviço C",
            slug="servico-c",
            base_price=10,
            category=category,
            created_by=provider,
        )
        cliente = UserFactory(role=CustomUser.Role.CLIENTE)
        sr = ServiceRequest.objects.create(cliente=cliente, service=service)
        client.force_login(cliente)
        response = client.post(
            reverse("services-request-cancel", kwargs={"pk": sr.pk})
        )
        assert response.status_code == 302
        sr.refresh_from_db()
        assert sr.status == ServiceRequest.Status.CANCELED


class TestCatalogo:
    def test_list_public(self, client, category):
        Service.objects.create(
            name="Serviço Público",
            slug="servico-publico",
            base_price=5,
            category=category,
        )
        response = client.get(reverse("services-list"))
        assert response.status_code == 200
        assert b"Servi" in response.content

    def test_detail_public(self, client, category):
        service = Service.objects.create(
            name="Serviço Detalhe",
            slug="servico-detalhe",
            base_price=5,
            category=category,
        )
        response = client.get(reverse("services-detail", kwargs={"slug": service.slug}))
        assert response.status_code == 200
