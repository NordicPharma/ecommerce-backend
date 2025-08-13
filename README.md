Nordic Backend — Django + Ninja

Backend de e-commerce (productos, pedidos, pagos y usuarios) hecho con Django 5 y Django Ninja (FastAPI-style para Django). Incluye JWT, caché, logging y endpoints listos para integrar con un frontend (p. ej. Next.js).

🧱 Stack
	•	Django 5 + Django Ninja (routers + Pydantic schemas)
	•	PostgreSQL (SQLite en desarrollo si no defines DB)
	•	Redis (caché; opcional)
	•	JWT con django-ninja-jwt
	•	Gunicorn (WSGI) para despliegue
	•	Celery (opcional; solo si quieres tareas en background)
	•	Docker / Docker Compose (recomendado)

📂 Estructura del proyecto (resumen)
.
├── api/               # Proyecto Django (settings, urls, wsgi/asgi)
├── apps/
│   ├── products/      # Productos, marcas, categorías, imágenes, etc.
│   ├── orders/        # Carrito, pedidos
│   ├── payments/      # Pagos (crypto u otros), wallets, webhooks
│   └── users/         # Usuario custom + endpoints de auth/perfil
├── core/              # Middleware, signals, utilidades core
├── manage.py
├── requirements.txt
├── Dockerfile
├── compose.yml
└── logs/              # access.log (middleware de acceso)

Los endpoints REST están en apps/*/api.py usando Django Ninja.
Los modelos están en apps/*/models.py con sus migraciones.

⚙️ Configuración (variables de entorno)

Copia este ejemplo a .env (no se sube a git ni se hornea en la imagen Docker):

# Django
DEBUG=1
SECRET_KEY=pon_aqui_una_clave_larga_y_secreta
ALLOWED_HOSTS=*

# Base de datos (usa Postgres en prod)
DB_NAME=supplements_db
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432
DB_SSLMODE=
DB_CONN_MAX_AGE=600

# Redis (opcional; cache y Celery si lo usas)
REDIS_URL=redis://redis:6379/0

# JWT (si usas ajustes personalizados)
# JWT_ACCESS_TTL_MINUTES=60

El proyecto usa django-environ: en settings.py se leen estas variables.
Si no defines DB, puede caer en SQLite para desarrollo.

▶️ Puesta en marcha

Opción A: Docker Compose (recomendada)
	1.	Construye e inicia:
    docker compose up --build
    2.	Ejecuta migraciones y crea superusuario:
    docker compose exec app python manage.py migrate
    docker compose exec app python manage.py createsuperuser
    3.	Entra al admin: http://localhost:8000/admin/
    Producción: el contenedor arranca con gunicorn api.wsgi:application (WSGI, no async).

    Opción B: Local (sin Docker)
    python -m venv .venv
    source .venv/bin/activate              # Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    python manage.py migrate
    python manage.py createsuperuser
    python manage.py runserver
    Si usas Postgres local, asegúrate de tenerlo corriendo y que .env apunte bien.


📚 Documentación de la API (Swagger / Redoc)

Django Ninja expone docs automáticas:
	•	Swagger: http://localhost:8000/api/docs
	•	OpenAPI JSON: http://localhost:8000/api/openapi.json

Si no las ves, revisa que en api/urls.py esté montado el NinjaAPI() y los routers.

⸻

🔐 Autenticación (JWT)

Flujo típico:
	1.	Registro
POST /api/users/register → devuelve access y refresh
	2.	Login
POST /api/users/login → devuelve access y refresh
	3.	Usar token
En cada request protegido, añade cabecera: Authorization: Bearer <access_token>

Ejemplos:

# Registro
curl -X POST http://localhost:8000/api/users/register \
  -H "Content-Type: application/json" \
  -d '{"email":"ana@ejemplo.com","password":"pass123","first_name":"Ana","last_name":"López"}'

# Login
curl -X POST http://localhost:8000/api/users/login \
  -H "Content-Type: application/json" \
  -d '{"email":"ana@ejemplo.com","password":"pass123"}'

# Perfil (protegido)
curl http://localhost:8000/api/users/profile \
  -H "Authorization: Bearer <ACCESS_TOKEN>"


🛒 Endpoints principales (breve guía)

Productos (apps/products/api.py)
	•	GET /api/products/ — listado con filtros (marca, categoría, precio, etc.)
	•	GET /api/products/{slug} — detalle
	•	GET /api/products/search/suggestions?q=creatina — sugerencias
	•	Admin (protegidos): POST /api/products/, PUT /api/products/{id}, DELETE /api/products/{id}
	•	Variantes, atributos e imágenes: ver rutas anidadas en el archivo.

Carrito y pedidos (apps/orders/api.py)
	•	GET /api/orders/cart — obtiene carrito (usuario o sesión anónima)
	•	POST /api/orders/cart/add — añade producto
	•	PUT /api/orders/cart/items/{item_id} — actualiza cantidad / borra si cantidad=0
	•	DELETE /api/orders/cart/items/{item_id} — elimina item
	•	DELETE /api/orders/cart — vacía
	•	POST /api/orders/checkout (protegido) — crea pedido desde carrito
	•	GET /api/orders/ (protegido) — lista pedidos del usuario
	•	GET /api/orders/{order_number} (protegido) — detalle
	•	PUT /api/orders/{order_id}/cancel (protegido) — cancelar pedido (si procede)

Pagos (apps/payments/api.py)
	•	POST /api/payments/initiate (protegido) — inicia pago (BTC/ETH/USDT)
	•	GET /api/payments/status/{payment_id} (protegido) — estado del pago
	•	POST /api/payments/webhook/{provider} — endpoint para notificaciones externas
	•	POST /api/payments/simulate/{payment_id} (solo en DEBUG) — simula pago confirmado

En initiate_payment se generan wallets y un QR base64. Para desarrollo puedes usar simulate si no corres Celery.

⸻

🧠 Conceptos básicos para tocar el código

1) Añadir un endpoint con Ninja

# apps/thing/api.py
from ninja import Router
from .schemas import ThingOut, ThingIn
from .models import Thing

router = Router(tags=["things"])

@router.get("/", response=list[ThingOut])
def list_things(request):
    return Thing.objects.all()

@router.post("/", response=ThingOut)
def create_thing(request, data: ThingIn):
    return Thing.objects.create(**data.dict())

Regístralo en api/urls.py:
from ninja import NinjaAPI
from apps.thing.api import router as thing_router

api = NinjaAPI()
api.add_router("/things", thing_router)
urlpatterns = [path("api/", api.urls)]

Crea/ajusta schemas con Pydantic en schemas.py.

2) Cambiar modelos
	•	Edita models.py.
	•	Crea migración: python manage.py makemigrations
	•	Aplica: python manage.py migrate

Si el modelo toca datos críticos (precio/stock), añade validaciones y tests.

3) Tests
	•	Crea tests en apps/*/tests.py (o tests/).
	•	Ejecuta: python manage.py test

⸻

🧰 Comandos útiles
# Migraciones
python manage.py makemigrations
python manage.py migrate

# Superusuario
python manage.py createsuperuser

# Cargar datos iniciales (si tienes fixtures)
python manage.py loaddata initial_data.json

# Shell interactiva
python manage.py shell_plus  # si tienes django-extensions


🧳 Logs y auditoría
	•	Middleware de acceso escribe en logs/access.log datos de cada petición (usuario, IP, latencia, etc.).
	•	Revisa core/middleware.py y core/auth_signals.py.
	•	Consejo: nunca loguees contraseñas/tokens; hay redacción de campos sensibles.

⸻

⚡️ Tareas en background (opcional)

El proyecto incluye tareas Celery (p. ej. monitorizar pagos y enviar emails).
	•	Si NO quieres async en local, puedes:
	•	Usar el endpoint POST /api/payments/simulate/{payment_id} para pruebas, o
	•	Temporalmente llamar a las funciones directamente (en vez de .delay) mientras desarrollas.
	•	Si SÍ quieres Celery:
    # Broker Redis en compose.yml
docker compose up -d redis
# Worker Celery
docker compose exec app celery -A api worker -l info
# (opcional) Beat para tareas periódicas
docker compose exec app celery -A api beat -l info


🗃️ Archivos estáticos y media
	•	MEDIA: subidas de usuarios (imágenes de productos, etc.). En desarrollo las sirve Django.
	•	STATIC: colecta con python manage.py collectstatic para producción.
En producción suele usarse WhiteNoise o un CDN; revisa STATIC_ROOT, STATIC_URL, MEDIA_ROOT, MEDIA_URL en api/settings.py.

⸻

🚀 Despliegue rápido con Docker

Dockerfile (WSGI, sin async)

Arranca Gunicorn con api.wsgi:application. Si necesitas compilar dependencias (p. ej. bitcoinlib/fastecdsa), la imagen instala build-essential en el build.

Compose (resumen esperado)
	•	Servicio app (Django + Gunicorn) en el puerto 8000
	•	Servicio redis (opcional para caché y Celery)
	•	Volúmenes para media/ si se guardan ficheros locales

Comandos típicos:
docker compose up --build
docker compose exec app python manage.py migrate
docker compose logs -f app


🛟 Troubleshooting
	•	gcc not found al instalar dependencias
Algunas libs (p. ej. fastecdsa) requieren toolchain. En Docker se soluciona instalando build-essential (ya contemplado). En Alpine: apk add gcc musl-dev gmp gmp-dev.
	•	psycopg2 no conecta
Revisa DB_HOST, DB_PORT, DB_USER, DB_PASSWORD. Si estás en Docker, DB_HOST suele ser el nombre del servicio del contenedor (p. ej. db), no localhost.
	•	Bad Request (400) en dev
Añade el host a ALLOWED_HOSTS o usa * en desarrollo.
	•	No ves Swagger
Asegúrate de montar api.urls en api/urls.py y visitar /api/docs.

⸻

✅ Checklist de “primer día”
	1.	Clona repo y crea .env a partir del ejemplo.
	2.	docker compose up --build
	3.	docker compose exec app python manage.py migrate
	4.	docker compose exec app python manage.py createsuperuser
	5.	Visita /admin y /api/docs.
	6.	Crea una marca/categoría/producto y prueba carrito → checkout → (opcional) payments/simulate.

⸻

📎 Notas para futuras mejoras
	•	Añadir rate limiting a endpoints sensibles.
	•	Separar “command bus” para pagos si se quiere prescindir de Celery.
	•	Tests de integración básicos para carrito/checkout.
	•	Servir estáticos con WhiteNoise o CDN en prod.

