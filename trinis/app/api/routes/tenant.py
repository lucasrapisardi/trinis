import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.auth import get_current_tenant, get_current_user
from app.db.session import get_db
from app.models.models import Tenant, VendorConfig
from app.schemas.schemas import TenantOut, VendorConfigCreate, VendorConfigOut

router = APIRouter(tags=["tenant"])


# ── Tenant ────────────────────────────────────────────────────────────────

@router.get("/tenant", response_model=TenantOut)
async def get_tenant(tenant: Tenant = Depends(get_current_tenant)):
    return {
        **tenant.__dict__,
        "plan_limit": tenant.plan_limit,
        "user_limit": tenant.user_limit,
    }


# ── Vendor configs ────────────────────────────────────────────────────────

@router.get("/vendors", response_model=list[VendorConfigOut])
async def list_vendors(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(VendorConfig).where(VendorConfig.tenant_id == tenant.id)
    )
    return result.scalars().all()


@router.post("/vendors", response_model=VendorConfigOut, status_code=201)
async def create_vendor(
    payload: VendorConfigCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    vendor = VendorConfig(**payload.model_dump(), tenant_id=tenant.id)
    db.add(vendor)
    await db.flush()
    return vendor


@router.put("/vendors/{vendor_id}", response_model=VendorConfigOut)
async def update_vendor(
    vendor_id: uuid.UUID,
    payload: VendorConfigCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(VendorConfig).where(
            VendorConfig.id == vendor_id,
            VendorConfig.tenant_id == tenant.id,
        )
    )
    vendor = result.scalar_one_or_none()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor config not found")

    for k, v in payload.model_dump().items():
        setattr(vendor, k, v)

    return vendor


@router.delete("/vendors/{vendor_id}", status_code=204)
async def delete_vendor(
    vendor_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(VendorConfig).where(
            VendorConfig.id == vendor_id,
            VendorConfig.tenant_id == tenant.id,
        )
    )
    vendor = result.scalar_one_or_none()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor config not found")

    await db.delete(vendor)



# ── Vendor scrape preview ─────────────────────────────────────────────────────
@router.post("/vendors/preview")
async def preview_vendor_scrape(
    payload: dict,
    tenant: Tenant = Depends(get_current_tenant),
    current_user = Depends(get_current_user),
):
    """
    Test-scrape up to 3 products from a vendor URL before saving the config.
    Uses the generic AI scraper for unknown sites, or the dedicated adapter for known ones.
    """
    from urllib.parse import urlparse
    from app.tasks.scrape_generic import extract_product_links, extract_product_detail

    url = payload.get("base_url", "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="base_url is required")

    try:
        # Detect scraper type
        domain = urlparse(url).netloc.lower()
        if "comercialgomes" in domain:
            return {"scraper_type": "comercial_gomes", "products": [], "message": "Dedicated adapter will be used for Comercial Gomes."}

        # Check for VTEX
        from app.tasks.scrape_vtex import is_vtex, fetch_vtex_products
        if is_vtex(url):
            products = fetch_vtex_products(url, limit=3)
            return {
                "scraper_type": "vtex",
                "products": [{"title": p["nome"], "price": p["preco"], "ean": p["ean"], "image_url": p["imagem_url"], "url": p["link"]} for p in products],
                "message": f"VTEX store detected. Showing {len(products)} products.",
            }

        # Generic AI scrape — limit to 3 products
        links = extract_product_links(url)
        if not links:
            return {"scraper_type": "auto", "products": [], "message": "No product links found on this page."}

        previews = []
        for item in links[:3]:
            detail = extract_product_detail(item.get("url", ""))
            if detail:
                previews.append({
                    "title": detail.get("title") or item.get("title", ""),
                    "price": detail.get("price", 0),
                    "ean": detail.get("ean", ""),
                    "image_url": detail.get("image_url", ""),
                    "url": item.get("url", ""),
                })

        return {
            "scraper_type": "auto",
            "products": previews,
            "message": f"Found {len(links)} products. Showing first {len(previews)}.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview failed: {str(e)}")

# ── Cancel account ────────────────────────────────────────────────────────────

@router.post("/tenant/cancel")
async def cancel_account(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Cancels the tenant account — deactivates all stores and marks tenant as cancelled.
    Data is retained for 30 days before permanent deletion.
    """
    from app.models.models import ShopifyStore
    from sqlalchemy import update

    # Deactivate all stores
    await db.execute(
        update(ShopifyStore)
        .where(ShopifyStore.tenant_id == tenant.id)
        .values(is_active=False)
    )

    # Mark tenant as cancelled
    tenant.plan = "cancelled"
    tenant.cancelled_at = datetime.utcnow()

    await db.flush()

    return {"ok": True, "message": "Account cancelled. Your data will be retained for 30 days."}
