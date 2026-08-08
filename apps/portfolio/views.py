"""Views do portfolio."""
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.core.mixins import OwnerRequiredMixin, ProviderRequiredMixin

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
        return qs


class PortfolioDetailView(DetailView):
    template_name = "portfolio/detail.html"
    context_object_name = "item"

    def get_queryset(self):
        return PortfolioItem.objects.filter(published=True, is_active=True)


class PortfolioCreateView(ProviderRequiredMixin, CreateView):
    model = PortfolioItem
    fields = ["title", "description", "category", "image", "video", "published"]
    template_name = "portfolio/form.html"
    success_url = reverse_lazy("portfolio-list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class PortfolioUpdateView(OwnerRequiredMixin, UpdateView):
    model = PortfolioItem
    fields = ["title", "description", "category", "image", "video", "published"]
    template_name = "portfolio/form.html"
    success_url = reverse_lazy("portfolio-list")
