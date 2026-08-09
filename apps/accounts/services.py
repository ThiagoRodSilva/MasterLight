"""Business logic de contas: aprovação de prestadores."""

from django.utils import timezone

from .models import CustomUser, ProviderApplication, PublicProfile


def approve_provider_application(application: ProviderApplication, admin) -> None:
    """Aprova a solicitação e promove o usuário a prestador.

    Levanta ValueError para fluxos inválidos (solicitação inexistente
    ou usuário desativado).
    """
    if not application.is_pending:
        raise ValueError("A solicitação já foi analisada.")
    user = application.user
    if not user.is_active:
        raise ValueError("O usuário não pode ser aprovado com a conta desativada.")
    user.role = CustomUser.Role.PRESTADOR
    user.save(update_fields=["role"])
    profile, _ = PublicProfile.objects.get_or_create(user=user)
    if application.bio and not profile.bio:
        profile.bio = application.bio
        profile.save(update_fields=["bio"])
    application.status = ProviderApplication.Status.APPROVED
    application.reviewed_by = admin
    application.reviewed_at = timezone.now()
    application.save(update_fields=["status", "reviewed_by", "reviewed_at"])


def reject_provider(application: ProviderApplication, admin) -> None:
    """Recusa a solicitação; o usuário permanece como cliente."""
    if not application.is_pending:
        raise ValueError("A solicitação já foi analisada.")
    application.status = ProviderApplication.Status.REJECTED
    application.reviewed_by = admin
    application.reviewed_at = timezone.now()
    application.save(update_fields=["status", "reviewed_by", "reviewed_at"])
