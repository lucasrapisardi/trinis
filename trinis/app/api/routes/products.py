import time
import requests
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.auth import get_current_tenant
from app.core.encryption import decrypt_token
from app.core.config import get_settings
from app.db.session import get_db
from app.models.models import Tenant, ShopifyStore

settings = get_settings()
router = APIRouter(tags=["products"])


@router.get("/products")
async def list_products(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Fetches products from all active Shopify stores for the current tenant.
    Proxies the Shopify Admin API so the frontend doesn't need store credentials.
    """
    result = await db.execute(
        select(ShopifyStore).where(
            ShopifyStore.tenant_id == tenant.id,
            ShopifyStore.is_active == True,
        )
    )
    stores = result.scalars().all()

    all_products = []

    for store in stores:
        try:
            access_token = decrypt_token(store.encrypted_access_token)
            base_url = f"https://{store.shop_domain}/admin/api/{settings.shopify_api_version}"
            headers = {"X-Shopify-Access-Token": access_token}

            params = {"limit": 250, "status": "any"}

            while True:
                resp = requests.get(
                    f"{base_url}/products.json",
                    headers=headers,
                    params=params,
                    timeout=20,
                )
                resp.raise_for_status()
                products = resp.json().get("products", [])

                for p in products:
                    p["shop_domain"] = store.shop_domain
                    p["shopify_id"] = str(p["id"])
                    all_products.append(p)

                # Pagination
                import re
                link = resp.headers.get("Link", "")
                if 'rel="next"' not in link:
                    break
                m = re.search(r'page_info=([^&>]+)[^>]*>;\s*rel="next"', link)
                if not m:
                    break
                params = {"limit": 250, "page_info": m.group(1)}

        except Exception as e:
            print(f"⚠️ Failed to fetch products from {store.shop_domain}: {e}")
            import traceback; traceback.print_exc()
            continue

    print(f">>> products found: {len(all_products)}")
    return all_products
