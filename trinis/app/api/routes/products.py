# PATH: /home/lumoura/trinis_ai/trinis/app/api/routes/products.py
"""
Products route — fetches products from all active Shopify stores for the tenant.
"""
import re

import requests
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.auth import get_current_user, get_current_tenant
from app.core.config import get_settings
from app.core.encryption import decrypt_token
from app.db.session import get_db
from app.models.models import ShopifyStore, Tenant, User

router = APIRouter(prefix="/products", tags=["products"])
settings = get_settings()


@router.get("")
async def list_products(
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetches products from all active Shopify stores for the current tenant."""
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
            params = {"limit": 250}

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

                # Pagination via Link header
                link = resp.headers.get("Link", "")
                if 'rel="next"' not in link:
                    break

                next_url = re.search(r'<([^>]+)>;\s*rel="next"', link)
                if not next_url:
                    break
                params = {"page_info": next_url.group(1).split("page_info=")[-1], "limit": 250}

        except Exception as e:
            print(f"⚠️ Failed to fetch products from {store.shop_domain}: {e}")

    print(f">>> products found: {len(all_products)}")
    return all_products
