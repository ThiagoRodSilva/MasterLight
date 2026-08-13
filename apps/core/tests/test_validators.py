"""Testes do validador de URL de imagem."""

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.core.validators import validate_image_url


class TestImageURLValidator(SimpleTestCase):
    def test_url_valida_passa(self):
        validate_image_url("https://exemplo.com/foto.png")
        validate_image_url("https://exemplo.com/foto.JPG")
        validate_image_url("https://exemplo.com/caminho/foto.webp?size=800")

    def test_url_sem_extensao_de_imagem_rejeita(self):
        with self.assertRaises(ValidationError):
            validate_image_url("https://exemplo.com/arquivo.pdf")

    def test_url_malformada_rejeita(self):
        with self.assertRaises(ValidationError):
            validate_image_url("nao-e-uma-url")

    def test_http_aceito(self):
        validate_image_url("http://exemplo.com/foto.gif")
