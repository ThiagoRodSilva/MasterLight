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

    def test_ftp_rejeitado(self):
        with self.assertRaises(ValidationError):
            validate_image_url("ftp://example.com/foto.png")

    def test_svg_rejeitado(self):
        with self.assertRaises(ValidationError):
            validate_image_url("https://exemplo.com/foto.svg")

    def test_jpg_ok(self):
        validate_image_url("https://exemplo.com/foto.jpg")

    def test_png_ok(self):
        validate_image_url("https://exemplo.com/foto.png")

    def test_webp_ok(self):
        validate_image_url("https://exemplo.com/foto.webp")

    def test_avif_ok(self):
        validate_image_url("https://exemplo.com/foto.avif")

    def test_gif_ok(self):
        validate_image_url("https://exemplo.com/foto.gif")
