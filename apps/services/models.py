"""Catalogo de servicos e solicitacoes de clientes."""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import CustomUser
from apps.core.models import BaseModel


class ServiceCategory(BaseModel):
    name = models.CharField(max_length=80, verbose_name="nome")
    slug = models.SlugField(unique=True, verbose_name="slug")
    icon = models.CharField(max_length=60, blank=True, default="", verbose_name="ícone")

    class Meta:
        verbose_name = "Categoria de Serviço"
        verbose_name_plural = "Categorias de Serviços"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Service(BaseModel):
    name = models.CharField(max_length=160, verbose_name="nome")
    slug = models.SlugField(unique=True, verbose_name="slug")
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
    image = models.ImageField(upload_to="services/", blank=True, null=True, verbose_name="imagem")

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
    address = models.TextField(_("endereço"), blank=True, default="")
    scheduled_at = models.DateTimeField(_("agendado para"), null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="situação",
    )
    final_price = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, null=True, blank=True,
        verbose_name="preço do orçamento",
    )
    notes = models.TextField(blank=True, default="", verbose_name="observações")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Solicitação de Serviço"
        verbose_name_plural = "Solicitações de Serviços"

    def __str__(self) -> str:
        return f"{self.service.name} - {self.get_status_display()}"
