from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Avg
from django.urls import reverse
from django.utils.safestring import mark_safe
import json
from .models import (
    Product, Brand, Category, ProductImage, ProductReview, 
    ProductVariant, ProductAttribute, ProductRelated
)
from apps.utils.revalidation import revalidate_product

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ['image', 'alt_text', 'is_primary', 'order']
    readonly_fields = ['image_preview']
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="75" />', obj.image.url)
        return '-'

class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    fields = ['name', 'sku_suffix', 'price_adjustment', 'stock', 'is_active']

class ProductAttributeInline(admin.TabularInline):
    model = ProductAttribute
    extra = 2
    fields = ['name', 'value']

class ProductRelatedInline(admin.TabularInline):
    model = ProductRelated
    fk_name = 'product'
    extra = 1
    fields = ['related_product', 'relation_type']
    raw_id_fields = ['related_product']

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'thumbnail', 'name', 'sku', 'brand', 'category', 
        'format_display', 'price_display', 'stock_status', 
        'is_active', 'is_featured', 'is_new'
    ]
    list_filter = [
        'is_active', 'is_featured', 'is_new', 'requires_prescription',
        'format', 'brand', 'category', 'created_at'
    ]
    search_fields = ['name', 'sku', 'description', 'composition']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at', 'price_per_unit']
    list_editable = ['is_active', 'is_featured', 'is_new']
    inlines = [
        ProductImageInline, 
        ProductVariantInline, 
        ProductAttributeInline, 
        ProductRelatedInline
    ]
    
    fieldsets = (
        ('Información Básica', {
            'fields': (
                'name', 'slug', 'sku', 'brand', 'category', 
                'is_active', 'is_featured', 'is_new'
            )
        }),
        ('Descripción', {
            'fields': (
                'short_description', 'description', 'composition',
                'benefits', 'usage_instructions', 'recommended_dosage'
            )
        }),
        ('Presentación', {
            'fields': (
                'format', 'presentation', 'unit', 'quantity', 'dosage'
            )
        }),
        ('Precio y Stock', {
            'fields': (
                'price', 'compare_price', 'cost', 'price_per_unit',
                'stock', 'low_stock_threshold'
            )
        }),
        ('Advertencias y Regulación', {
            'fields': (
                'warnings', 'contraindications', 'side_effects', 
                'storage_conditions', 'requires_prescription',
                'batch_number', 'expiry_date', 'registration_number'
            ),
            'classes': ('collapse',)
        }),
        ('Información Técnica', {
            'fields': ('technical_info', 'nutritional_info'),
            'classes': ('collapse',),
            'description': 'Información adicional en formato JSON'
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def thumbnail(self, obj):
        image = obj.images.filter(is_primary=True).first()
        if image:
            return format_html(
                '<img src="{}" width="50" height="50" style="object-fit: cover;" />',
                image.image.url
            )
        return '-'
    thumbnail.short_description = 'Imagen'
    
    def format_display(self, obj):
        return f"{obj.get_format_display()} - {obj.presentation}"
    format_display.short_description = 'Formato'
    
    def price_display(self, obj):
        if obj.compare_price and obj.compare_price > obj.price:
            return format_html(
                '<span style="text-decoration: line-through; color: #666;">{}€</span> '
                '<span style="color: #e74c3c; font-weight: bold;">{}€</span> '
                '<span style="color: #27ae60; font-size: 0.8em;">(-{}%)</span>',
                obj.compare_price, obj.price, obj.discount_percentage
            )
        return format_html('<span>{}€</span>', obj.price)
    price_display.short_description = 'Precio'
    
    def stock_status(self, obj):
        if obj.stock == 0:
            return format_html('<span style="color: red;">⚠ Sin stock</span>')
        elif obj.is_low_stock:
            return format_html('<span style="color: orange;">⚠ Stock bajo ({0})</span>', obj.stock)
        return format_html('<span style="color: green;">✓ En stock ({0})</span>', obj.stock)
    stock_status.short_description = 'Stock'
    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Revalidar caché de Next.js automáticamente
        revalidate_product(obj)
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            images_count=Count('images'),
            reviews_count=Count('reviews'),
            avg_rating=Avg('reviews__rating')
        )
    
    actions = [
        'activate_products', 'deactivate_products', 
        'mark_as_featured', 'mark_as_new', 'export_products'
    ]
    
    def activate_products(self, request, queryset):
        count = queryset.update(is_active=True)
        for product in queryset:
            revalidate_product(product)
        self.message_user(request, f"{count} productos activados.")
    activate_products.short_description = "Activar productos seleccionados"
    
    def deactivate_products(self, request, queryset):
        count = queryset.update(is_active=False)
        for product in queryset:
            revalidate_product(product)
        self.message_user(request, f"{count} productos desactivados.")
    deactivate_products.short_description = "Desactivar productos seleccionados"
    
    def mark_as_featured(self, request, queryset):
        count = queryset.update(is_featured=True)
        for product in queryset:
            revalidate_product(product)
        self.message_user(request, f"{count} productos marcados como destacados.")
    mark_as_featured.short_description = "Marcar como destacados"
    
    def mark_as_new(self, request, queryset):
        count = queryset.update(is_new=True)
        for product in queryset:
            revalidate_product(product)
        self.message_user(request, f"{count} productos marcados como nuevos.")
    mark_as_new.short_description = "Marcar como nuevos"

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'products_count', 'is_active']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']
    list_filter = ['is_active']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(products_count=Count('products'))
    
    def products_count(self, obj):
        count = obj.products_count
        url = reverse('admin:products_product_changelist') + f'?brand__id__exact={obj.id}'
        return format_html('<a href="{}">{} productos</a>', url, count)
    products_count.short_description = 'Productos'

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'parent', 'products_count', 'order', 'is_active']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']
    list_filter = ['parent', 'is_active']
    list_editable = ['order']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(products_count=Count('products'))
    
    def products_count(self, obj):
        count = obj.products_count
        url = reverse('admin:products_product_changelist') + f'?category__id__exact={obj.id}'
        return format_html('<a href="{}">{} productos</a>', url, count)
    products_count.short_description = 'Productos'

@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = [
        'product', 'user', 'rating_stars', 'title', 
        'is_verified_purchase', 'created_at'
    ]
    list_filter = ['rating', 'is_verified_purchase', 'created_at']
    search_fields = ['product__name', 'user__email', 'title', 'comment']
    readonly_fields = ['created_at', 'user', 'product']
    
    def rating_stars(self, obj):
        stars = '★' * obj.rating + '☆' * (5 - obj.rating)
        return format_html(
            '<span style="color: #f39c12; font-size: 1.2em;">{}</span>',
            stars
        )
    rating_stars.short_description = 'Calificación'
    
    def has_add_permission(self, request):
        # Las reseñas solo se crean desde el frontend
        return False

@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ['product', 'name', 'full_sku', 'final_price', 'stock', 'is_active']
    list_filter = ['is_active', 'product__category', 'product__brand']
    search_fields = ['product__name', 'name', 'sku_suffix']
    list_editable = ['stock', 'is_active']
    
    def final_price(self, obj):
        return format_html('{}€', obj.final_price)
    final_price.short_description = 'Precio final'

# Registrar inline para gestión rápida de atributos
admin.site.register(ProductAttribute)

# Personalizar el título del admin
admin.site.site_header = "Suplementos Admin"
admin.site.site_title = "Suplementos Admin"
admin.site.index_title = "Gestión de Tienda"