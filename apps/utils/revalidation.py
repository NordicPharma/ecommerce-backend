import httpx
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def revalidate_nextjs(path: str = None, tags: list = None):
    """
    Invalida el caché de Next.js on-demand
    
    Args:
        path: Ruta específica a revalidar (ej: '/products/whey-protein')
        tags: Lista de tags a revalidar (ej: ['products-list', 'product-123'])
    """
    if not settings.NEXTJS_URL or not settings.REVALIDATION_TOKEN:
        logger.warning("Next.js revalidation not configured")
        return False
    
    try:
        response = httpx.post(
            f"{settings.NEXTJS_URL}/api/revalidate",
            headers={
                "Authorization": f"Bearer {settings.REVALIDATION_TOKEN}"
            },
            json={
                "path": path,
                "tags": tags
            },
            timeout=5.0
        )
        
        if response.status_code == 200:
            logger.info(f"Successfully revalidated - Path: {path}, Tags: {tags}")
            return True
        else:
            logger.error(f"Revalidation failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error during revalidation: {str(e)}")
        return False

def revalidate_product(product):
    """Revalida todas las páginas relacionadas con un producto"""
    tags = [
        f"product-{product.id}",
        f"category-{product.category.slug}",
        f"brand-{product.brand.slug}",
        "products-list",
        "homepage"
    ]
    
    paths = [
        f"/products/{product.slug}",
        f"/category/{product.category.slug}",
        f"/brand/{product.brand.slug}"
    ]
    
    # Revalidar por tags
    revalidate_nextjs(tags=tags)
    
    # Revalidar paths específicos
    for path in paths:
        revalidate_nextjs(path=path)