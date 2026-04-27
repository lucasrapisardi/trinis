import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

def _get_base(base_url):
    p = urlparse(base_url)
    return f"{p.scheme}://{p.netloc}"

def _fetch_product_detail(item):
    try:
        resp = requests.get(item["link"], timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(resp.text, "html.parser")
        price_el = soup.select_one(".price .woocommerce-Price-amount, .price bdi")
        if price_el:
            price_text = price_el.get_text(strip=True)
            nums = re.findall(r"[\d]+[.,][\d]+", price_text)
            if nums:
                item["preco"] = float(nums[0].replace(".", "").replace(",", "."))
        img_el = soup.select_one(".woocommerce-product-gallery img")
        if img_el:
            src = img_el.get("src", "") or img_el.get("data-lazy-src", "")
            if src and not src.startswith("data:"):
                item["imagem_url"] = src
        desc_el = soup.select_one(".woocommerce-product-details__short-description, .entry-summary .woocommerce-Tabs-panel--description")
        if desc_el:
            item["descricao"] = desc_el.get_text(strip=True)[:500]
    except Exception:
        pass
    return item

def fetch_woocommerce_products(base_url, limit=50, ctx=None):
    base = _get_base(base_url)
    if ctx:
        ctx.log("info", f"[woocommerce] Fetching from {base}")
    try:
        probe = requests.get(
            f"{base}/wp-json/wc/v3/products?per_page=1",
            timeout=8, headers={"User-Agent": "Mozilla/5.0"}
        )
        if probe.status_code == 401:
            if ctx:
                ctx.log("info", "[woocommerce] API private - scraping HTML directly")
            return _scrape_woo_html(base_url, limit, ctx)
    except Exception:
        pass
    results = []
    page = 1
    page_size = min(100, limit)
    while len(results) < limit:
        try:
            r = requests.get(
                f"{base}/wp-json/wc/v3/products",
                params={"per_page": page_size, "page": page, "status": "publish"},
                timeout=20, headers={"User-Agent": "Mozilla/5.0"}
            )
            r.raise_for_status()
            products = r.json()
            if not products:
                break
            for p in products:
                images = p.get("images", [])
                image_url = images[0].get("src", "") if images else ""
                ean = ""
                for attr in p.get("attributes", []):
                    name = attr.get("name", "").lower()
                    if "ean" in name or "barcode" in name:
                        opts = attr.get("options", [])
                        ean = opts[0] if opts else ""
                        break
                results.append({
                    "nome": p.get("name", ""),
                    "preco": float(p.get("price", 0) or 0),
                    "ean": ean,
                    "descricao": p.get("description", "") or p.get("short_description", ""),
                    "imagem_url": image_url,
                    "link": p.get("permalink", ""),
                })
            if len(products) < page_size:
                break
            page += 1
        except Exception as e:
            if ctx:
                ctx.log("warning", f"[woocommerce] Error page {page}: {e}")
            break
    if ctx:
        ctx.log("info", f"[woocommerce] Done - {len(results)} products")
    return results[:limit]


def _scrape_woo_html(listing_url, limit=50, ctx=None):
    results = []
    try:
        resp = requests.get(listing_url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(resp.text, "html.parser")
        seen = set()
        items = []
        for li in soup.select("li.product"):
            a = li.select_one("a.woocommerce-LoopProduct-link, a.ast-loop-product__link")
            if not a:
                a = li.select_one("a[href]")
            if a and a.get("href") and a["href"] not in seen:
                seen.add(a["href"])
                title_el = li.select_one("h2, .woocommerce-loop-product__title")
                title = title_el.get_text(strip=True) if title_el else ""
                items.append({
                    "nome": title,
                    "preco": 0.0,
                    "ean": "",
                    "descricao": "",
                    "imagem_url": "",
                    "link": a["href"],
                })
        items = items[:limit]
        if ctx:
            ctx.log("info", f"[woocommerce-html] Found {len(items)} products, fetching details...")
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(_fetch_product_detail, items))
        if ctx:
            ctx.log("info", f"[woocommerce-html] Done - {len(results)} products with details")
    except Exception as e:
        if ctx:
            ctx.log("warning", f"[woocommerce-html] Error: {e}")
    return results


def is_woocommerce(base_url):
    base = _get_base(base_url)
    try:
        r = requests.get(
            f"{base}/wp-json/wc/v3/products?per_page=1",
            timeout=8, headers={"User-Agent": "Mozilla/5.0"}
        )
        return r.status_code in (200, 401)
    except Exception:
        return False
