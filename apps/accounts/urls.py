"""URLs de accounts: perfil publico e meus dados (allauth trata login)."""

from django.urls import path

from .views import ProfileDetailView, me_view

urlpatterns = [
    path("me/", me_view, name="accounts-me"),
    path("u/<str:username>/", ProfileDetailView.as_view(), name="accounts-profile"),
]
