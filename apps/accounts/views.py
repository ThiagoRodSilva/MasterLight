"""Views de accounts."""

from django.shortcuts import render
from django.views.generic import DetailView

from .models import CustomUser


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
