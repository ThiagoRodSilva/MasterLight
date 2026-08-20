"""Catalogo de servicos e solicitacoes de clientes."""

from typing import TYPE_CHECKING

from django.db import models
from django.db.models import Q
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
    image = models.URLField(blank=True, null=True, validators=[validate_image_url], verbose_name="imagem")
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


class MaintenancePlan(BaseModel):
    class PlanType(models.TextChoices):
        MONTHLY = "mensal", _("Mensal")
        QUARTERLY = "trimestral", _("Trimestral")
        ANNUAL = "anual", _("Anual")

    DESCRIPTIONS: dict[str, str] = {
        "mensal": _("Uma visita por mês, com acompanhamento contínuo."),
        "trimestral": _("Uma visita a cada 3 meses. Melhor custo-benefício."),
        "anual": _("Visitas para o ano inteiro, com desconto no ciclo."),
    }

    plan_type = models.CharField(
        max_length=20,
        choices=PlanType.choices,
        default=PlanType.MONTHLY,
        verbose_name="tipo de plano",
    )
    value = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name="valor do ciclo"
    )
    next_due_date = models.DateField(verbose_name="próximo vencimento")
    client = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="maintenance_plans",
        verbose_name="cliente",
    )
    prestador = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_plans_as_provider",
        limit_choices_to={"role": "prestador"},
        verbose_name="prestador atribuído",
    )
    order = models.OneToOneField(
        "checkout.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_plan",
        verbose_name="pedido de pagamento",
    )
    asaas_subscription_id = models.CharField(
        max_length=120, blank=True, default="", db_index=True, verbose_name="assinatura Asaas"
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Plano de Manutenção"
        verbose_name_plural = "Planos de Manutenção"

    def __str__(self) -> str:
        return f"Manutenção {self.get_plan_type_display()} de {self.client}"

    @classmethod
    def cycle_days_for(cls, plan_type: str) -> int:
        """Intervalo em dias do ciclo (30/90/365) para um tipo de plano."""
        return {
            cls.PlanType.MONTHLY: 30,
            cls.PlanType.QUARTERLY: 90,
            cls.PlanType.ANNUAL: 365,
        }[plan_type]

    def cycle_days(self) -> int:
        """Intervalo em dias do ciclo (30/90/365) para avançar vencimentos."""
        return self.cycle_days_for(self.plan_type)


class MaintenancePlanTemplate(BaseModel):
    """Catálogo de planos de manutenção oferecidos (CRUD via admin)."""

    name = models.CharField(max_length=120, verbose_name="nome")
    plan_type = models.CharField(
        max_length=20,
        choices=MaintenancePlan.PlanType.choices,
        default=MaintenancePlan.PlanType.MONTHLY,
        verbose_name="tipo de plano",
    )
    value = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name="preço por ciclo"
    )
    description = models.TextField(blank=True, default="", verbose_name="descrição")
    ordering = models.PositiveIntegerField(default=0, verbose_name="ordem de exibição")
    affiliate_commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="comissão do afiliado",
        help_text="Override da comissão do afiliado para assinaturas deste plano (ex.: 0.15 = 15%)",
    )

    class Meta:
        ordering = ["ordering", "value"]
        verbose_name = "Plano de Manutenção (catálogo)"
        verbose_name_plural = "Planos de Manutenção (catálogo)"
        constraints = [
            models.UniqueConstraint(
                fields=["plan_type"],
                condition=Q(is_active=True),
                name="uniq_services_active_plan_type",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} — R$ {self.value}"

    @property
    def label(self) -> str:
        return self.get_plan_type_display()


class MaintenanceVisit(BaseModel):
    plan = models.ForeignKey(
        MaintenancePlan,
        on_delete=models.CASCADE,
        related_name="visits",
        verbose_name="plano",
    )
    scheduled_at = models.DateTimeField(verbose_name="agendada para")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="concluída em")
    notes = models.TextField(blank=True, default="", verbose_name="observações")

    class Meta:
        ordering = ["scheduled_at"]
        verbose_name = "Visita de Manutenção"
        verbose_name_plural = "Visitas de Manutenção"

    def __str__(self) -> str:
        return f"Visita {self.plan} em {self.scheduled_at}"

    @property
    def is_pending(self) -> bool:
        return self.completed_at is None


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
