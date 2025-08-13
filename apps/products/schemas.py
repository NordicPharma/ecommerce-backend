from ninja import Schema, ModelSchema
from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import datetime, date
from .models import Product, Brand, Category, ProductImage, ProductReview, ProductVariant, ProductAttribute

class BrandSchema(ModelSchema):
    class Meta:
        model = Brand
        fields = ['id', 'name', 'slug', 'logo', 'description']

class CategorySchema(ModelSchema):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'image']

class ProductImageSchema(ModelSchema):
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'alt_text', 'is_primary', 'order']

class ProductAttributeSchema(ModelSchema):
    class Meta:
        model = ProductAttribute
        fields = ['name', 'value']

class ProductVariantSchema(ModelSchema):
    final_price: Decimal
    full_sku: str
    
    class Meta:
        model = ProductVariant
        fields = ['id', 'name', 'sku_suffix', 'price_adjustment', 'stock', 'is_active']

class ProductListSchema(Schema):
    id: int
    name: str
    slug: str
    price: Decimal
    compare_price: Optional[Decimal]
    presentation: str
    format: str
    brand: str
    category: str
    primary_image: Optional[str]
    discount_percentage: int
    is_low_stock: bool
    is_new: bool
    rating: Optional[float]
    stock: int

class ProductDetailSchema(ModelSchema):
    brand: BrandSchema
    category: CategorySchema
    images: List[ProductImageSchema]
    attributes: List[ProductAttributeSchema]
    variants: List[ProductVariantSchema]
    discount_percentage: int
    is_low_stock: bool
    price_per_unit: Decimal
    rating: Optional[float]
    reviews_count: int
    technical_info: Dict[str, Any]
    nutritional_info: Dict[str, Any]
    
    class Meta:
        model = Product
        fields = '__all__'

class ProductCreateSchema(Schema):
    name: str
    sku: str
    brand_id: int
    category_id: int
    short_description: str
    description: str
    composition: str
    format: str
    presentation: str
    unit: str
    quantity: int
    dosage: Optional[str]
    usage_instructions: str
    recommended_dosage: Optional[str]
    benefits: Optional[str]
    warnings: Optional[str]
    contraindications: Optional[str]
    side_effects: Optional[str]
    storage_conditions: Optional[str]
    price: Decimal
    compare_price: Optional[Decimal]
    cost: Optional[Decimal]
    stock: int
    requires_prescription: bool = False
    batch_number: Optional[str]
    expiry_date: Optional[date]
    registration_number: Optional[str]
    is_featured: bool = False
    is_new: bool = False
    meta_title: Optional[str]
    meta_description: Optional[str]
    technical_info: Optional[Dict[str, Any]]
    nutritional_info: Optional[Dict[str, Any]]

class ProductUpdateSchema(Schema):
    name: Optional[str]
    short_description: Optional[str]
    description: Optional[str]
    composition: Optional[str]
    usage_instructions: Optional[str]
    recommended_dosage: Optional[str]
    benefits: Optional[str]
    warnings: Optional[str]
    contraindications: Optional[str]
    side_effects: Optional[str]
    storage_conditions: Optional[str]
    price: Optional[Decimal]
    compare_price: Optional[Decimal]
    stock: Optional[int]
    is_active: Optional[bool]
    is_featured: Optional[bool]
    is_new: Optional[bool]
    meta_title: Optional[str]
    meta_description: Optional[str]

class ProductAttributeCreateSchema(Schema):
    name: str
    value: str

class ProductVariantCreateSchema(Schema):
    name: str
    sku_suffix: str
    price_adjustment: Decimal = Decimal('0.00')
    stock: int

class ReviewCreateSchema(Schema):
    rating: int
    title: str
    comment: str

class ReviewSchema(ModelSchema):
    user_name: str
    
    class Meta:
        model = ProductReview
        fields = ['id', 'rating', 'title', 'comment', 'is_verified_purchase', 'created_at']

class ProductFilterSchema(Schema):
    category: Optional[str]
    brand: Optional[str]
    search: Optional[str]
    min_price: Optional[float]
    max_price: Optional[float]
    format: Optional[str]
    is_featured: Optional[bool]
    is_new: Optional[bool]
    in_stock: Optional[bool]
    requires_prescription: Optional[bool]
    ordering: str = "-created_at"
    limit: int = 20
    offset: int = 0