from django.contrib import admin

from .models import Category, Product, ProductImage, ProductVariant


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "price", "stock", "category", "featured", "is_active")
    list_filter = ("category", "featured")
    search_fields = ("name", "sku", "description")
    date_hierarchy = "created_at"
    inlines = [ProductVariantInline, ProductImageInline]


admin.site.register(ProductImage)
admin.site.register(ProductVariant)
