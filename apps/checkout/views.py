"""Views de pedido/endereço."""

from django.urls import reverse_lazy
from django.views.generic import CreateView

from apps.core.mixins import ClienteRequiredMixin

from .forms import AddressForm
from .models import Address


class AddressCreateView(ClienteRequiredMixin, CreateView):
    model = Address
    form_class = AddressForm
    template_name = "checkout/address_form.html"
    success_url = reverse_lazy("accounts-me")

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)