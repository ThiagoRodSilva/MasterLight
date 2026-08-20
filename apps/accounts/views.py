"""Views de accounts."""

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import DetailView, FormView

from .forms import ProfileEditForm, SocialSignupCompleteForm
from .models import CustomUser


@login_required
def me_view(request):
    """Dashboard rapido do proprio usuario."""
    return render(request, "accounts/me.html", {})


class ProfileDetailView(DetailView):
    """Perfil publico de prestadores/afiliados."""

    model = CustomUser
    template_name = "accounts/profile.html"
    slug_field = "username"
    slug_url_kwarg = "username"
    context_object_name = "profile_user"

    def get_queryset(self):
        return CustomUser.objects.filter(
            is_active=True,
            role__in=[CustomUser.Role.PRESTADOR, CustomUser.Role.AFILIADO],
            public_profile__is_active=True,
        ).select_related("public_profile")


class ProfileEditView(LoginRequiredMixin, FormView):
    """Edição dos dados pessoais e de pagamento (CPF, telefone, endereço)."""

    form_class = ProfileEditForm
    template_name = "accounts/me_edit.html"
    success_url = reverse_lazy("accounts-me")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Dados atualizados.")
        return super().form_valid(form)


class SocialSignupCompleteView(FormView):
    """Tela obrigatória de completamento após login social."""

    template_name = "accounts/social_signup_complete.html"
    form_class = SocialSignupCompleteForm
    success_url = reverse_lazy("home")

    def dispatch(self, request, *args, **kwargs):
        # Exige sociallogin na sessão
        if "sociallogin" not in request.session:
            return redirect("account_login")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def form_valid(self, form):
        from allauth.socialaccount.models import SocialAccount, SocialLogin

        sociallogin = SocialLogin.deserialize(self.request.session.pop("sociallogin"))
        # O sociallogin da sessão foi serializado antes do save do allauth:
        # o usuário está sem pk e a SocialAccount idem. O usuário real (criado
        # e logado no signup do allauth) é usado no lugar do usuário da sessão,
        # e a conta real já existente substitui a serializada — evita duplicar
        # usuário e violar UNIQUE(provider, uid) no connect.
        sociallogin.user = self.request.user
        social_account = getattr(sociallogin, "account", None)
        if social_account is not None:
            existing_account = SocialAccount.objects.filter(
                user=self.request.user,
                provider=social_account.provider,
                uid=social_account.uid,
            ).first()
            if existing_account:
                sociallogin.account = existing_account
        user = form.save(sociallogin.user, sociallogin)
        # Loga o usuário
        login(self.request, user, backend="allauth.account.auth_backends.AuthenticationBackend")
        messages.success(self.request, "Cadastro completado! Bem-vindo à MasterLight.")
        return super().form_valid(form)
