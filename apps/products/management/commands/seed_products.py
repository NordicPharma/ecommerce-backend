# apps/products/management/commands/seed_products.py
import io
import random
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta, date

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.products.models import (
    Brand,
    Category,
    Product,
    ProductImage,
    ProductVariant,
    ProductAttribute,
    ProductReview,
    ProductRelated,
)

# Try to use Pillow to generar imágenes dummy
try:
    from PIL import Image

    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False


def q2(amount):
    """Redondea a 2 decimales con HALF_UP."""
    return Decimal(amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


FORMAT_CHOICES = [c[0] for c in Product.FORMAT_CHOICES]
UNIT_CHOICES = [c[0] for c in Product.UNIT_CHOICES]

BASE_PRODUCTS = [
    "Vitamina C",
    "Omega 3",
    "Magnesio",
    "Colágeno",
    "Zinc",
    "Multivitamínico",
    "Probióticos",
    "Vitamina D3",
    "B-Complex",
    "Calcio",
    "Hierro",
    "Ashwagandha",
    "Creatina",
    "Proteína WPI",
]

PRESENTATIONS = [
    ("capsule", "capsules", "60 cápsulas", 60),
    ("tablet", "tablets", "30 tabletas", 30),
    ("powder", "g", "300g", 300),
    ("liquid", "ml", "250ml", 250),
    ("gel", "g", "100g", 100),
]

ATTR_NAMES = ["Sabor", "Origen", "Lote", "Libre de gluten", "Vegano"]

VARIANT_SPECS = [
    ("Sabor Fresa", "FRESA", Decimal("0.00")),
    ("Sabor Limón", "LIMON", Decimal("0.00")),
    ("200mg", "200MG", Decimal("1.50")),
    ("500mg", "500MG", Decimal("3.00")),
]


def create_dummy_image(size=(800, 800), text="Producto"):
    """Crea una imagen PNG en memoria (si Pillow está disponible)."""
    if not PIL_AVAILABLE:
        return None
    img = Image.new("RGB", size, (230, 230, 230))
    try:
        from PIL import ImageDraw

        d = ImageDraw.Draw(img)
        d.text((20, 20), text, fill=(20, 20, 20))
    except Exception:
        pass
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio


class Command(BaseCommand):
    help = "Llena la base de datos con marcas, categorías, productos, variantes, imágenes y reseñas de prueba."

    def add_arguments(self, parser):
        parser.add_argument("--brands", type=int, default=8, help="Cantidad de marcas")
        parser.add_argument(
            "--categories",
            type=int,
            default=6,
            help="Cantidad de categorías raíz (cada una tendrá 2 hijas)",
        )
        parser.add_argument(
            "--products", type=int, default=60, help="Cantidad de productos"
        )
        parser.add_argument(
            "--variants",
            type=int,
            default=2,
            help="Variantes por producto (0-4 recomendado)",
        )
        parser.add_argument(
            "--reviews", type=int, default=2, help="Reseñas por producto"
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Borrar datos existentes antes de crear",
        )
        parser.add_argument("--no-images", action="store_true", dest="no_images",
                    help="No generar imágenes")
        parser.add_argument(
            "--seed", type=int, default=None, help="Semilla para datos reproducibles"
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts["seed"] is not None:
            random.seed(opts["seed"])

        if opts["clear"]:
            self.stdout.write("→ Limpiando datos previos…")
            ProductRelated.objects.all().delete()
            ProductImage.objects.all().delete()
            ProductVariant.objects.all().delete()
            ProductAttribute.objects.all().delete()
            ProductReview.objects.all().delete()
            Product.objects.all().delete()
            Category.objects.all().delete()
            Brand.objects.all().delete()

        # 1) Usuarios para reseñas
        User = get_user_model()
        users = list(User.objects.all()[:5])
        if not users:
            self.stdout.write("→ Creando usuarios de prueba para reseñas…")
            for i in range(1, 4):
                u, _ = User.objects.get_or_create(
                    username=f"tester{i}", defaults={"email": f"tester{i}@example.com"}
                )
                users.append(u)

        # 2) Marcas
        self.stdout.write(f"→ Creando {opts['brands']} marcas…")
        brands = []
        for i in range(opts["brands"]):
            name = f"Marca {i + 1}"
            b, _ = Brand.objects.get_or_create(
                name=name,
                defaults={
                    "description": f"Descripción de {name}",
                    "is_active": True,
                },
            )
            brands.append(b)

        # 3) Categorías (raíz + 2 hijas)
        self.stdout.write(f"→ Creando árbol de {opts['categories']} categorías…")
        categories = []
        for i in range(opts["categories"]):
            parent, _ = Category.objects.get_or_create(
                name=f"Categoría {i + 1}", defaults={"order": i, "is_active": True}
            )
            categories.append(parent)
            # 2 hijas
            for j in range(2):
                child, _ = Category.objects.get_or_create(
                    name=f"{parent.name} - Sub{j + 1}",
                    defaults={"parent": parent, "order": j, "is_active": True},
                )
                categories.append(child)

        # Tomar solo hojas para productos (hijas)
        leaf_categories = [
            c for c in categories if c.parent_id is not None
        ] or categories

        # 4) Productos
        n_products = opts["products"]
        n_variants = max(0, min(4, opts["variants"]))
        n_reviews = max(0, opts["reviews"])
        create_images = (not opts.get("no_images", False)) and PIL_AVAILABLE

        self.stdout.write(
            f"→ Creando {n_products} productos… (variantes={n_variants}, reseñas={n_reviews}, imágenes={'sí' if create_images else 'no'})"
        )
        created_products = []

        for i in range(n_products):
            base_name = random.choice(BASE_PRODUCTS)
            fmt, unit, pres_text, qty = random.choice(PRESENTATIONS)
            name = f"{base_name} {random.randint(1, 999)}"
            brand = random.choice(brands)
            category = random.choice(leaf_categories)

            price = q2(random.uniform(5, 60))
            compare_price = (
                price + q2(random.uniform(0, 15)) if random.random() < 0.4 else None
            )
            cost = q2(price * Decimal(random.uniform(0.4, 0.7)))

            stock = random.randint(0, 250)
            is_featured = random.random() < 0.15
            is_new = random.random() < 0.20

            sku = f"{brand.id:02d}-{category.id:02d}-{i + 1:05d}"

            product = Product.objects.create(
                name=name,
                sku=sku,
                brand=brand,
                category=category,
                short_description=f"Breve descripción de {name}.",
                description=f"Descripción extensa de {name}. Incluye indicaciones, composición y usos.",
                composition=f"{base_name} {random.randint(100, 1000)}mg",
                format=fmt,
                presentation=pres_text,
                unit=unit,
                quantity=qty,
                dosage=f"{random.choice([10, 50, 100, 500])}mg",
                usage_instructions="Tomar según indicación del especialista. No exceder la dosis recomendada.",
                recommended_dosage="1 a 2 veces al día después de comidas.",
                benefits="Apoya el bienestar general.",
                warnings="Mantener fuera del alcance de los niños.",
                contraindications="Consultar con un profesional si está embarazada o en lactancia.",
                side_effects="Raros; podría causar molestias estomacales.",
                storage_conditions="Conservar en lugar fresco y seco.",
                technical_info={
                    "origen": random.choice(["UE", "USA", "LatAm", "Asia"]),
                    "lote": f"L{random.randint(10000, 99999)}",
                    "libre_gluten": random.choice([True, False]),
                },
                nutritional_info={"calorías": 0, "sodio_mg": random.randint(0, 30)},
                price=price,
                compare_price=compare_price,
                cost=cost,
                stock=stock,
                low_stock_threshold=random.choice([5, 10, 20]),
                requires_prescription=random.random() < 0.05,
                batch_number=f"BATCH-{random.randint(100000, 999999)}",
                expiry_date=(
                    timezone.now().date() + timedelta(days=random.randint(180, 900))
                ),
                registration_number=f"REG-{random.randint(100000, 999999)}",
                is_active=True,
                is_featured=is_featured,
                is_new=is_new,
                meta_title=name,
                meta_description=f"Compra {name} al mejor precio.",
            )
            created_products.append(product)

            # Atributos
            for attr_name in random.sample(
                ATTR_NAMES, k=random.randint(1, min(3, len(ATTR_NAMES)))
            ):
                ProductAttribute.objects.create(
                    product=product,
                    name=attr_name,
                    value=random.choice(["Sí", "No", "N/A", "MX", "ES", "AR", "FR"]),
                )

            # Variantes
            for vname, suffix, padj in random.sample(VARIANT_SPECS, k=n_variants):
                ProductVariant.objects.create(
                    product=product,
                    name=vname,
                    sku_suffix=suffix,
                    price_adjustment=q2(padj),
                    stock=max(0, stock - random.randint(0, 20)),
                    is_active=True,
                )

            # Imágenes (si Pillow)
            if create_images:
                from django.core.files.base import ContentFile

                # Principal
                img_bytes = create_dummy_image(text=product.name)
                if img_bytes:
                    ProductImage.objects.create(
                        product=product,
                        image=ContentFile(
                            img_bytes.read(), name=f"{product.slug or product.id}_1.png"
                        ),
                        alt_text=product.name,
                        is_primary=True,
                        order=1,
                    )
                # Secundarias
                for k in range(random.randint(0, 2)):
                    img_bytes = create_dummy_image(text=f"{product.name} {k + 2}")
                    if img_bytes:
                        ProductImage.objects.create(
                            product=product,
                            image=ContentFile(
                                img_bytes.read(),
                                name=f"{product.slug or product.id}_{k + 2}.png",
                            ),
                            alt_text=f"{product.name} {k + 2}",
                            is_primary=False,
                            order=k + 2,
                        )

            # Reseñas
            for _ in range(n_reviews):
                user = random.choice(users)
                # Evitar unique_together (product, user)
                if ProductReview.objects.filter(product=product, user=user).exists():
                    continue
                ProductReview.objects.create(
                    product=product,
                    user=user,
                    rating=random.randint(3, 5),
                    title=f"Buena experiencia con {product.name}",
                    comment="Me funcionó bien. Entrega rápida.",
                    is_verified_purchase=random.random() < 0.6,
                )

        # 5) Relacionados: tomar pares dentro de misma categoría
        self.stdout.write("→ Creando relaciones de productos…")
        by_cat = {}
        for p in created_products:
            by_cat.setdefault(p.category_id, []).append(p)
        for plist in by_cat.values():
            if len(plist) < 2:
                continue
            for p in plist:
                others = [x for x in plist if x.id != p.id]
                for rel in random.sample(others, k=min(2, len(others))):
                    # Evitar duplicados
                    if ProductRelated.objects.filter(
                        product=p, related_product=rel
                    ).exists():
                        continue
                    ProductRelated.objects.create(
                        product=p,
                        related_product=rel,
                        relation_type=random.choice(["complement", "alternative"]),
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"✔ Seed completado: {len(brands)} marcas, {len(categories)} categorías, {len(created_products)} productos."
            )
        )
        if not PIL_AVAILABLE and not opts["no-images"]:
            self.stdout.write(
                self.style.WARNING(
                    "Pillow no está instalado; no se generaron imágenes. Usa '--no-images' para silenciar este aviso o instala 'Pillow'."
                )
            )
