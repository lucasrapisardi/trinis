"""
SKU creator task — refactored from sku-creator.py

Generates SKUs from product titles for all variants that
don't have one yet, scoped to the tenant's Shopify store.
"""
import re
import time
import unicodedata

import requests

from app.tasks.celery_app import celery_app
from app.tasks.base import JobTask
from app.models.models import ShopifyStore
from app.core.config import get_settings
from app.core.encryption import decrypt_token

settings = get_settings()


@celery_app.task(bind=True, base=JobTask, queue="sync", max_retries=3)
def generate_skus(self, job_id: str, tenant_id: str):
    """
    Iterates all Shopify products for the tenant's store and
    generates SKUs for any variant that is missing one.
    """
    with self.job_context(job_id) as ctx:
        try:
            db = ctx.db
            job = ctx.job

            store = db.get(ShopifyStore, job.store_id)
            if not store:
                ctx.fail("Store not found")
                return

            access_token = decrypt_token(store.encrypted_access_token)
            base_url = f"https://{store.shop_domain}/admin/api/{settings.shopify_api_version}"
            headers = {
                "X-Shopify-Access-Token": access_token,
                "Content-Type": "application/json",
            }

            ctx.log("info", f"Generating SKUs for store: {store.shop_domain}")

            updated, skipped = 0, 0
            params = {"limit": 250, "status": "active"}

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
                    for variant in product.get("variants", []):
                        if variant.get("sku"):
                            skipped += 1
                            continue

                        new_sku = _generate_sku(product["title"])
                        ctx.log("info", f"Setting SKU: {product['title']} → {new_sku}")

                        patch_resp = requests.put(
                            f"{base_url}/variants/{variant['id']}.json",
                            headers=headers,
                            json={"variant": {"id": variant["id"], "sku": new_sku}},
                            timeout=15,
                        )
                        if patch_resp.status_code in (200, 201):
                            updated += 1
                        else:
                            ctx.log("warn", f"Failed to set SKU for variant {variant['id']}: {patch_resp.status_code}")

                        time.sleep(0.5)  # ~2 req/s

                # Pagination
                link = resp.headers.get("Link", "")
                if 'rel="next"' not in link:
                    break
                m = re.search(r'page_info=([^&>]+)[^>]*>;\s*rel="next"', link)
                if not m:
                    break
                params = {"limit": 250, "page_info": m.group(1)}

            ctx.log("info", f"SKU generation complete — {updated} updated, {skipped} already had SKUs")
            ctx.finish()

        except Exception as e:
            ctx.fail(str(e))
            raise self.retry(exc=e, countdown=60)


def _normalize(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def _generate_sku(title: str) -> str:
    """
    Generate a SKU from a product title.
    e.g. "Jogo de Facas Tramontina 5 Peças" → "JOG-DE-FAC-TRA-5-PEC"
    """
    normalized = _normalize(title.lower())
    words = re.findall(r"\w+", normalized)
    parts = []
    for word in words:
        if word.isdigit():
            parts.append(word)
        else:
            parts.append(word[:3].upper())
    return "-".join(parts)
