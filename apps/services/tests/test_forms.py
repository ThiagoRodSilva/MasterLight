"""Testes do ServiceForm (URL de imagem)."""

from django.test import TestCase

from apps.services.forms import ServiceForm
from apps.services.models import ServiceCategory


class TestServiceFormImage(TestCase):
    def setUp(self):
        self.category = ServiceCategory.objects.create(name="Elétrica", slug="eletrica")

    def _data(self, **overrides):
        data = {
            "name": "Instalação",
            "category": self.category.pk,
            "description": "",
            "base_price": "50.00",
            "is_active": "on",
        }
        data.update(overrides)
        return data

    def test_url_de_imagem_valida_salva(self):
        form = ServiceForm(
            data=self._data(image="https://exemplo.com/servico.jpg")
        )
        assert form.is_valid()

    def test_url_de_imagem_invalida_rejeita(self):
        form = ServiceForm(
            data=self._data(image="https://exemplo.com/arquivo.pdf")
        )
        assert not form.is_valid()
        assert "image" in form.errors
