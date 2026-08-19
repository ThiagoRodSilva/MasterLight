"""Views de loja."""

from django.views.generic import DetailView, ListView

from apps.core.mixins import SectionEnabledMixin

from .models import Category, Product


class ProductListView(SectionEnabledMixin, ListView):
    section_flag = "store_enabled"
    template_name = "shop/list.html"
    context_object_name = "products"
    paginate_by = 12

    def get_queryset(self):
        qs = Product.objects.filter(is_active=True)
        category_slug = self.kwargs.get("category_slug") or self.request.GET.get("categoria")
        q = self.request.GET.get("q")
        if category_slug:
            qs = qs.filter(category__slug=category_slug)
        if q:
            qs = qs.filter(name__icontains=q)
        return qs.select_related("category").prefetch_related("images")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categories"] = Category.objects.filter(is_active=True)
        ctx["active_category"] = self.kwargs.get("category_slug") or self.request.GET.get(
            "categoria"
        )
        return ctx


class ProductDetailView(SectionEnabledMixin, DetailView):
    section_flag = "store_enabled"
    template_name = "shop/detail.html"
    context_object_name = "product"

    def get_queryset(self):
        return Product.objects.filter(is_active=True).select_related("category").prefetch_related("images", "variants")
