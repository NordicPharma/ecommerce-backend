import csv
import json
import re
from decimal import Decimal
from datetime import datetime
from urllib.parse import urlparse

from django.core.management.base import BaseCommand, CommandError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils.text import slugify

from apps.products.models import (
    Brand, Category, Product, ProductAttribute,
    ProductVariant, ProductImage
)

# Choices permitidos desde el modelo
FORMAT_CHOICES = {c[0] for c in Product.FORMAT_CHOICES}
UNIT_CHOICES = {c[0] for c in Product.UNIT_CHOICES}

def to_bool(v):
    if v is None:
        return False
    s = str(v).strip().lower()
    return s in {"1","true","t","yes","y","si","sí"}

def to_decimal(v):
    if v is None or str(v).strip() == "":
        return None
    return Decimal(str(v).replace(",", ".")).quantize(Decimal("0.01"))

def to_date(v):
    if not v:
        return None
    return datetime.strptime(str(v).strip(), "%Y-%m-%d").date()

def parse_json_maybe(v):
    v = (v or "").strip()
    if not v:
        return {}
    try:
        return json.loads(v)
    except json.JSONDecodeError as e:
        raise CommandError(f"JSON inválido: {e}: {v}")

def split_semicolon(v):
    v = (v or "").strip()
    return [p.strip() for p in v.split(";") if p.strip()]

def ensure_brand(name):
    b, _ = Brand.objects.get_or_create(name=name.strip(), defaults={"description": f"{name}."})
    return b

def ensure_category_path(path):
    """
    Crea/obtiene categorías por ruta 'A/B/C'.
    Devuelve la última (la hoja).
    """
    if not path:
        raise CommandError("category_path requerido.")
    parts = re.split(r"[>/]", path)
    parent = None
    for order, raw in enumerate(p.strip() for p in parts if p.strip()):
        cat, _ = Category.objects.get_or_create(
            name=raw,
            parent=parent,
            defaults={"order": order, "is_active": True}
        )
        parent = cat
    return parent  # hoja

def download_image(url):
    import requests  # disponible en prod normalmente
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    name = slugify(urlparse(url).path.rsplit("/", 1)[-1] or "image") + ".jpg"
    return ContentFile(resp.content, name=name)

def clean_choice(value, allowed, field):
    if value not in allowed:
        raise CommandError(f"Valor inválido para {field}: '{value}'. Permitidos: {sorted(list(allowed))}")
    return value

class Command(BaseCommand):
    help = "Importa catálogo desde CSV (crea/actualiza por SKU)."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="Ruta al CSV (UTF-8/UTF-8-SIG)")
        parser.add_argument("--delimiter", default=",", help="Delimitador CSV (por defecto ,)")
        parser.add_argument("--update", action="store_true", help="Actualizar productos existentes por SKU")
        parser.add_argument("--create-missing", action="store_true", help="Crear marcas/categorías si no existen")
        parser.add_argument("--dry-run", action="store_true", help="Valida sin guardar (rollback)")
        parser.add_argument("--images-from-url", action="store_true", help="Descargar imágenes de las URLs")
        parser.add_argument("--primary-image-first", action="store_true", help="Marca la primera imagen como principal")

    def handle(self, *args, **opts):
        path = opts["file"]
        delimiter = opts["delimiter"]
        do_update = opts["update"]
        create_missing = opts["create_missing"]
        images_from_url = opts["images_from_url"]
        primary_first = opts["primary_image_first"]

        created, updated, skipped = 0, 0, 0

        self.stdout.write(f"→ Leyendo {path} …")

        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            required = {"sku","name","brand","category_path","format","presentation","unit","quantity","price","stock"}
            missing = required - set(reader.fieldnames or [])
            if missing:
                raise CommandError(f"Faltan columnas requeridas: {missing}")

            with transaction.atomic():
                savepoint = transaction.savepoint()

                for idx, row in enumerate(reader, start=2):
                    sku = (row.get("sku") or "").strip()
                    if not sku:
                        raise CommandError(f"Fila {idx}: SKU vacío.")

                    # Marca y categoría
                    brand_name = (row.get("brand") or "").strip()
                    cat_path = (row.get("category_path") or "").strip()
                    if not brand_name or not cat_path:
                        raise CommandError(f"Fila {idx} (SKU {sku}): brand y category_path son obligatorios.")

                    brand = Brand.objects.filter(name=brand_name).first()
                    if not brand:
                        if create_missing:
                            brand = ensure_brand(brand_name)
                        else:
                            raise CommandError(f"Fila {idx} (SKU {sku}): marca '{brand_name}' no existe (usa --create-missing).")

                    category = None
                    if create_missing:
                        category = ensure_category_path(cat_path)
                    else:
                        # Buscar por nombres exactos: hoja
                        parts = [p.strip() for p in re.split(r"[>/]", cat_path) if p.strip()]
                        parent = None
                        for name in parts:
                            qs = Category.objects.filter(name=name, parent=parent)
                            if not qs.exists():
                                raise CommandError(f"Fila {idx} (SKU {sku}): categoría '{cat_path}' no existe (usa --create-missing).")
                            parent = qs.first()
                        category = parent

                    # Producto existente
                    product = Product.objects.filter(sku=sku).first()
                    if product and not do_update:
                        skipped += 1
                        self.stdout.write(f"· Fila {idx} (SKU {sku}): ya existe → skip (usa --update).")
                        continue

                    # Campos básicos
                    name = (row.get("name") or "").strip()
                    fmt = clean_choice((row.get("format") or "").strip(), FORMAT_CHOICES, "format")
                    unit = clean_choice((row.get("unit") or "").strip(), UNIT_CHOICES, "unit")
                    quantity = int(row.get("quantity") or 0)
                    price = to_decimal(row.get("price"))
                    compare_price = to_decimal(row.get("compare_price"))
                    cost = to_decimal(row.get("cost"))
                    stock = int(row.get("stock") or 0)

                    # Otros campos
                    data = {
                        "short_description": (row.get("short_description") or "").strip()[:500],
                        "description": (row.get("description") or "").strip(),
                        "composition": (row.get("composition") or "").strip(),
                        "format": fmt,
                        "presentation": (row.get("presentation") or "").strip(),
                        "unit": unit,
                        "quantity": quantity,
                        "dosage": (row.get("dosage") or "").strip(),
                        "usage_instructions": (row.get("usage_instructions") or "").strip(),
                        "recommended_dosage": (row.get("recommended_dosage") or "").strip(),
                        "benefits": (row.get("benefits") or "").strip(),
                        "warnings": (row.get("warnings") or "").strip(),
                        "contraindications": (row.get("contraindications") or "").strip(),
                        "side_effects": (row.get("side_effects") or "").strip(),
                        "storage_conditions": (row.get("storage_conditions") or "").strip(),
                        "technical_info": parse_json_maybe(row.get("technical_info_json")),
                        "nutritional_info": parse_json_maybe(row.get("nutritional_info_json")),
                        "price": price,
                        "compare_price": compare_price,
                        "cost": cost,
                        "stock": stock,
                        "requires_prescription": to_bool(row.get("requires_prescription")),
                        "batch_number": (row.get("batch_number") or "").strip(),
                        "expiry_date": to_date(row.get("expiry_date")),
                        "registration_number": (row.get("registration_number") or "").strip(),
                        "is_active": True,
                        "is_featured": to_bool(row.get("is_featured")),
                        "is_new": to_bool(row.get("is_new")),
                        "meta_title": (row.get("meta_title") or "").strip()[:200],
                        "meta_description": (row.get("meta_description") or "").strip()[:320],
                    }

                    if product:
                        # UPDATE
                        product.name = name or product.name
                        product.brand = brand
                        product.category = category
                        for k, v in data.items():
                            setattr(product, k, v)
                        product.save()
                        updated += 1
                    else:
                        # CREATE
                        product = Product.objects.create(
                            sku=sku,
                            name=name,
                            brand=brand,
                            category=category,
                            **data
                        )
                        created += 1

                    # Atributos
                    for pair in split_semicolon(row.get("attributes")):
                        if ":" not in pair:
                            raise CommandError(f"Fila {idx} (SKU {sku}): atributo '{pair}' debe ser 'Nombre:Valor'.")
                        n, v = [p.strip() for p in pair.split(":", 1)]
                        if not n:
                            continue
                        ProductAttribute.objects.update_or_create(
                            product=product, name=n, defaults={"value": v}
                        )

                    # Variantes
                    for raw in split_semicolon(row.get("variants")):
                        parts = [p.strip() for p in raw.split("|")]
                        if len(parts) != 4:
                            raise CommandError(f"Fila {idx} (SKU {sku}): variante '{raw}' debe ser 'Nombre|SKU_SUFFIX|PRICE_ADJ|STOCK'.")
                        vname, suffix, padj, vstk = parts
                        ProductVariant.objects.update_or_create(
                            product=product, name=vname,
                            defaults={
                                "sku_suffix": suffix,
                                "price_adjustment": to_decimal(padj) or Decimal("0.00"),
                                "stock": int(vstk or 0),
                                "is_active": True
                            }
                        )

                    # Imágenes
                    if images_from_url:
                        urls = split_semicolon(row.get("images"))
                        for i, url in enumerate(urls, start=1):
                            try:
                                cf = download_image(url)
                            except Exception as e:
                                self.stdout.write(self.style.WARNING(f"   - No se pudo descargar imagen ({url}): {e}"))
                                continue
                            is_primary = (i == 1 and primary_first)
                            ProductImage.objects.create(
                                product=product,
                                image=cf,
                                alt_text=product.name if is_primary else f"{product.name} {i}",
                                is_primary=is_primary,
                                order=i
                            )

                if opts["dry_run"]:
                    transaction.savepoint_rollback(savepoint)
                    self.stdout.write(self.style.WARNING("DRY-RUN: Se validó el archivo pero NO se guardaron cambios."))
                else:
                    transaction.savepoint_commit(savepoint)

        self.stdout.write(self.style.SUCCESS(f"✔ Importación completada. Creados: {created} · Actualizados: {updated} · Omitidos: {skipped}"))