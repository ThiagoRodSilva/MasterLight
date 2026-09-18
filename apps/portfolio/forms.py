"""Forms do app portfolio."""

from django import forms

from .models import PortfolioItem


class PortfolioItemForm(forms.ModelForm):
    """Form para itens do portfólio do prestador."""

    class Meta:
        model = PortfolioItem
        fields = ["title", "description", "category", "image", "video"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["image"].help_text = "Link direto da imagem (.jpg, .png, .webp)"
        self.fields["video"].help_text = "Link do YouTube/Vimeo (opcional)"
