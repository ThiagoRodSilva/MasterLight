"""Modelos base compartilhados (timestamps)."""

import secrets
import uuid
from typing import ClassVar

from django.db import models
from django.utils import timezone


def random_slug(length: int = 8) -> str:
    """Gera um slug aleatório (hex) para URLs não adivinháveis."""
    return secrets.token_hex(length)


class BaseModel(models.Model):
    """Modelo abstrato com campos de auditoria padronizados."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True


class RandomSlugMixin(models.Model):
    """Preenche o slug automático quando vazio.

    Requer que o modelo tenha um campo `slug`. Em updates o slug existente
    é preservado (URLs estáveis); apenas a criação gera um valor aleatório.
    """

    slug: models.SlugField

    class Meta:
        abstract = True

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = random_slug()
        super().save(*args, **kwargs)


class SiteSettings(models.Model):
    """Configuração global do site (linha única, editável no Admin).

    Controla a disponibilidade pública de cada seção: serviços e programa de
    afiliados. É uma configuração, não um dado de domínio,
    por isso não herda `BaseModel` e usa `pk=1` fixa (singleton).
    """

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    services_enabled = models.BooleanField(default=True, verbose_name="serviços habilitados")
    affiliates_enabled = models.BooleanField(
        default=True, verbose_name="programa de afiliados habilitado"
    )
    provider_registration_enabled = models.BooleanField(
        default=True, verbose_name="cadastro de prestadores habilitado"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuração do site"
        verbose_name_plural = "Configurações do site"

    _FLAGS: ClassVar[tuple[str, ...]] = (
        "services_enabled",
        "affiliates_enabled",
        "provider_registration_enabled",
    )

    def save(self, *args, **kwargs) -> None:
        # Garante a linha única (singleton) sempre com pk=1: se a linha já
        # existe, atualiza-a no lugar de tentar inserir um duplicado.
        self.pk = 1
        now = timezone.now()
        update_fields = kwargs.get("update_fields")
        if self.__class__.objects.filter(pk=1).exists():
            if update_fields is None:
                flag_fields = self._FLAGS
            else:
                flag_fields = [f for f in update_fields if f in self._FLAGS]
            if flag_fields:
                update_data = {f: getattr(self, f) for f in flag_fields}
                update_data["updated_at"] = now
                self.__class__.objects.filter(pk=1).update(**update_data)
                self.updated_at = now
            return
        self.updated_at = now
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "SiteSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self) -> str:
        return "Configuração do site"
