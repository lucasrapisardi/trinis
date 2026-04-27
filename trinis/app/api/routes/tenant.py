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

    base_url = payload.get("base_url", "").strip()
    if not base_url:
        raise HTTPException(status_code=400, detail="base_url is required")

    # Build target URL from scope fields
    scope = payload.get("scrape_scope", "pagina")
    categoria = payload.get("categoria", "").strip().strip("/")
    subcategoria = payload.get("subcategoria", "").strip().strip("/")
    pagina = payload.get("pagina_especifica", "").strip().strip("/")
    base = base_url.rstrip("/")

    if scope == "categoria" and categoria:
        url = f"{base}/{categoria}/"
    elif scope == "subcategoria" and subcategoria:
        url = f"{base}/{subcategoria}/"
    elif scope == "pagina" and pagina:
        url = f"{base}/{pagina}/"
    else:
        url = base_url

    try:
        # Detect scraper type
        domain = urlparse(url).netloc.lower()
        if "comercialgomes" in domain:
            return {"scraper_type": "comercial_gomes", "products": [], "message": "Dedicated adapter will be used for Comercial Gomes."}

        # Platform detection
        from app.tasks.scrape_vtex import is_vtex, fetch_vtex_products
        from app.tasks.scrape_shopify import is_shopify, fetch_shopify_products
        from app.tasks.scrape_woocommerce import is_woocommerce, fetch_woocommerce_products
        from app.tasks.scrape_nuvemshop import is_nuvemshop, fetch_nuvemshop_products

        def _fmt(products, scraper_type):
            return {
                "scraper_type": scraper_type,
                "products": [{"title": p["nome"], "price": p["preco"], "ean": p["ean"], "image_url": p["imagem_url"], "url": p["link"]} for p in products],
                "message": f"{scraper_type.upper()} store detected. Showing {len(products)} products.",
            }

        if is_vtex(url):
            return _fmt(fetch_vtex_products(url, limit=3), "vtex")
        if is_shopify(url):
            return _fmt(fetch_shopify_products(url, limit=3), "shopify")
        if is_nuvemshop(url):
            return _fmt(fetch_nuvemshop_products(url, limit=3), "nuvemshop")
        if is_woocommerce(url):
            products = fetch_woocommerce_products(url, limit=3)
            if not products:
                # Try /shop as fallback
                shop_url = url.rstrip("/") + "/shop/"
                products = fetch_woocommerce_products(shop_url, limit=3)
            scraper = "woocommerce (api)" if products and products[0].get("link", "").startswith("http") else "woocommerce (html)"
            msg = f"WooCommerce detected. {len(products)} products found."
            if not products:
                msg = "WooCommerce detected but no products found on this page. Try using a category URL (e.g. /shop/ or /categoria-produto/)."
            return {"scraper_type": scraper, "products": [{"title": p["nome"], "price": p["preco"], "ean": p["ean"], "image_url": p["imagem_url"], "url": p["link"]} for p in products], "message": msg}

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
