"""Catalogo de servicos e solicitacoes de clientes."""

from typing import TYPE_CHECKING

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import CustomUser
from apps.core.models import BaseModel, RandomSlugMixin
from apps.core.validators import validate_image_url

if TYPE_CHECKING:
    pass


class ServiceCategory(BaseModel, RandomSlugMixin):
    name = models.CharField(max_length=80, verbose_name="nome")
    slug = models.SlugField(unique=True, verbose_name="slug", editable=False)
    icon = models.CharField(max_length=60, blank=True, default="", verbose_name="ícone")

    class Meta:
        verbose_name = "Categoria de Serviço"
        verbose_name_plural = "Categorias de Serviços"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Service(BaseModel, RandomSlugMixin):
    name = models.CharField(max_length=160, verbose_name="nome")
    slug = models.SlugField(unique=True, verbose_name="slug", editable=False)
    description = models.TextField(blank=True, default="", verbose_name="descrição")
    base_price = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name="preço base"
    )
    category = models.ForeignKey(
        ServiceCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="services",
        verbose_name="categoria",
    )
    providers = models.ManyToManyField(
        CustomUser,
        limit_choices_to={"role": "prestador"},
        related_name="services",
        blank=True,
        verbose_name="prestadores",
    )
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_services",
        verbose_name="criado por",
    )
    image = models.URLField(
        blank=True, null=True, validators=[validate_image_url], verbose_name="imagem"
    )
    affiliate_commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="comissão do afiliado",
        help_text="Override da comissão do afiliado para este serviço (ex.: 0.15 = 15%)",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Serviço"
        verbose_name_plural = "Serviços"

    def __str__(self) -> str:
        return self.name


class ServiceRequest(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", _("Pendente")
        QUOTED = "quoted", _("Orçado")
        APPROVED = "approved", _("Aprovado")
        CONCLUDED = "concluded", _("Concluído")
        CANCELED = "canceled", _("Cancelado")

    cliente = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="service_requests",
        verbose_name="cliente",
    )
    prestador = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_service_requests",
        limit_choices_to={"role": "prestador"},
        verbose_name=_("prestador atribuído"),
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name="requests",
        verbose_name="serviço",
    )
    order = models.OneToOneField(
        "checkout.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_request",
        verbose_name="pedido de pagamento",
    )
    address = models.CharField(_("endereço"), max_length=500, blank=True, default="")
    scheduled_at = models.DateTimeField(_("agendado para"), null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="situação",
    )
    final_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        null=True,
        blank=True,
        verbose_name="preço do orçamento",
    )
    notes = models.TextField(blank=True, default="", verbose_name="observações")
    asaas_payment_link_id = models.CharField(
        _("link de pagamento (Asaas)"),
        max_length=120,
        blank=True,
        default="",
        db_index=True,
        help_text="Id do paymentLink avulso; usado para reconciliar o pagamento via webhook.",
    )
    affiliate_ref_code = models.CharField(
        _("código de afiliado (referral)"),
        max_length=20,
        blank=True,
        default="",
        help_text="Código do afiliado que indicou esta solicitação (cookie ref).",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Solicitação de Serviço"
        verbose_name_plural = "Solicitações de Serviços"

    def __str__(self) -> str:
        return f"{self.service.name} - {self.get_status_display()}"
