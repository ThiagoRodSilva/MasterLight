from django.urls import path

from .views import ProductDetailView, ProductListView

urlpatterns = [
    path("", ProductListView.as_view(), name="shop-list"),
    path("categoria/<slug:category_slug>/", ProductListView.as_view(), name="shop-category"),
    path("<slug:slug>/", ProductDetailView.as_view(), name="shop-detail"),
]
