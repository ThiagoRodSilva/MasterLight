"""Forms do app services."""

from django import forms

from .models import MaintenancePlan, MaintenancePlanTemplate, Service, ServiceRequest


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ["name", "category", "description", "base_price", "image", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["image"].help_text = "Cole o link direto da imagem — .jpg, .png, .webp, etc."


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


class MaintenancePlanForm(forms.ModelForm):
    class Meta:
        model = MaintenancePlan
        fields = ["plan_type", "prestador"]

    def __init__(self, *args, **kwargs):
        from apps.accounts.models import CustomUser

        super().__init__(*args, **kwargs)
        self.fields["plan_type"].label = "Plano"
        self.fields["prestador"].label = "Prestador responsável"
        self.fields["prestador"].queryset = CustomUser.objects.filter(
            role="prestador", is_active=True
        )

    def clean(self):
        cleaned = super().clean()
        plan_type = cleaned.get("plan_type")
        if plan_type:
            template = MaintenancePlanTemplate.objects.filter(
                plan_type=plan_type, is_active=True
            ).first()
            if template is None:
                raise forms.ValidationError("Este plano está indisponível no momento.")
            cleaned["value"] = template.value
        return cleaned
