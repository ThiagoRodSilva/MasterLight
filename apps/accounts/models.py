"""CustomUser eAMPLO de role perfis."""

from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.core.models import BaseModel
from apps.core.validators import validate_image_url


class CustomUser(AbstractUser):
    """Usuario customizado com role telefone avatar CPF.

    Roles:
        cliente    -> consumidor padrao
        prestador  -> pode cadastrar portfolio servicos
        afiliado   -> divulga e recebe comissao
        admin      -> operacional da plataforma (staff)
    """

    class Role(models.TextChoices):
        CLIENTE = "cliente", "Cliente"
        PRESTADOR = "prestador", "Prestador"
        AFILIADO = "afiliado", "Afiliado"
        ADMIN = "admin", "Admin"

    email = models.EmailField(unique=True)
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CLIENTE,
    )
    telefone = models.CharField(max_length=20, blank=True, default="")
    cpf = models.CharField(max_length=14, blank=True, default="")
    avatar = models.URLField(blank=True, null=True, validators=[validate_image_url])
    asaas_customer_id = models.CharField(max_length=64, blank=True, default="", db_index=True)

    # configuracoes herdadadas do AbstractUser
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self) -> str:
        return f"{self.get_full_name() or self.email} ({self.get_role_display()})"

    @property
    def is_prestador(self) -> bool:
        return self.role == self.Role.PRESTADOR or self.is_superuser

    @property
    def is_afiliado(self) -> bool:
        return self.role == self.Role.AFILIADO

    @property
    def is_admin(self) -> bool:
        return self.role == self.Role.ADMIN or self.is_superuser


class PublicProfile(BaseModel):
    """Perfil publico opcional para prestadores/afiliados."""

    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="public_profile",
    )
    bio = models.TextField(blank=True, default="")
    website = models.URLField(blank=True, default="")
    instagram = models.URLField(blank=True, default="")

    def __str__(self) -> str:
        return f"Perfil publico de {self.user.email}"


class ProviderApplication(BaseModel):
    """Solicitação de abertura de conta de prestador, aguardando aprovação do admin.

    O usuário candidato mantém `role=cliente` até a aprovação; o admin aprova
    (promove para `prestador`) ou recusa direto do Django Admin.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        APPROVED = "approved", "Aprovado"
        REJECTED = "rejected", "Recusado"

    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="provider_application",
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
    )
    bio = models.TextField(blank=True, default="", verbose_name="bio / especialidades")
    reviewed_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_applications",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "solicitação de prestador"
        verbose_name_plural = "solicitações de prestador"

    @property
    def is_pending(self) -> bool:
        return self.status == self.Status.PENDING

    def __str__(self) -> str:
        return f"Solicitação de {self.user.email} ({self.get_status_display()})"
