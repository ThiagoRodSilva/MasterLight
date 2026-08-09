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


class MaintenancePlan(BaseModel):
    class PlanType(models.TextChoices):
        MONTHLY = "mensal", _("Mensal")
        QUARTERLY = "trimestral", _("Trimestral")
        ANNUAL = "anual", _("Anual")

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

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Solicitação de Serviço"
        verbose_name_plural = "Solicitações de Serviços"

    def __str__(self) -> str:
        return f"{self.service.name} - {self.get_status_display()}"
