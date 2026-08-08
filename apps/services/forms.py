"""Forms do app services."""
from django import forms

from .models import Service, ServiceRequest


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ["name", "slug", "category", "description", "base_price", "image", "is_active"]


class ServiceRequestForm(forms.ModelForm):
    class Meta:
        model = ServiceRequest
        fields = ["prestador", "address", "scheduled_at", "notes"]

    def __init__(self, *args, service=None, **kwargs):
        super().__init__(*args, **kwargs)
        if service is not None:
            self.fields["prestador"].queryset = service.providers.filter(is_active=True)
            if service.providers.count() == 1:
                self.initial["prestador"] = service.providers.first()
