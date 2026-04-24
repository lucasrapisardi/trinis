"""
Shopify sync task — refactored from sync_cg_to_shopify.py

Pushes enriched products (with upgraded images) to Shopify
via the Admin REST API. Creates new products or updates existing ones.
"""
import base64
import re
import time
import uuid
from datetime import datetime, timezone

import requests

from app.tasks.celery_app import celery_app
from app.tasks.base import JobTask, SyncSession
from app.models.models import VendorConfig, ShopifyStore
from app.core.config import get_settings
from app.core.encryption import decrypt_token
from app.services.ean_cache import set_cached

settings = get_settings()


@celery_app.task(bind=True, base=JobTask, queue="sync", max_retries=3)
def push_to_shopify(self, job_id: str, tenant_id: str, products: list[dict]):
    """
    Creates or updates products in the tenant's Shopify store.
    Uses the per-tenant encrypted access token.
    """
    with self.job_context(job_id) as ctx:
        try:
            db = ctx.db
            job = ctx.job

            # Load store credentials
            store = db.get(ShopifyStore, job.store_id)
            if not store or not store.is_active:
                ctx.fail("Shopify store not found or disconnected")
                return

            config = db.get(VendorConfig, job.vendor_config_id)
            access_token = decrypt_token(store.encrypted_access_token)

            shop_url = store.shop_domain
            api_version = settings.shopify_api_version
            headers = {
                "X-Shopify-Access-Token": access_token,
                "Content-Type": "application/json",
            }

            ctx.log("info", f"Pushing {len(products)} products to {shop_url}")

            pushed, failed = 0, 0
            store_id = str(store.id)
            pushed_shopify_ids = []

            for i, product in enumerate(products):
                ctx.log("info", f"Syncing [{i+1}/{len(products)}]: {product['nome']}")
                try:
                    shopify_product_id = _upsert_product(
                        product=product,
                        shop_url=shop_url,
                        api_version=api_version,
                        headers=headers,
                        config=config,
                        ctx=ctx,
                    )
                    pushed += 1
                    pushed_shopify_ids.append(str(shopify_product_id))
                    # Cache EAN for future re-sync skip
                    set_cached(tenant_id, store_id, product["ean"], {
                        "image_hash": product.get("image_hash"),
                        "minio_keys": product.get("minio_keys", []),
                        "enriched_description": product.get("enriched_description", ""),
                    })
                except Exception as e:
                    ctx.log("error", f"Failed to sync {product['nome']}: {e}")
                    failed += 1

                pct = 83 + int((i + 1) / len(products) * 17)  # 83–100%
                ctx.update_progress(
                    scraped=len(products),
                    enriched=len(products),
                    pushed=pushed,
                    failed=failed,
                    pct=pct,
                )

                time.sleep(0.5)  # Shopify rate limit: ~2 req/s

            # Update last synced timestamp
            store.last_synced_at = datetime.now(timezone.utc)
            db.commit()

            ctx.log("info", f"Sync complete — {pushed} pushed, {failed} failed")

            if failed > 0 and pushed > 0:
                ctx.finish_with_errors({
                    "pushed": pushed,
                    "failed": failed,
                    "total": len(products),
                    "message": f"{failed} product(s) failed during sync",
                })
            elif failed > 0 and pushed == 0:
                ctx.fail(f"All {failed} products failed to sync")
            else:
                ctx.finish()

            # Chain post-processing tasks
            if pushed > 0:
                ctx.log("info", f"Starting post-processing for {len(pushed_shopify_ids)} products: SKU → Tags → Pricing")
                from app.tasks.sku import generate_skus
                from app.tasks.tags import update_tags
                from app.tasks.pricing import update_prices
                generate_skus.apply_async(
                    args=[job_id, tenant_id, pushed_shopify_ids],
                    queue="sync",
                )
                update_tags.apply_async(
                    args=[job_id, tenant_id, None, pushed_shopify_ids],
                    queue="sync",
                )
                update_prices.apply_async(
                    args=[job_id, tenant_id, pushed_shopify_ids],
                    queue="sync",
                )

        except Exception as e:
            ctx.fail(str(e))
            raise self.retry(exc=e, countdown=60)


def _upsert_product(
    product: dict,
    shop_url: str,
    api_version: str,
    headers: dict,
    config: VendorConfig,
    ctx,
):
    """Create or update a single Shopify product."""
    base_url = f"https://{shop_url}/admin/api/{api_version}"

    # Check if product exists by barcode (EAN)
    existing_id = _find_product_by_ean(product["ean"], base_url, headers)

    # Parse price from enriched description or fallback to raw price
    cost = _parse_price(product.get("preco", "0"))
    multiplier = product.get("price_multiplier", config.price_multiplier if config else 2.0)
    sale_price = round(cost * multiplier, 2)
    compare_price = round(cost * multiplier * 1.2, 2)  # 20% above sale = "was" price

    payload = {
        "product": {
            "title": product["nome"],
            "body_html": product.get("enriched_description") or product.get("descricao", ""),
            "vendor": config.brand_name if config else "",
            "status": "active",
            "variants": [
                {
                    "price": str(sale_price),
                    "compare_at_price": str(compare_price),
                    "barcode": product["ean"],
                    "inventory_management": "shopify",
                }
            ],
        }
    }

    if existing_id:
        # Update
        resp = requests.put(
            f"{base_url}/products/{existing_id}.json",
            headers=headers,
            json=payload,
            timeout=30,
        )
        action = "updated"
    else:
        # Create
        resp = requests.post(
            f"{base_url}/products.json",
            headers=headers,
            json=payload,
            timeout=30,
        )
        action = "created"

    resp.raise_for_status()
    shopify_product = resp.json()["product"]
    shopify_product_id = shopify_product["id"]

    ctx.log("info", f"  ✓ Product {action}: {product['nome']} (Shopify ID: {shopify_product_id})")

    # Upload upgraded images
    upgraded_images = product.get("upgraded_images", [])
    if upgraded_images:
        _upload_images(shopify_product_id, upgraded_images, base_url, headers, ctx)
    return shopify_product_id


def _find_product_by_ean(ean: str, base_url: str, headers: dict) -> str | None:
    """
    Search Shopify for a product whose variant barcode matches the EAN.
    Uses GraphQL for efficient barcode lookup.
    Returns the numeric Shopify product ID or None if not found.
    """
    graphql_url = base_url.replace("/admin/api/", "/admin/api/").rstrip("/") + "/../graphql.json"
    # Build correct GraphQL URL from base_url
    shop_host = base_url.split("/admin/api/")[0]
    api_version = base_url.split("/admin/api/")[1].rstrip("/")
    gql_url = f"{shop_host}/admin/api/{api_version}/graphql.json"

    query = """
    query($query: String!) {
      productVariants(first: 1, query: $query) {
        edges {
          node {
            product {
              id
              legacyResourceId
            }
          }
        }
      }
    }
    """
    variables = {"query": f"barcode:{ean}"}

    try:
        gql_headers = {k: v for k, v in headers.items()}
        gql_headers["Content-Type"] = "application/json"
        resp = requests.post(
            gql_url,
            headers=gql_headers,
            json={"query": query, "variables": variables},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        edges = data.get("data", {}).get("productVariants", {}).get("edges", [])
        if edges:
            return edges[0]["node"]["product"]["legacyResourceId"]
    except Exception as e:
        print(f"⚠️ GraphQL EAN lookup failed for {ean}: {e}")
    return None


def _upload_images(
    product_id: str,
    images: list[bytes],
    base_url: str,
    headers: dict,
    ctx,
):
    """Upload upgraded images to a Shopify product."""
    upload_headers = {k: v for k, v in headers.items() if k != "Content-Type"}

    for i, img_bytes in enumerate(images[:5]):  # max 5 images
        try:
            encoded = base64.b64encode(img_bytes).decode("utf-8")
            payload = {
                "image": {
                    "attachment": encoded,
                    "filename": f"product_{i+1}.png",
                    "position": i + 1,
                }
            }
            resp = requests.post(
                f"{base_url}/products/{product_id}/images.json",
                headers=upload_headers,
                json=payload,
                timeout=30,
            )
            if resp.status_code in (200, 201):
                ctx.log("info", f"  ✓ Image {i+1} uploaded")
            else:
                ctx.log("warn", f"  ✗ Image {i+1} upload failed: {resp.status_code}")
            time.sleep(0.3)
        except Exception as e:
            ctx.log("warn", f"  ✗ Image upload error: {e}")


def _parse_price(preco_str: str) -> float:
    """Extract numeric price from Brazilian format strings."""
    if not preco_str:
        return 0.0
    cleaned = re.sub(r"[^\d,.]", "", str(preco_str))
    cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


# ─────────────────────────────────────────────
# Maintenance task: deactivate discontinued products
# Refactored from sync_cg_to_shopify.py → desativar_produtos_inexistentes()
# ─────────────────────────────────────────────

@celery_app.task(bind=True, base=JobTask, queue="sync")
def deactivate_discontinued(self, job_id: str, tenant_id: str):
    """
    Checks all active Shopify products against the vendor API.
    Deactivates products no longer available at the supplier.
    """
    with self.job_context(job_id) as ctx:
        from app.tasks.base import SyncSession
        from app.models.models import Tenant
        from fetch_comercialgomes_product import fetch_comercialgomes_product

        db = ctx.db
        job = ctx.job
        store = db.get(ShopifyStore, job.store_id)

        if not store:
            ctx.fail("Store not found")
            return

        access_token = decrypt_token(store.encrypted_access_token)
        shop_url = store.shop_domain
        api_version = settings.shopify_api_version
        headers = {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json",
        }
        base_url = f"https://{shop_url}/admin/api/{api_version}"

        ctx.log("info", f"Checking active products against supplier...")

        # Paginate Shopify products
        params = {"limit": 250, "status": "active"}
        deactivated = 0

        while True:
            resp = requests.get(f"{base_url}/products.json", headers=headers, params=params, timeout=30)
            resp.raise_for_status()
            products = resp.json().get("products", [])

            if not products:
                break

            for p in products:
                ean = _extract_ean_from_product(p)
                if not ean:
                    continue

                supplier_data = fetch_comercialgomes_product(ean)
                if not supplier_data:
                    ctx.log("info", f"Deactivating: {p['title']} (EAN: {ean})")
                    requests.put(
                        f"{base_url}/products/{p['id']}.json",
                        headers=headers,
                        json={"product": {"id": p["id"], "status": "draft"}},
                        timeout=15,
                    )
                    deactivated += 1
                time.sleep(0.4)

            link_header = resp.headers.get("Link", "")
            if 'rel="next"' not in link_header:
                break
            # Extract next page_info from Link header
            import re as _re
            m = _re.search(r'<[^>]*page_info=([^&>]+)[^>]*>;\s*rel="next"', link_header)
            if not m:
                break
            params = {"limit": 250, "page_info": m.group(1)}

        ctx.log("info", f"Done — {deactivated} products deactivated")
        ctx.finish()


def _extract_ean_from_product(shopify_product: dict) -> str | None:
    for variant in shopify_product.get("variants", []):
        barcode = variant.get("barcode", "")
        if barcode and re.fullmatch(r"\d{12,14}", barcode):
            return barcode
    return None


# ─────────────────────────────────────────────
# Webhook registration helper
# ─────────────────────────────────────────────

@celery_app.task(queue="sync")
def register_shopify_webhooks(store_id: str):
    """Register required webhooks after a store connects."""
    from app.tasks.base import SyncSession
    from app.models.models import ShopifyStore

    db = SyncSession()
    try:
        store = db.get(ShopifyStore, uuid.UUID(store_id))
        if not store:
            return

        access_token = decrypt_token(store.encrypted_access_token)
        base_url = f"https://{store.shop_domain}/admin/api/{settings.shopify_api_version}"
        headers = {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json",
        }

        webhooks = [
            {"topic": "products/update", "address": f"{settings.app_base_url}/api/webhooks/shopify/products"},
            {"topic": "app/uninstalled", "address": f"{settings.app_base_url}/api/webhooks/shopify/uninstalled"},
        ]

        for wh in webhooks:
            resp = requests.post(
                f"{base_url}/webhooks.json",
                headers=headers,
                json={"webhook": {**wh, "format": "json"}},
                timeout=15,
            )
            if resp.status_code in (200, 201):
                print(f"✓ Webhook registered: {wh['topic']}")

        store.webhooks_registered = True
        db.commit()
    finally:
        db.close()
