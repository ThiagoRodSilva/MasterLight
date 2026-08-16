"""Views de accounts."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import DetailView, FormView

from .forms import ProfileEditForm
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
        return CustomUser.objects.filter(is_active=True)


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
