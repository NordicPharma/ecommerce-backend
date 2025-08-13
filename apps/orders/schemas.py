from ninja import Schema, ModelSchema
from typing import List, Optional
from decimal import Decimal
from datetime import datetime
from .models import Order, OrderItem, Cart, CartItem

class OrderItemSchema(ModelSchema):
    product_name: str
    product_image: Optional[str]
    
    class Meta:
        model = OrderItem
        fields = ['id', 'product_sku', 'product_price', 'quantity', 'subtotal']

class OrderCreateSchema(Schema):
    # Dirección de envío
    shipping_name: str
    shipping_email: str
    shipping_phone: str
    shipping_address: str
    shipping_city: str
    shipping_postal_code: str
    shipping_country: str = 'ES'
    
    # Items del pedido
    items: List[dict]  # [{'product_id': 1, 'quantity': 2}, ...]

class OrderListSchema(ModelSchema):
    items_count: int
    
    class Meta:
        model = Order
        fields = ['id', 'order_number', 'status', 'total', 'created_at']

class OrderDetailSchema(ModelSchema):
    items: List[OrderItemSchema]
    payment_status: Optional[str]
    payment_method: Optional[str]
    
    class Meta:
        model = Order
        fields = '__all__'

class CartItemSchema(Schema):
    id: int
    product_id: int
    product_name: str
    product_slug: str
    product_image: Optional[str]
    product_price: Decimal
    product_stock: int
    quantity: int
    subtotal: Decimal

class CartSchema(Schema):
    items: List[CartItemSchema]
    items_count: int
    total: Decimal

class AddToCartSchema(Schema):
    product_id: int
    quantity: int = 1

class UpdateCartItemSchema(Schema):
    quantity: int