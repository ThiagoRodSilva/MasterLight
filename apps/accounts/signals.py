"""Sinais de accounts: criar perfil afiliado ao registrar usuario."""
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.affiliate.models import AffiliateProfile

from .models import CustomUser, PublicProfile


@receiver(post_save, sender=CustomUser)
def create_affiliate_profile(sender, instance, created, **kwargs):
    """Todo novo usuario recebe AffiliateProfile (tracking code)."""
    if not created:
        return
    AffiliateProfile.objects.get_or_create(user=instance)


@receiver(post_save, sender=CustomUser)
def create_public_profile(sender, instance, created, **kwargs):
    """Cria PublicProfile para prestador/afiliado no create ou na troca de role."""
    if created and instance.role not in (
        CustomUser.Role.PRESTADOR,
        CustomUser.Role.AFILIADO,
    ):
        return
    if instance.role in (CustomUser.Role.PRESTADOR, CustomUser.Role.AFILIADO):
        PublicProfile.objects.get_or_create(user=instance)
