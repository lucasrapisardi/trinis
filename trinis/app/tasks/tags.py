"""
Tags updater task — refactored from tags-updater.py

Generates SEO tags from product title/vendor/type and
an optional keyword list stored in VendorConfig, then
pushes them to Shopify via GraphQL.
"""
import time

import requests

from app.tasks.celery_app import celery_app
from app.tasks.base import JobTask
from app.models.models import ShopifyStore, VendorConfig
from app.core.config import get_settings
from app.core.encryption import decrypt_token

settings = get_settings()


@celery_app.task(bind=True, base=JobTask, queue="sync", max_retries=3)
def update_tags(self, job_id: str, tenant_id: str, keywords: list[str] | None = None):
    """
    Generates and applies SEO tags to all products in the tenant's store.
    Optionally accepts a list of seed keywords to match against.
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
            access_token = decrypt_token(store.encrypted_access_token)
            shop_url = store.shop_domain
            api_version = settings.shopify_api_version

            gql_url = f"https://{shop_url}/admin/api/{api_version}/graphql.json"
            gql_headers = {
                "X-Shopify-Access-Token": access_token,
                "Content-Type": "application/json",
            }

            keyword_set = set(k.lower() for k in (keywords or []))
            ctx.log("info", f"Updating tags for store: {shop_url} ({len(keyword_set)} seed keywords)")

            cursor = None
            updated = 0

            while True:
                products, has_next, cursor = _fetch_products_page(gql_url, gql_headers, cursor)

                if not products:
                    break

                for product in products:
                    new_tags = _generate_tags(
                        title=product["title"],
                        vendor=product.get("vendor", ""),
                        product_type=product.get("productType", ""),
                        keywords=keyword_set,
                    )

                    success = _apply_tags(gql_url, gql_headers, product["id"], new_tags)
                    if success:
                        ctx.log("info", f"Tagged: {product['title']} ({len(new_tags)} tags)")
                        updated += 1
                    else:
                        ctx.log("warn", f"Failed to tag: {product['title']}")

                    time.sleep(0.5)

                if not has_next:
                    break

            ctx.log("info", f"Tags update complete — {updated} products updated")
            ctx.finish()

        except Exception as e:
            ctx.fail(str(e))
            raise self.retry(exc=e, countdown=60)


def _fetch_products_page(
    gql_url: str, headers: dict, cursor: str | None
) -> tuple[list[dict], bool, str | None]:
    query = """
    query($cursor: String) {
      products(first: 20, after: $cursor) {
        edges {
          cursor
          node {
            id
            title
            vendor
            productType
            tags
          }
        }
        pageInfo { hasNextPage }
      }
    }
    """
    resp = requests.post(
        gql_url,
        headers=headers,
        json={"query": query, "variables": {"cursor": cursor}},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json().get("data", {}).get("products", {})
    edges = data.get("edges", [])
    products = [e["node"] for e in edges]
    has_next = data.get("pageInfo", {}).get("hasNextPage", False)
    next_cursor = edges[-1]["cursor"] if edges else None
    return products, has_next, next_cursor


def _apply_tags(gql_url: str, headers: dict, product_id: str, tags: list[str]) -> bool:
    mutation = """
    mutation productUpdate($input: ProductInput!) {
      productUpdate(input: $input) {
        product { id tags }
        userErrors { field message }
      }
    }
    """
    resp = requests.post(
        gql_url,
        headers=headers,
        json={"query": mutation, "variables": {"input": {"id": product_id, "tags": tags}}},
        timeout=20,
    )
    if resp.status_code != 200:
        return False
    errors = resp.json().get("data", {}).get("productUpdate", {}).get("userErrors", [])
    return len(errors) == 0


def _generate_tags(
    title: str,
    vendor: str,
    product_type: str,
    keywords: set[str],
    max_tags: int = 50,
) -> list[str]:
    """
    Generate tags from title words, vendor, product type,
    and matching seed keywords.
    """
    titulo = title.lower()
    marca = vendor.lower() if vendor else ""
    categoria = product_type.lower() if product_type else ""

    # Simple word tokenization (no NLTK dependency in worker)
    words = [w for w in titulo.split() if len(w) > 2]

    tags: set[str] = set()

    # Single words and bigrams from title
    for i, word in enumerate(words):
        tags.add(word)
        if i < len(words) - 1:
            tags.add(f"{word} {words[i+1]}")

    # Vendor + category combos
    if marca:
        tags.add(marca)
        if words:
            tags.add(f"{words[0]} {marca}")
    if categoria:
        tags.add(categoria)
        if marca:
            tags.add(f"{categoria} {marca}")

    # Seed keyword matching
    texto = f"{titulo} {marca} {categoria}"
    for kw in keywords:
        if any(part in texto for part in kw.split()):
            tags.add(kw)

    # Title-case and cap at max_tags
    return sorted({t.strip().title() for t in tags if t.strip()})[:max_tags]
