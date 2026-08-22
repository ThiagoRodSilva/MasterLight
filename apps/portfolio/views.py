"""Views do portfolio."""

from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.core.mixins import OwnerRequiredMixin, ProviderRequiredMixin

from .forms import PortfolioItemForm
from .models import PortfolioItem


class PortfolioListView(ListView):
    template_name = "portfolio/list.html"
    context_object_name = "items"
    paginate_by = 12

    def get_queryset(self):
        qs = PortfolioItem.objects.filter(published=True, is_active=True)
        cat = self.request.GET.get("categoria")
        if cat:
            qs = qs.filter(category=cat)
        return qs.select_related("created_by")


class PortfolioDetailView(DetailView):
    template_name = "portfolio/detail.html"
    context_object_name = "item"

    def get_queryset(self):
        return PortfolioItem.objects.filter(published=True, is_active=True).select_related("created_by")


class PortfolioCreateView(ProviderRequiredMixin, CreateView):
    model = PortfolioItem
    form_class = PortfolioItemForm
    template_name = "portfolio/form.html"
    success_url = reverse_lazy("portfolio-list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class PortfolioUpdateView(ProviderRequiredMixin, OwnerRequiredMixin, UpdateView):
    model = PortfolioItem
    form_class = PortfolioItemForm
    template_name = "portfolio/form.html"
    success_url = reverse_lazy("portfolio-list")
