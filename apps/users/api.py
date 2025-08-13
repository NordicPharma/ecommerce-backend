from ninja import Router
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from django.db import transaction
from ninja_jwt.tokens import RefreshToken
from .schemas import (
    UserRegisterSchema, UserLoginSchema, UserProfileSchema,
    UserUpdateSchema, ChangePasswordSchema, TokenResponseSchema
)
from apps.utils.auth import JWTAuth
from django.contrib.auth import get_user_model

User = get_user_model()
router = Router(tags=["users"])

@router.post("/register", response=TokenResponseSchema)
@transaction.atomic
def register(request, data: UserRegisterSchema):
    """Registra un nuevo usuario"""
    # Verificar si el email ya existe
    if User.objects.filter(email=data.email).exists():
        return router.create_response(
            request,
            {"detail": "El email ya está registrado"},
            status=400
        )
    
    # Crear usuario
    user = User.objects.create(
        email=data.email,
        username=data.email,  # Usar email como username
        password=make_password(data.password),
        first_name=data.first_name,
        last_name=data.last_name,
        phone=data.phone or ''
    )
    
    # Si el usuario tenía un carrito anónimo, transferirlo
    if hasattr(request, 'session') and request.session.session_key:
        from apps.orders.models import Cart
        try:
            anonymous_cart = Cart.objects.get(session_key=request.session.session_key)
            anonymous_cart.user = user
            anonymous_cart.session_key = None
            anonymous_cart.save()
        except Cart.DoesNotExist:
            pass
    
    # Generar tokens
    refresh = RefreshToken.for_user(user)
    
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': {
            **user.__dict__,
            'full_name': user.get_full_name()
        }
    }

@router.post("/login", response=TokenResponseSchema)
def login(request, data: UserLoginSchema):
    """Inicia sesión"""
    user = authenticate(username=data.email, password=data.password)
    
    if not user:
        return router.create_response(
            request,
            {"detail": "Credenciales inválidas"},
            status=401
        )
    
    # Transferir carrito anónimo si existe
    if hasattr(request, 'session') and request.session.session_key:
        from apps.orders.models import Cart, CartItem
        try:
            anonymous_cart = Cart.objects.get(session_key=request.session.session_key)
            user_cart, created = Cart.objects.get_or_create(user=user)
            
            # Transferir items
            for item in anonymous_cart.items.all():
                user_item, created = CartItem.objects.get_or_create(
                    cart=user_cart,
                    product=item.product,
                    defaults={'quantity': 0}
                )
                user_item.quantity += item.quantity
                user_item.save()
            
            # Eliminar carrito anónimo
            anonymous_cart.delete()
            
        except Cart.DoesNotExist:
            pass
    
    # Generar tokens
    refresh = RefreshToken.for_user(user)
    
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': {
            **user.__dict__,
            'full_name': user.get_full_name()
        }
    }

@router.get("/profile", auth=JWTAuth(), response=UserProfileSchema)
def get_profile(request):
    """Obtiene el perfil del usuario actual"""
    return {
        **request.auth.__dict__,
        'full_name': request.auth.get_full_name()
    }

@router.put("/profile", auth=JWTAuth(), response=UserProfileSchema)
def update_profile(request, data: UserUpdateSchema):
    """Actualiza el perfil del usuario"""
    user = request.auth
    
    for field, value in data.dict(exclude_unset=True).items():
        setattr(user, field, value)
    
    user.save()
    
    return {
        **user.__dict__,
        'full_name': user.get_full_name()
    }

@router.post("/change-password", auth=JWTAuth())
def change_password(request, data: ChangePasswordSchema):
    """Cambia la contraseña del usuario"""
    user = request.auth
    
    # Verificar contraseña actual
    if not user.check_password(data.current_password):
        return router.create_response(
            request,
            {"detail": "La contraseña actual es incorrecta"},
            status=400
        )
    
    # Cambiar contraseña
    user.set_password(data.new_password)
    user.save()
    
    return {"success": True, "message": "Contraseña actualizada correctamente"}

@router.get("/orders", auth=JWTAuth())
def get_user_orders(request):
    """Obtiene los pedidos del usuario"""
    from apps.orders.models import Order
    
    orders = Order.objects.filter(user=request.auth).values(
        'id', 'order_number', 'status', 'total', 'created_at'
    ).order_by('-created_at')
    
    return list(orders)

@router.get("/wishlist", auth=JWTAuth())
def get_wishlist(request):
    """Obtiene la lista de deseos del usuario"""
    # Implementar modelo Wishlist si lo necesitas
    return []