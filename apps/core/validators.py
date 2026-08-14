"""Validators de uso transversal."""

import re

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.utils.deconstruct import deconstructible
from django.utils.translation import gettext_lazy as _

_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp", "avif", "svg"}


@deconstructible
class ImageURLValidator(URLValidator):
    """Valida URL HTTP/HTTPS apontando para uma imagem."""

    message = _("Informe uma URL de imagem válida (.jpg, .png, .webp, etc.).")

    def __call__(self, value: str) -> None:
        super().__call__(value)
        extension = re.search(r"\.([A-Za-z0-9]+)(?:[?#]|$)", value)
        if extension is None or extension.group(1).lower() not in _IMAGE_EXTENSIONS:
            raise ValidationError(self.message)


def validate_image_url(value: str) -> None:
    ImageURLValidator()(value)


def validate_brazilian_cpf(value: str) -> None:
    """Valida CPF brasileiro (11 dígitos e dígitos verificadores).

    Aceita valor mascarado (pontos/traço são ignorados). Rejeita CPFs de
    dígitos repetidos ou com checksum inválido — o Asaas devolve 400 para
    `cpfCnpj` inválido na criação do customer.
    """
    digits = re.sub(r"\D", "", value or "")
    if len(digits) != 11 or digits == digits[0] * 11:
        raise ValidationError(_("Informe um CPF válido."))
    for length in (9, 10):
        total = sum(int(digits[i]) * (length + 1 - i) for i in range(length))
        check = (total * 10) % 11 % 10
        if int(digits[length]) != check:
            raise ValidationError(_("Informe um CPF válido."))
