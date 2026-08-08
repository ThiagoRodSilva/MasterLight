"""URLs raiz do projeto."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.core.views import home_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home_view, name="home"),
    path("accounts/", include("apps.accounts.urls")),
    path("portfolio/", include("apps.portfolio.urls")),
    path("servicos/", include("apps.services.urls")),
    path("loja/", include("apps.shop.urls")),
    path("afiliados/", include("apps.affiliate.urls")),
    path("carrinho/", include("apps.checkout.urls")),
    path("pagamentos/", include("apps.payments.urls")),
    path("social/", include("allauth.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
