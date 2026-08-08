"""CustomUser eAMPLO de role perfis."""

from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.core.models import BaseModel


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
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
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
