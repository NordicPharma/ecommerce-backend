from ninja import Router
from typing import List
from django.shortcuts import get_object_or_404
from django.db import transaction
from decimal import Decimal
from .models import Order, OrderItem, Cart, CartItem
from .schemas import (
    OrderCreateSchema, OrderListSchema, OrderDetailSchema,
    CartSchema, AddToCartSchema, UpdateCartItemSchema
)
from apps.products.models import Product
from apps.utils.auth import JWTAuth
from apps.utils.revalidation import revalidate_nextjs

router = Router(tags=["orders"])

# Carrito de compras
@router.get("/cart", response=CartSchema)
def get_cart(request):
    """Obtiene el carrito del usuario actual"""
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        cart, created = Cart.objects.get_or_create(session_key=session_key)
    
    items = []
    for item in cart.items.select_related('product').all():
        product = item.product
        primary_image = product.images.filter(is_primary=True).first()
        
        items.append({
            'id': item.id,
            'product_id': product.id,
            'product_name': product.name,
            'product_slug': product.slug,
            'product_image': primary_image.image.url if primary_image else None,
            'product_price': product.price,
            'product_stock': product.stock,
            'quantity': item.quantity,
            'subtotal': item.subtotal
        })
    
    return {
        'items': items,
        'items_count': cart.items_count,
        'total': cart.total
    }

@router.post("/cart/add", response=CartSchema)
def add_to_cart(request, data: AddToCartSchema):
    """Añade un producto al carrito"""
    product = get_object_or_404(Product, id=data.product_id, is_active=True)
    
    # Verificar stock
    if product.stock < data.quantity:
        return router.create_response(
            request,
            {"detail": "Stock insuficiente"},
            status=400
        )
    
    # Obtener o crear carrito
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        cart, created = Cart.objects.get_or_create(session_key=session_key)
    
    # Añadir o actualizar item
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={'quantity': data.quantity}
    )
    
    if not created:
        cart_item.quantity += data.quantity
        cart_item.save()
    
    return get_cart(request)

@router.put("/cart/items/{item_id}", response=CartSchema)
def update_cart_item(request, item_id: int, data: UpdateCartItemSchema):
    """Actualiza la cantidad de un item del carrito"""
    # Obtener carrito del usuario
    if request.user.is_authenticated:
        cart = get_object_or_404(Cart, user=request.user)
    else:
        session_key = request.session.session_key
        cart = get_object_or_404(Cart, session_key=session_key)
    
    cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
    
    # Verificar stock
    if cart_item.product.stock < data.quantity:
        return router.create_response(
            request,
            {"detail": "Stock insuficiente"},
            status=400
        )
    
    if data.quantity == 0:
        cart_item.delete()
    else:
        cart_item.quantity = data.quantity
        cart_item.save()
    
    return get_cart(request)

@router.delete("/cart/items/{item_id}", response=CartSchema)
def remove_from_cart(request, item_id: int):
    """Elimina un item del carrito"""
    if request.user.is_authenticated:
        cart = get_object_or_404(Cart, user=request.user)
    else:
        session_key = request.session.session_key
        cart = get_object_or_404(Cart, session_key=session_key)
    
    cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
    cart_item.delete()
    
    return get_cart(request)

@router.delete("/cart", response=dict)
def clear_cart(request):
    """Vacía el carrito"""
    if request.user.is_authenticated:
        cart = get_object_or_404(Cart, user=request.user)
    else:
        session_key = request.session.session_key
        cart = get_object_or_404(Cart, session_key=session_key)
    
    cart.items.all().delete()
    return {"success": True}

# Pedidos (requieren autenticación)
@router.get("/", auth=JWTAuth(), response=List[OrderListSchema])
def list_orders(request):
    """Lista los pedidos del usuario"""
    orders = Order.objects.filter(user=request.auth).annotate(
        items_count=models.Count('items')
    )
    return orders

@router.get("/{order_number}", auth=JWTAuth(), response=OrderDetailSchema)
def get_order(request, order_number: str):
    """Obtiene el detalle de un pedido"""
    order = get_object_or_404(
        Order.objects.prefetch_related('items__product'),
        order_number=order_number,
        user=request.auth
    )
    
    # Añadir información de pago si existe
    payment_data = {}
    if hasattr(order, 'payment'):
        payment_data = {
            'payment_status': order.payment.status,
            'payment_method': order.payment.payment_method
        }
    
    # Añadir imágenes a los items
    items_data = []
    for item in order.items.all():
        primary_image = item.product.images.filter(is_primary=True).first()
        items_data.append({
            **item.__dict__,
            'product_name': item.product.name,
            'product_image': primary_image.image.url if primary_image else None
        })
    
    return {
        **order.__dict__,
        **payment_data,
        'items': items_data
    }

@router.post("/checkout", auth=JWTAuth(), response=OrderDetailSchema)
@transaction.atomic
def create_order(request, data: OrderCreateSchema):
    """Crea un pedido desde el carrito"""
    # Obtener carrito del usuario
    cart = get_object_or_404(Cart, user=request.auth)
    
    if not cart.items.exists():
        return router.create_response(
            request,
            {"detail": "El carrito está vacío"},
            status=400
        )
    
    # Calcular totales
    subtotal = Decimal('0.00')
    items_data = []
    
    for cart_item in cart.items.select_related('product'):
        product = cart_item.product
        
        # Verificar stock nuevamente
        if product.stock < cart_item.quantity:
            return router.create_response(
                request,
                {"detail": f"Stock insuficiente para {product.name}"},
                status=400
            )
        
        subtotal += cart_item.subtotal
        items_data.append({
            'product': product,
            'quantity': cart_item.quantity,
            'product_price': product.price
        })
    
    # Calcular envío e impuestos
    shipping_cost = Decimal('0.00') if subtotal >= 50 else Decimal('4.95')
    tax_rate = Decimal('0.21')  # 21% IVA en España
    tax_amount = (subtotal + shipping_cost) * tax_rate
    total = subtotal + shipping_cost + tax_amount
    
    # Crear orden
    order = Order.objects.create(
        user=request.auth,
        **data.dict(),
        subtotal=subtotal,
        shipping_cost=shipping_cost,
        tax_amount=tax_amount,
        total=total
    )
    
    # Crear items del pedido y actualizar stock
    for item_data in items_data:
        product = item_data['product']
        
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            product_sku=product.sku,
            product_price=item_data['product_price'],
            quantity=item_data['quantity']
        )
        
        # Actualizar stock
        product.stock -= item_data['quantity']
        product.save()
        
        # Revalidar página del producto
        revalidate_nextjs(
            path=f"/products/{product.slug}",
            tags=[f"product-{product.id}"]
        )
    
    # Limpiar carrito
    cart.items.all().delete()
    
    return get_order(request, order.order_number)

@router.put("/{order_id}/cancel", auth=JWTAuth())
def cancel_order(request, order_id: int):
    """Cancela un pedido"""
    order = get_object_or_404(Order, id=order_id, user=request.auth)
    
    if order.status not in ['pending', 'processing']:
        return router.create_response(
            request,
            {"detail": "No se puede cancelar este pedido"},
            status=400
        )
    
    # Restaurar stock
    for item in order.items.all():
        item.product.stock += item.quantity
        item.product.save()
        
        # Revalidar producto
        revalidate_nextjs(
            path=f"/products/{item.product.slug}",
            tags=[f"product-{item.product.id}"]
        )
    
    order.status = 'cancelled'
    order.save()
    
    return {"success": True, "status": order.status}