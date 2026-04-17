import hashlib
import hmac
import secrets
import uuid
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as aioredis

from app.core.auth import get_current_user, get_current_tenant
from app.core.config import get_settings
from app.core.encryption import encrypt_token
from app.db.session import get_db
from app.models.models import User, Tenant, ShopifyStore
from app.schemas.schemas import StoreOut

settings = get_settings()
router = APIRouter(prefix="/stores", tags=["stores"])


def _get_redis():
    return aioredis.from_url(settings.redis_url, decode_responses=True)


# ─────────────────────────────────────────────
# List stores for current tenant
# ─────────────────────────────────────────────

@router.get("", response_model=list[StoreOut])
async def list_stores(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ShopifyStore).where(ShopifyStore.tenant_id == tenant.id)
    )
    return result.scalars().all()


# ─────────────────────────────────────────────
# Step 1 — Initiate OAuth
# POST /stores/connect  body: { shop_domain: "acme.myshopify.com" }
# ─────────────────────────────────────────────

@router.post("/connect")
async def initiate_oauth(
    shop_domain: str,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
):
    shop = shop_domain.lower().strip()
    if not shop.endswith(".myshopify.com"):
        shop = f"{shop}.myshopify.com"

    # Generate state and store in Redis (TTL 10 min)
    state = secrets.token_urlsafe(32)
    redis = _get_redis()
    await redis.setex(
        f"oauth_state:{state}",
        600,
        f"{tenant.id}:{current_user.id}:{shop}",
    )
    await redis.aclose()

    scopes = "read_products,write_products,read_inventory"
    redirect_uri = settings.shopify_callback_url or f"{settings.app_base_url}/api/stores/callback"

    params = {
        "client_id": settings.shopify_app_client_id,
        "scope": scopes,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    auth_url = f"https://{shop}/admin/oauth/authorize?{urlencode(params)}"

    redirect_uri = settings.shopify_callback_url or f"{settings.app_base_url}/api/stores/callback"
    print(f">>> redirect_uri being sent to Shopify: {redirect_uri}")

    return {"redirect_url": auth_url}


# ─────────────────────────────────────────────
# Step 2 — OAuth callback (Shopify redirects here)
# GET /stores/callback?code=...&state=...&shop=...
# ─────────────────────────────────────────────

@router.get("/callback")
async def oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    shop: str = Query(...),
    hmac_param: str = Query(None, alias="hmac"),
    db: AsyncSession = Depends(get_db),
):
    # 1. Validate HMAC from Shopify
    if hmac_param:
        _verify_shopify_hmac(shop, state, code, hmac_param)

    # 2. Validate state from Redis
    redis = _get_redis()
    stored = await redis.get(f"oauth_state:{state}")
    if not stored:
        raise HTTPException(status_code=403, detail="Invalid or expired OAuth state")
    await redis.delete(f"oauth_state:{state}")
    await redis.aclose()

    tenant_id_str, user_id_str, expected_shop = stored.split(":", 2)
    if shop != expected_shop:
        raise HTTPException(status_code=403, detail="Shop domain mismatch")

    # 3. Exchange code for permanent access token
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://{shop}/admin/oauth/access_token",
            json={
                "client_id": settings.shopify_app_client_id,
                "client_secret": settings.shopify_app_client_secret,
                "code": code,
            },
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to exchange OAuth code")
        token_data = resp.json()

    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=502, detail="No access token in response")

    # 4. Encrypt and persist
    encrypted = encrypt_token(access_token)
    tenant_id = uuid.UUID(tenant_id_str)

    existing = await db.execute(
        select(ShopifyStore).where(ShopifyStore.shop_domain == shop)
    )
    store = existing.scalar_one_or_none()

    if store:
        store.encrypted_access_token = encrypted
        store.is_active = True
        store.webhooks_registered = False
    else:
        store = ShopifyStore(
            tenant_id=tenant_id,
            shop_domain=shop,
            encrypted_access_token=encrypted,
        )
        db.add(store)

    await db.flush()

    # 5. Register webhooks (fire-and-forget via Celery)
    from app.tasks.sync import register_shopify_webhooks
    register_shopify_webhooks.apply_async(args=[str(store.id)], queue="sync")

    # 6. Redirect to dashboard
    return RedirectResponse(
        url=f"{settings.app_base_url}/dashboard?connected=1&shop={shop}"
    )


# ─────────────────────────────────────────────
# Disconnect a store
# ─────────────────────────────────────────────

@router.delete("/{store_id}")
async def disconnect_store(
    store_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ShopifyStore).where(
            ShopifyStore.id == store_id,
            ShopifyStore.tenant_id == tenant.id,
        )
    )
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    store.is_active = False
    return {"ok": True}


# ─────────────────────────────────────────────
# HMAC validation helper
# ─────────────────────────────────────────────

def _verify_shopify_hmac(shop: str, state: str, code: str, received_hmac: str):
    message = f"code={code}&shop={shop}&state={state}"
    digest = hmac.new(
        settings.shopify_app_client_secret.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(digest, received_hmac):
        raise HTTPException(status_code=403, detail="HMAC validation failed")
