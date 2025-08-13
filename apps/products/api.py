from ninja import Router, Query, File, UploadedFile
from typing import List, Optional
from django.shortcuts import get_object_or_404
from django.db.models import Avg, Count, Q, F
from django.core.cache import cache
from .models import Product, Brand, Category, ProductImage, ProductReview, ProductVariant, ProductAttribute
from .schemas import (
    ProductListSchema, ProductDetailSchema, ProductCreateSchema, ProductUpdateSchema,
    BrandSchema, CategorySchema, ReviewCreateSchema, ReviewSchema,
    ProductFilterSchema, ProductAttributeCreateSchema, ProductVariantCreateSchema
)
from apps.utils.auth import JWTAuth
from apps.utils.revalidation import revalidate_nextjs
import json

router = Router(tags=["products"])

# Productos públicos
@router.get("/", response=List[ProductListSchema])
def list_products(request, filters: ProductFilterSchema = Query(...)):
    cache_key = f"products_list_{json.dumps(filters.dict())}"
    cached_result = cache.get(cache_key)
    
    if cached_result:
        return cached_result
    
    products = Product.objects.filter(is_active=True).select_related('brand', 'category')
    
    # Aplicar filtros
    if filters.category:
        products = products.filter(
            Q(category__slug=filters.category) | 
            Q(category__parent__slug=filters.category)
        )
    if filters.brand:
        products = products.filter(brand__slug=filters.brand)
    if filters.search:
        products = products.filter(
            Q(name__icontains=filters.search) | 
            Q(description__icontains=filters.search) |
            Q(composition__icontains=filters.search) |
            Q(brand__name__icontains=filters.search)
        )
    if filters.min_price:
        products = products.filter(price__gte=filters.min_price)
    if filters.max_price:
        products = products.filter(price__lte=filters.max_price)
    if filters.format:
        products = products.filter(format=filters.format)
    if filters.is_featured is not None:
        products = products.filter(is_featured=filters.is_featured)
    if filters.is_new is not None:
        products = products.filter(is_new=filters.is_new)
    if filters.in_stock:
        products = products.filter(stock__gt=0)
    if filters.requires_prescription is not None:
        products = products.filter(requires_prescription=filters.requires_prescription)
    
    # Ordenamiento
    if filters.ordering == 'price':
        products = products.order_by('price')
    elif filters.ordering == '-price':
        products = products.order_by('-price')
    elif filters.ordering == 'name':
        products = products.order_by('name')
    else:
        products = products.order_by(filters.ordering)
    
    # Añadir anotaciones
    products = products.annotate(
        rating=Avg('reviews__rating'),
        reviews_count=Count('reviews')
    )
    
    # Paginar
    products = products[filters.offset:filters.offset + filters.limit]
    
    # Transformar para incluir imagen principal
    result = []
    for product in products:
        primary_image = product.images.filter(is_primary=True).first()
        result.append({
            'id': product.id,
            'name': product.name,
            'slug': product.slug,
            'price': product.price,
            'compare_price': product.compare_price,
            'presentation': product.presentation,
            'format': product.format,
            'brand': product.brand.name,
            'category': product.category.name,
            'primary_image': primary_image.image.url if primary_image else None,
            'discount_percentage': product.discount_percentage,
            'is_low_stock': product.is_low_stock,
            'is_new': product.is_new,
            'rating': product.rating,
            'stock': product.stock
        })
    
    # Cachear por 5 minutos
    cache.set(cache_key, result, 300)
    
    return result

@router.get("/{slug}", response=ProductDetailSchema)
def get_product(request, slug: str):
    product = get_object_or_404(
        Product.objects.annotate(
            rating=Avg('reviews__rating'),
            reviews_count=Count('reviews')
        ).prefetch_related(
            'images', 'attributes', 'variants', 'reviews'
        ),
        slug=slug,
        is_active=True
    )
    return product

@router.get("/search/suggestions")
def search_suggestions(request, q: str):
    """Sugerencias de búsqueda para autocompletado"""
    if len(q) < 2:
        return []
    
    # Buscar en productos
    products = Product.objects.filter(
        Q(name__icontains=q) | Q(brand__name__icontains=q),
        is_active=True
    ).values('name', 'slug')[:5]
    
    # Buscar en categorías
    categories = Category.objects.filter(
        name__icontains=q,
        is_active=True
    ).values('name', 'slug')[:3]
    
    # Buscar en marcas
    brands = Brand.objects.filter(
        name__icontains=q,
        is_active=True
    ).values('name', 'slug')[:3]
    
    return {
        'products': list(products),
        'categories': list(categories),
        'brands': list(brands)
    }

# Admin endpoints (requieren autenticación)
@router.post("/", auth=JWTAuth(), response=ProductDetailSchema)
def create_product(request, data: ProductCreateSchema):
    product_dict = data.dict()
    brand_id = product_dict.pop('brand_id')
    category_id = product_dict.pop('category_id')
    technical_info = product_dict.pop('technical_info', {})
    nutritional_info = product_dict.pop('nutritional_info', {})
    
    product = Product.objects.create(
        brand_id=brand_id,
        category_id=category_id,
        technical_info=technical_info,
        nutritional_info=nutritional_info,
        **product_dict
    )
    
    # Revalidar caché de Next.js
    revalidate_nextjs(tags=['products-list', f'category-{product.category.slug}'])
    
    return product

@router.put("/{product_id}", auth=JWTAuth(), response=ProductDetailSchema)
def update_product(request, product_id: int, data: ProductUpdateSchema):
    product = get_object_or_404(Product, id=product_id)
    
    for attr, value in data.dict(exclude_unset=True).items():
        setattr(product, attr, value)
    
    product.save()
    
    # Limpiar caché
    cache.delete_pattern(f"products_list_*")
    
    # Revalidar Next.js
    revalidate_nextjs(
        path=f"/products/{product.slug}",
        tags=[f'product-{product.id}', 'products-list']
    )
    
    return product

@router.delete("/{product_id}", auth=JWTAuth())
def delete_product(request, product_id: int):
    product = get_object_or_404(Product, id=product_id)
    product.is_active = False
    product.save()
    
    # Limpiar caché y revalidar
    cache.delete_pattern(f"products_list_*")
    revalidate_nextjs(tags=['products-list'])
    
    return {"success": True}

# Gestión de variantes
@router.post("/{product_id}/variants", auth=JWTAuth())
def create_variant(request, product_id: int, data: ProductVariantCreateSchema):
    product = get_object_or_404(Product, id=product_id)
    
    variant = ProductVariant.objects.create(
        product=product,
        **data.dict()
    )
    
    revalidate_nextjs(path=f"/products/{product.slug}")
    
    return {"id": variant.id, "name": variant.name, "full_sku": variant.full_sku}

@router.put("/variants/{variant_id}", auth=JWTAuth())
def update_variant(request, variant_id: int, data: ProductVariantCreateSchema):
    variant = get_object_or_404(ProductVariant, id=variant_id)
    
    for attr, value in data.dict(exclude_unset=True).items():
        setattr(variant, attr, value)
    
    variant.save()
    
    revalidate_nextjs(path=f"/products/{variant.product.slug}")
    
    return {"success": True}

# Gestión de atributos
@router.post("/{product_id}/attributes", auth=JWTAuth())
def add_attribute(request, product_id: int, data: ProductAttributeCreateSchema):
    product = get_object_or_404(Product, id=product_id)
    
    attribute, created = ProductAttribute.objects.update_or_create(
        product=product,
        name=data.name,
        defaults={'value': data.value}
    )
    
    revalidate_nextjs(path=f"/products/{product.slug}")
    
    return {"id": attribute.id, "created": created}

# Imágenes
@router.post("/{product_id}/images", auth=JWTAuth())
def upload_product_image(
    request,
    product_id: int,
    image: UploadedFile = File(...),
    alt_text: str = "",
    is_primary: bool = False
):
    product = get_object_or_404(Product, id=product_id)
    
    # Obtener el orden más alto actual
    max_order = product.images.aggregate(max_order=models.Max('order'))['max_order'] or 0
    
    product_image = ProductImage.objects.create(
        product=product,
        image=image,
        alt_text=alt_text,
        is_primary=is_primary,
        order=max_order + 1
    )
    
    # Revalidar producto
    revalidate_nextjs(
        path=f"/products/{product.slug}",
        tags=[f'product-{product.id}']
    )
    
    return {"id": product_image.id, "url": product_image.image.url}

@router.delete("/images/{image_id}", auth=JWTAuth())
def delete_product_image(request, image_id: int):
    image = get_object_or_404(ProductImage, id=image_id)
    product_slug = image.product.slug
    image.delete()
    
    revalidate_nextjs(path=f"/products/{product_slug}")
    
    return {"success": True}

# Marcas
@router.get("/brands/", response=List[BrandSchema])
def list_brands(request):
    return Brand.objects.filter(is_active=True).annotate(
        products_count=Count('products')
    ).order_by('name')

@router.get("/brands/{slug}")
def get_brand(request, slug: str):
    brand = get_object_or_404(Brand, slug=slug, is_active=True)
    products_count = brand.products.filter(is_active=True).count()
    
    return {
        **brand.__dict__,
        'products_count': products_count
    }

# Categorías
@router.get("/categories/", response=List[CategorySchema])
def list_categories(request, parent: Optional[str] = None):
    categories = Category.objects.filter(is_active=True)
    
    if parent:
        parent_cat = get_object_or_404(Category, slug=parent)
        categories = categories.filter(parent=parent_cat)
    else:
        categories = categories.filter(parent=None)
    
    return categories.annotate(
        products_count=Count('products')
    ).order_by('order', 'name')

@router.get("/categories/tree")
def categories_tree(request):
    """Devuelve el árbol completo de categorías"""
    def build_tree(parent=None):
        categories = []
        for cat in Category.objects.filter(parent=parent, is_active=True).order_by('order', 'name'):
            categories.append({
                'id': cat.id,
                'name': cat.name,
                'slug': cat.slug,
                'children': build_tree(cat)
            })
        return categories
    
    return build_tree()

# Reviews
@router.get("/{product_id}/reviews", response=List[ReviewSchema])
def list_reviews(request, product_id: int, limit: int = 10, offset: int = 0):
    reviews = ProductReview.objects.filter(
        product_id=product_id
    ).select_related('user')[offset:offset + limit]
    
    return [
        {
            **review.__dict__,
            'user_name': review.user.get_full_name() or review.user.username
        }
        for review in reviews
    ]

@router.post("/{product_id}/reviews", auth=JWTAuth(), response=ReviewSchema)
def create_review(request, product_id: int, data: ReviewCreateSchema):
    product = get_object_or_404(Product, id=product_id)
    
    # Verificar si ya existe una reseña
    if ProductReview.objects.filter(product=product, user=request.auth).exists():
        return router.create_response(
            request,
            {"detail": "Ya has reseñado este producto"},
            status=400
        )
    
    review = ProductReview.objects.create(
        product=product,
        user=request.auth,
        **data.dict()
    )
    
    # Verificar si es compra verificada
    from apps.orders.models import Order
    has_purchased = Order.objects.filter(
        user=request.auth,
        items__product=product,
        status__in=['delivered', 'completed']
    ).exists()
    
    if has_purchased:
        review.is_verified_purchase = True
        review.save()
    
    # Limpiar caché y revalidar
    cache.delete(f"product_detail_{product.slug}")
    revalidate_nextjs(
        path=f"/products/{product.slug}",
        tags=[f'product-{product.id}']
    )
    
    return {
        **review.__dict__,
        'user_name': request.auth.get_full_name() or request.auth.username
    }

# Productos relacionados
@router.get("/{product_id}/related")
def get_related_products(request, product_id: int):
    product = get_object_or_404(Product, id=product_id)
    
    # Productos relacionados directamente
    related_ids = product.related_from.values_list('related_product_id', flat=True)
    
    # Si no hay productos relacionados, buscar por categoría
    if not related_ids:
        related_products = Product.objects.filter(
            category=product.category,
            is_active=True
        ).exclude(id=product.id)[:6]
    else:
        related_products = Product.objects.filter(
            id__in=related_ids,
            is_active=True
        )
    
    # Transformar para respuesta
    result = []
    for p in related_products:
        primary_image = p.images.filter(is_primary=True).first()
        result.append({
            'id': p.id,
            'name': p.name,
            'slug': p.slug,
            'price': p.price,
            'presentation': p.presentation,
            'primary_image': primary_image.image.url if primary_image else None
        })
    
    return result