from django.contrib import admin

from .models import PortfolioItem


@admin.register(PortfolioItem)
class PortfolioItemAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "published", "created_by", "created_at")
    list_filter = ("published", "category")
    search_fields = ("title", "description")
    date_hierarchy = "created_at"
