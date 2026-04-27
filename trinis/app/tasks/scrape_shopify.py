"""
Shopify platform scraper — uses the public /products.json endpoint.
Works on any Shopify store without authentication.
"""
import requests
from urllib.parse import urlparse


def _get_domain(base_url: str) -> str:
    return urlparse(base_url).netloc


def fetch_shopify_products(base_url: str, limit: int = 50, ctx=None) -> list[dict]:
    domain = _get_domain(base_url)

    if ctx:
        ctx.log("info", f"[shopify] Fetching products from {domain}")

    results = []
    page = 1
    page_size = min(250, limit)

    while len(results) < limit:
        url = f"https://{domain}/products.json"
        params = {"limit": page_size, "page": page}

        try:
            r = requests.get(url, params=params, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            products = r.json().get("products", [])

            if not products:
                break

            for p in products:
                variant = p.get("variants", [{}])[0]
                image = p.get("images", [{}])
                image_url = image[0].get("src", "") if image else ""
                ean = variant.get("barcode", "") or ""

                results.append({
                    "nome": p.get("title", ""),
                    "preco": float(variant.get("price", 0)),
                    "ean": ean,
                    "descricao": p.get("body_html", ""),
                    "imagem_url": image_url,
                    "link": f"https://{domain}/products/{p.get('handle', '')}",
                })

            if len(products) < page_size:
                break

            page += 1

        except Exception as e:
            if ctx:
                ctx.log("warning", f"[shopify] Failed page {page}: {e}")
            break

    if ctx:
        ctx.log("info", f"[shopify] Done — {len(results)} products")

    return results[:limit]


def is_shopify(base_url: str) -> bool:
    """Detect if a site runs on Shopify by probing /products.json."""
    domain = _get_domain(base_url)
    try:
        r = requests.get(
            f"https://{domain}/products.json?limit=1",
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        return r.status_code == 200 and "products" in r.json()
    except Exception:
        return False
