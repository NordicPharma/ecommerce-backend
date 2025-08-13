from django.db import models
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from decimal import Decimal
import json

User = get_user_model()

class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    logo = models.ImageField(upload_to='brands/', blank=True, null=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    class Meta:
        db_table = 'brands'
        verbose_name = 'Marca'
        verbose_name_plural = 'Marcas'
        ordering = ['name']
    
    def __str__(self):
        return self.name

class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    class Meta:
        db_table = 'categories'
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'
        ordering = ['order', 'name']
    
    def __str__(self):
        return self.name

class Product(models.Model):
    UNIT_CHOICES = [
        ('tablets', 'Tabletas'),
        ('capsules', 'Cápsulas'),
        ('ml', 'Mililitros'),
        ('g', 'Gramos'),
        ('kg', 'Kilogramos'),
        ('vials', 'Viales'),
        ('ampoules', 'Ampollas'),
        ('sachets', 'Sobres'),
        ('units', 'Unidades'),
    ]
    
    FORMAT_CHOICES = [
        ('tablet', 'Tableta'),
        ('capsule', 'Cápsula'),
        ('powder', 'Polvo'),
        ('liquid', 'Líquido'),
        ('injectable', 'Inyectable'),
        ('cream', 'Crema'),
        ('gel', 'Gel'),
        ('patch', 'Parche'),
    ]
    
    # Información básica
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    sku = models.CharField(max_length=50, unique=True)
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    
    # Descripción
    short_description = models.TextField(max_length=500)
    description = models.TextField()
    composition = models.TextField(help_text="Composición o ingredientes activos")
    
    # Presentación
    format = models.CharField(max_length=20, choices=FORMAT_CHOICES)
    presentation = models.CharField(max_length=100, help_text="Ej: 60 cápsulas, 100ml, 30 tabletas")
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES)
    quantity = models.IntegerField(help_text="Cantidad total en el envase")
    
    # Dosificación
    dosage = models.CharField(max_length=100, blank=True, help_text="Ej: 10mg, 500mg por cápsula")
    usage_instructions = models.TextField()
    recommended_dosage = models.TextField(blank=True)
    
    # Información adicional
    benefits = models.TextField(blank=True, help_text="Beneficios principales")
    warnings = models.TextField(blank=True)
    contraindications = models.TextField(blank=True)
    side_effects = models.TextField(blank=True)
    storage_conditions = models.CharField(max_length=200, blank=True)
    
    # Información técnica (campos JSON para flexibilidad)
    technical_info = models.JSONField(default=dict, blank=True, help_text="Información técnica adicional")
    nutritional_info = models.JSONField(default=dict, blank=True, help_text="Información nutricional si aplica")
    
    # Precio y stock
    price = models.DecimalField(max_digits=10, decimal_places=2)
    compare_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock = models.IntegerField(default=0)
    low_stock_threshold = models.IntegerField(default=10)
    
    # Control y regulación
    requires_prescription = models.BooleanField(default=False)
    batch_number = models.CharField(max_length=50, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    registration_number = models.CharField(max_length=50, blank=True, help_text="Número de registro sanitario")
    
    # Estado
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    is_new = models.BooleanField(default=False)
    
    # SEO
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(max_length=320, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.name}-{self.presentation}")
        super().save(*args, **kwargs)
    
    @property
    def discount_percentage(self):
        if self.compare_price and self.compare_price > self.price:
            return int(((self.compare_price - self.price) / self.compare_price) * 100)
        return 0
    
    @property
    def is_low_stock(self):
        return self.stock <= self.low_stock_threshold
    
    @property
    def price_per_unit(self):
        if self.quantity and self.quantity > 0:
            return self.price / self.quantity
        return None
    
    def get_technical_info(self):
        """Retorna la información técnica como diccionario"""
        return self.technical_info or {}
    
    def set_technical_info(self, key, value):
        """Establece un valor en la información técnica"""
        if not self.technical_info:
            self.technical_info = {}
        self.technical_info[key] = value
        self.save()
    
    class Meta:
        db_table = 'products'
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['sku']),
            models.Index(fields=['is_active', 'is_featured']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.presentation}"

class ProductAttribute(models.Model):
    """Atributos dinámicos para productos específicos"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='attributes')
    name = models.CharField(max_length=100)
    value = models.CharField(max_length=200)
    
    class Meta:
        db_table = 'product_attributes'
        unique_together = ['product', 'name']
    
    def __str__(self):
        return f"{self.name}: {self.value}"

class ProductVariant(models.Model):
    """Variantes del producto (diferentes presentaciones, sabores, etc.)"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    name = models.CharField(max_length=100, help_text="Ej: Sabor fresa, 200mg")
    sku_suffix = models.CharField(max_length=20)
    price_adjustment = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'product_variants'
        unique_together = ['product', 'name']
    
    @property
    def final_price(self):
        return self.product.price + self.price_adjustment
    
    @property
    def full_sku(self):
        return f"{self.product.sku}-{self.sku_suffix}"
    
    def __str__(self):
        return f"{self.product.name} - {self.name}"

class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/')
    alt_text = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    order = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'product_images'
        ordering = ['order']
    
    def save(self, *args, **kwargs):
        if self.is_primary:
            ProductImage.objects.filter(product=self.product, is_primary=True).update(is_primary=False)
        super().save(*args, **kwargs)

class ProductReview(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    title = models.CharField(max_length=200)
    comment = models.TextField()
    is_verified_purchase = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'product_reviews'
        unique_together = ['product', 'user']
        ordering = ['-created_at']

class ProductRelated(models.Model):
    """Productos relacionados o complementarios"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='related_from')
    related_product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='related_to')
    relation_type = models.CharField(
        max_length=20,
        choices=[
            ('complement', 'Complementario'),
            ('alternative', 'Alternativa'),
            ('bundle', 'Paquete'),
        ],
        default='complement'
    )
    
    class Meta:
        db_table = 'product_related'
        unique_together = ['product', 'related_product']