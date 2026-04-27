import requests
from urllib.parse import urlparse

def _get_base(base_url):
    p = urlparse(base_url)
    return f"{p.scheme}://{p.netloc}"

def fetch_nuvemshop_products(base_url, limit=50, ctx=None):
    base = _get_base(base_url)
    if ctx:
        ctx.log("info", f"[nuvemshop] Fetching from {base}")
    results = []
    page = 1
    page_size = min(200, limit)
    while len(results) < limit:
        try:
            r = requests.get(
                f"{base}/api/v1/products",
                params={"per_page": page_size, "page": page, "published": "true"},
                timeout=20, headers={"User-Agent": "Mozilla/5.0"}
            )
            r.raise_for_status()
            products = r.json()
            if not products:
                break
            for p in products:
                images = p.get("images", [])
                image_url = images[0].get("src", "") if images else ""
                name = p.get("name", {})
                if isinstance(name, dict):
                    title = name.get("pt") or name.get("en") or next(iter(name.values()), "")
                else:
                    title = str(name)
                desc = p.get("description", {})
                if isinstance(desc, dict):
                    description = desc.get("pt") or desc.get("en") or next(iter(desc.values()), "")
                else:
                    description = str(desc)
                variants = p.get("variants", [{}])
                price = float(variants[0].get("price", 0) or 0) if variants else 0
                ean = variants[0].get("barcode", "") or "" if variants else ""
                results.append({
                    "nome": title,
                    "preco": price,
                    "ean": ean,
                    "descricao": description,
                    "imagem_url": image_url,
                    "link": p.get("canonical_url", ""),
                })
            if len(products) < page_size:
                break
            page += 1
        except Exception as e:
            if ctx:
                ctx.log("warning", f"[nuvemshop] Error page {page}: {e}")
            break
    if ctx:
        ctx.log("info", f"[nuvemshop] Done — {len(results)} products")
    return results[:limit]

def is_nuvemshop(base_url):
    base = _get_base(base_url)
    try:
        r = requests.get(f"{base}/api/v1/products?per_page=1", timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        return r.status_code in (200, 401)
    except Exception:
        return False
