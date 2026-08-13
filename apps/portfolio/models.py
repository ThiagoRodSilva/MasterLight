"""Modelos do portfolio de prestadores."""

from django.db import models

from apps.accounts.models import CustomUser
from apps.core.models import BaseModel
from apps.core.validators import validate_image_url


class PortfolioItem(BaseModel):
    title = models.CharField(max_length=160, verbose_name="título")
    description = models.TextField(blank=True, default="", verbose_name="descrição")
    category = models.CharField(max_length=80, blank=True, default="", verbose_name="categoria")
    image = models.URLField(blank=True, null=True, validators=[validate_image_url], verbose_name="imagem")
    video = models.URLField(blank=True, default="", verbose_name="vídeo")
    published = models.BooleanField(default=False, verbose_name="publicado")
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="portfolio_items",
        verbose_name="criado por",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Item de Portfólio"
        verbose_name_plural = "Itens de Portfólio"

    def __str__(self) -> str:
        return self.title
