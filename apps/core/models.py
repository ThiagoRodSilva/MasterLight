"""Modelos base compartilhados (timestamps)."""

import secrets
import uuid

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

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = random_slug()
        super().save(*args, **kwargs)


class SiteSettings(models.Model):
    """Configuração global do site (linha única, editável no Admin).

    Controla a disponibilidade pública de cada seção: loja, serviços e
    programa de afiliados. É uma configuração, não um dado de domínio,
    por isso não herda `BaseModel` e usa `pk=1` fixa (singleton).
    """

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    store_enabled = models.BooleanField(default=True, verbose_name="loja habilitada")
    services_enabled = models.BooleanField(default=True, verbose_name="serviços habilitados")
    affiliates_enabled = models.BooleanField(
        default=True, verbose_name="programa de afiliados habilitado"
    )
    maintenance_enabled = models.BooleanField(
        default=True, verbose_name="manutenção habilitada"
    )
    provider_registration_enabled = models.BooleanField(
        default=True, verbose_name="cadastro de prestadores habilitado"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuração do site"
        verbose_name_plural = "Configurações do site"

    def save(self, *args, **kwargs):
        # Garante a linha única (singleton) sempre com pk=1: se a linha já
        # existe, atualiza-a no lugar de tentar inserir um duplicado.
        self.pk = 1
        now = timezone.now()
        if self.__class__.objects.filter(pk=1).exists():
            self.__class__.objects.filter(pk=1).update(
                store_enabled=self.store_enabled,
                services_enabled=self.services_enabled,
                affiliates_enabled=self.affiliates_enabled,
                maintenance_enabled=self.maintenance_enabled,
                provider_registration_enabled=self.provider_registration_enabled,
                updated_at=now,
            )
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
