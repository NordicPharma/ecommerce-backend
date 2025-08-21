from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from ninja import NinjaAPI
from ninja_extra import NinjaExtraAPI
from ninja_jwt.controller import NinjaJWTDefaultController
from django.urls import include
from apps.products.api import router as products_router
from apps.orders.api import router as orders_router
from apps.payments.api import router as payments_router
from apps.users.api import router as users_router


# Crear API principal
api = NinjaExtraAPI(
    title="Supplements Store API",
    version="1.0.0",
    description="API para tienda de suplementos deportivos"
)

# Añadir autenticación JWT
api.register_controllers(NinjaJWTDefaultController)

# Registrar routers
api.add_router("/products/", products_router)
api.add_router("/orders/", orders_router)
api.add_router("/payments/", payments_router)
api.add_router("/users/", users_router)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', api.urls),
    path('', include('django_prometheus.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
