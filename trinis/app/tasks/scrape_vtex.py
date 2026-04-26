"""
VTEX platform scraper — uses the Intelligent Search API.
Works for any VTEX-based store without JS rendering.
"""
import requests
from urllib.parse import urlparse


def _get_domain(base_url: str) -> str:
    return urlparse(base_url).netloc


def _extract_query(base_url: str) -> str:
    """Try to extract a search term from the URL path."""
    path = urlparse(base_url).path.strip("/")
    # Use last path segment as search query
    parts = [p for p in path.split("/") if p]
    return parts[-1].replace("-", " ") if parts else ""


def fetch_vtex_products(base_url: str, limit: int = 50, ctx=None) -> list[dict]:
    domain = _get_domain(base_url)
    query = _extract_query(base_url) or "produto"

    if ctx:
        ctx.log("info", f"[vtex] Searching '{query}' on {domain}")

    results = []
    page_size = min(50, limit)

    url = f"https://{domain}/api/io/_v/api/intelligent-search/product_search/{query}"
    params = {"count": page_size, "page": 1}

    try:
        r = requests.get(url, params=params, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        data = r.json()
        products = data.get("products", [])

        if ctx:
            ctx.log("info", f"[vtex] Found {len(products)} products")

        for p in products[:limit]:
            # Extract price from items/sellers
            price = 0
            image_url = ""
            ean = ""

            items = p.get("items", [])
            if items:
                sellers = items[0].get("sellers", [])
                if sellers:
                    price = sellers[0].get("commertialOffer", {}).get("Price", 0)
                ean = items[0].get("ean", "") or items[0].get("referenceId", [{}])[0].get("Value", "")
                images = items[0].get("images", [])
                if images:
                    image_url = images[0].get("imageUrl", "")

            results.append({
                "nome": p.get("productName", ""),
                "preco": price,
                "ean": ean,
                "descricao": p.get("description", ""),
                "imagem_url": image_url,
                "link": f"https://{domain}{p.get('linkText', '')}/p",
            })

    except Exception as e:
        if ctx:
            ctx.log("warning", f"[vtex] Failed: {e}")

    return results


def is_vtex(base_url: str) -> bool:
    """Detect if a site runs on VTEX by probing the API."""
    domain = _get_domain(base_url)
    try:
        r = requests.get(
            f"https://{domain}/api/catalog_system/pub/products/search/?_from=0&_to=0",
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        # VTEX returns 206 or 200 on this endpoint
        return r.status_code in (200, 206)
    except Exception:
        return False
