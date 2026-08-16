"""Testes do portfolio (visibilidade)."""

from django.shortcuts import reverse
from django.test import TestCase

from apps.accounts.models import CustomUser
from apps.portfolio.models import PortfolioItem
from apps.tests.helpers import make_user


class TestPortfolioVisibility(TestCase):
    def test_unpublished_item_404_on_detail(self):
        owner = make_user()
        item = PortfolioItem.objects.create(
            title="Privado", description="", category="", published=False, created_by=owner
        )
        response = self.client.get(reverse("portfolio-detail", args=[item.pk]))
        assert response.status_code == 404

    def test_published_item_200_on_detail(self):
        owner = make_user()
        item = PortfolioItem.objects.create(
            title="Publico", description="", category="", published=True, created_by=owner
        )
        response = self.client.get(reverse("portfolio-detail", args=[item.pk]))
        assert response.status_code == 200

    def test_inactive_item_404_on_detail(self):
        owner = make_user()
        item = PortfolioItem.objects.create(
            title="Inativo",
            description="",
            category="",
            published=True,
            is_active=False,
            created_by=owner,
        )
        response = self.client.get(reverse("portfolio-detail", args=[item.pk]))
        assert response.status_code == 404


class TestPortfolioUpdateRoleSeparation(TestCase):
    def setUp(self):
        super().setUp()
        self.provider = make_user(role=CustomUser.Role.PRESTADOR)
        self.item = PortfolioItem.objects.create(
            title="Meu item",
            description="",
            category="",
            published=True,
            created_by=self.provider,
        )

    def test_update_restrito_a_prestador(self):
        for role in (CustomUser.Role.CLIENTE, CustomUser.Role.AFILIADO):
            with self.subTest(role=role):
                user = make_user(role=role)
                self.client.force_login(user)
                response = self.client.get(reverse("portfolio-update", args=[self.item.pk]))
                assert response.status_code == 403

    def test_admin_pode_atualizar_item_de_outro(self):
        admin = make_user(role=CustomUser.Role.ADMIN)
        self.client.force_login(admin)
        response = self.client.get(reverse("portfolio-update", args=[self.item.pk]))
        assert response.status_code == 200
