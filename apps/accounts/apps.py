from django.apps import AppConfig
from django.db.models.signals import post_save


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    label = "accounts"

    def ready(self):
        from apps.accounts.models import CustomUser, PublicProfile
        from apps.affiliate.models import AffiliateProfile

        def create_affiliate_profile(sender, instance, created, **kwargs):
            """Todo novo usuario recebe AffiliateProfile (tracking code)."""
            if not created:
                return
            AffiliateProfile.objects.get_or_create(user=instance)

        def create_public_profile(sender, instance, created, **kwargs):
            """Cria PublicProfile para prestador/afiliado no create ou na troca de role.
            Não desativa/deleta ao virar cliente (decisão de design).
            """
            if created and instance.role not in (
                CustomUser.Role.PRESTADOR,
                CustomUser.Role.AFILIADO,
            ):
                return
            if instance.role in (CustomUser.Role.PRESTADOR, CustomUser.Role.AFILIADO):
                PublicProfile.objects.get_or_create(user=instance)

        post_save.connect(create_affiliate_profile, sender=CustomUser)
        post_save.connect(create_public_profile, sender=CustomUser)
