"""
Price updater task — refactored from price_updater.py

Reads inventory cost from Shopify InventoryItem and applies
the tenant's configured price multiplier + compare-at price.
"""
import random
import time
from math import isfinite

import requests

from app.tasks.celery_app import celery_app
from app.tasks.base import JobTask
from app.models.models import ShopifyStore, VendorConfig
from app.core.config import get_settings
from app.core.encryption import decrypt_token

settings = get_settings()


@celery_app.task(bind=True, base=JobTask, queue="sync", max_retries=3)
def update_prices(self, job_id: str, tenant_id: str):
    """
    Iterates all Shopify products for the tenant's store and
    recalculates prices from inventory cost using the configured multiplier.
    """
    with self.job_context(job_id) as ctx:
        try:
            db = ctx.db
            job = ctx.job

            store = db.get(ShopifyStore, job.store_id)
            if not store:
                ctx.fail("Store not found")
                return

            config = db.get(VendorConfig, job.vendor_config_id)
            multiplier = config.price_multiplier if config else 2.0

            access_token = decrypt_token(store.encrypted_access_token)
            base_url = f"https://{store.shop_domain}/admin/api/{settings.shopify_api_version}"
            headers = {
                "X-Shopify-Access-Token": access_token,
                "Content-Type": "application/json",
            }

            ctx.log("info", f"Updating prices for store: {store.shop_domain} (multiplier: {multiplier}x)")

            total, updated, skipped, failed = 0, 0, 0, 0
            statuses = ["active", "draft"]

            for status in statuses:
                params = {"limit": 250, "status": status}

                while True:
                    resp = requests.get(
                        f"{base_url}/products.json",
                        headers=headers,
                        params=params,
                        timeout=30,
                    )
                    resp.raise_for_status()
                    products = resp.json().get("products", [])

                    if not products:
                        break

                    for product in products:
                        total += 1
                        for variant in product.get("variants", []):
                            result = _update_variant_price(
                                variant=variant,
                                base_url=base_url,
                                headers=headers,
                                multiplier=multiplier,
                                ctx=ctx,
                            )
                            if result == "updated":
                                updated += 1
                            elif result == "skipped":
                                skipped += 1
                            else:
                                failed += 1

                    # Pagination
                    import re
                    link = resp.headers.get("Link", "")
                    if 'rel="next"' not in link:
                        break
                    m = re.search(r'page_info=([^&>]+)[^>]*>;\s*rel="next"', link)
                    if not m:
                        break
                    params = {"limit": 250, "page_info": m.group(1)}

            ctx.log("info", (
                f"Price update complete — "
                f"{updated} updated, {skipped} no cost, {failed} failed"
            ))
            ctx.finish()

        except Exception as e:
            ctx.fail(str(e))
            raise self.retry(exc=e, countdown=60)


def _get_inventory_cost(
    variant: dict, base_url: str, headers: dict
) -> float | None:
    """Fetch the inventory cost for a variant from Shopify InventoryItem."""
    inventory_item_id = variant.get("inventory_item_id")
    if not inventory_item_id:
        return None
    try:
        resp = requests.get(
            f"{base_url}/inventory_items/{inventory_item_id}.json",
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        cost = resp.json().get("inventory_item", {}).get("cost")
        if cost is not None:
            return float(cost)
    except Exception:
        pass
    return None


def _randomize_discount() -> float:
    """Returns a random factor between 0.65 and 0.95 for compare-at price variation."""
    return round(random.uniform(0.65, 0.95), 2)


def _update_variant_price(
    variant: dict,
    base_url: str,
    headers: dict,
    multiplier: float,
    ctx,
) -> str:
    """
    Update price + compare_at_price for a single variant.
    Returns 'updated', 'skipped', or 'failed'.
    """
    cost = _get_inventory_cost(variant, base_url, headers)

    if cost is None or not isfinite(cost) or cost <= 0:
        return "skipped"

    # sale price = cost × multiplier × random discount factor
    factor = _randomize_discount()
    sale_price = round(cost * multiplier * factor, 2)

    # compare-at = full cost × multiplier (no discount — appears as "was" price)
    compare_price = round(cost * multiplier, 2)

    ctx.log("info", (
        f"  Variant {variant['id']} — "
        f"cost R${cost:.2f} → sale R${sale_price:.2f} | compare R${compare_price:.2f}"
    ))

    # Retry logic for rate limits
    for attempt in range(4):
        try:
            resp = requests.put(
                f"{base_url}/variants/{variant['id']}.json",
                headers=headers,
                json={"variant": {
                    "id": variant["id"],
                    "price": str(sale_price),
                    "compare_at_price": str(compare_price),
                }},
                timeout=15,
            )
            if resp.status_code in (200, 201):
                time.sleep(0.6)
                return "updated"
            elif resp.status_code == 429:
                # Rate limited — back off
                time.sleep(min(8, 2 ** attempt))
                continue
            else:
                ctx.log("warn", f"  Variant {variant['id']} price update failed: {resp.status_code}")
                return "failed"
        except Exception as e:
            time.sleep(min(8, 2 ** attempt))
            if attempt == 3:
                ctx.log("error", f"  Variant {variant['id']} exception: {e}")
                return "failed"

    return "failed"
