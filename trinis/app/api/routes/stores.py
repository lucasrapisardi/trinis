import hashlib
import hmac as hmac_lib
import secrets
import uuid
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
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
# List stores
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

    print(f">>> redirect_uri: {redirect_uri}")

    params = {
        "client_id": settings.shopify_app_client_id,
        "scope": scopes,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    auth_url = f"https://{shop}/admin/oauth/authorize?{urlencode(params)}"

    return {"redirect_url": auth_url}


# ─────────────────────────────────────────────
# Step 2 — OAuth callback
# ─────────────────────────────────────────────

@router.get("/callback")
async def oauth_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    params = dict(request.query_params)
    code = params.get("code")
    state = params.get("state")
    shop = params.get("shop")
    hmac_param = params.get("hmac")

    print(f">>> callback params: {list(params.keys())}")

    # 1. Validate HMAC
    if hmac_param:
        if not _verify_shopify_hmac(params, hmac_param):
            raise HTTPException(status_code=403, detail="HMAC validation failed")

    # 2. Validate state
    redis = _get_redis()
    stored = await redis.get(f"oauth_state:{state}")
    if not stored:
        raise HTTPException(status_code=403, detail="Invalid or expired OAuth state")
    await redis.delete(f"oauth_state:{state}")
    await redis.aclose()

    tenant_id_str, user_id_str, expected_shop = stored.split(":", 2)
    if shop != expected_shop:
        raise HTTPException(status_code=403, detail="Shop domain mismatch")

    # 3. Exchange code for token
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

    # 5. Register webhooks
    from app.tasks.sync import register_shopify_webhooks
    register_shopify_webhooks.apply_async(args=[str(store.id)], queue="sync")

    # 6. Redirect to frontend dashboard
    return RedirectResponse(
        url=f"{settings.app_base_url}/stores?connected=1&shop={shop}"
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
# HMAC validation — Shopify spec compliant
# ─────────────────────────────────────────────

def _verify_shopify_hmac(params: dict, received_hmac: str) -> bool:
    # Remove hmac from params, sort remaining, build message
    filtered = {k: v for k, v in params.items() if k != "hmac"}
    sorted_params = "&".join(
        f"{k}={v}" for k, v in sorted(filtered.items())
    )

    digest = hmac_lib.new(
        settings.shopify_app_client_secret.encode(),
        sorted_params.encode(),
        hashlib.sha256,
    ).hexdigest()

    print(f">>> computed hmac: {digest}")
    print(f">>> received hmac: {received_hmac}")

    return hmac_lib.compare_digest(digest, received_hmac)


# ─────────────────────────────────────────────
# Manual task triggers
# ─────────────────────────────────────────────

@router.post("/{store_id}/tasks/{task_name}")
async def run_store_task(
    store_id: uuid.UUID,
    task_name: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger SKU, tags, or pricing update for entire store."""
    if task_name not in ("sku", "tags", "pricing"):
        raise HTTPException(status_code=400, detail="Invalid task. Use: sku, tags, pricing")

    result = await db.execute(
        select(ShopifyStore).where(
            ShopifyStore.id == store_id,
            ShopifyStore.tenant_id == tenant.id,
            ShopifyStore.is_active == True,
        )
    )
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    # Create a lightweight job record for tracking
    from app.models.models import Job, JobStatus
    job = Job(
        tenant_id=tenant.id,
        store_id=store.id,
        status=JobStatus.queued,
    )
    db.add(job)
    await db.flush()

    # Dispatch the appropriate task
    if task_name == "sku":
        from app.tasks.sku import generate_skus
        generate_skus.apply_async(args=[str(job.id), str(tenant.id)], queue="sync")
    elif task_name == "tags":
        from app.tasks.tags import update_tags
        update_tags.apply_async(args=[str(job.id), str(tenant.id)], queue="sync")
    elif task_name == "pricing":
        from app.tasks.pricing import update_prices
        update_prices.apply_async(args=[str(job.id), str(tenant.id)], queue="sync")

    return {"ok": True, "job_id": str(job.id), "message": f"{task_name} task queued for {store.shop_domain}"}
