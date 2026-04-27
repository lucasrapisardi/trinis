# PATH: /home/lumoura/trinis_ai/trinis/app/tasks/scrape.py
"""
Scrape task — parallel product detail fetching using ThreadPoolExecutor.

Fetches product listing pages sequentially (to respect pagination),
but fetches individual product detail pages in parallel for ~5x speedup.
"""
import concurrent.futures
import hashlib
import os
import re
import uuid
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

from app.tasks.celery_app import celery_app
from app.tasks.base import JobTask, SyncSession
from app.models.models import VendorConfig
from app.tasks.scrape_generic import scrape_generic
from app.tasks.scrape_vtex import fetch_vtex_products, is_vtex
from app.tasks.scrape_shopify import fetch_shopify_products, is_shopify
from app.tasks.scrape_woocommerce import fetch_woocommerce_products, is_woocommerce
from app.tasks.scrape_nuvemshop import fetch_nuvemshop_products, is_nuvemshop

# Max parallel detail page fetches
MAX_SCRAPE_WORKERS = 8


@celery_app.task(bind=True, base=JobTask, queue="scrape", max_retries=3)
def scrape_vendor(self, job_id: str, tenant_id: str):
    with self.job_context(job_id) as ctx:
        try:
            db = ctx.db
            job = ctx.job
            config = db.get(VendorConfig, job.vendor_config_id)

            if not config:
                ctx.fail("VendorConfig not found")
                return

            product_limit = job.product_limit
            scope = getattr(config, "scrape_scope", "pagina")

            ctx.log("info", f"Starting scrape: {config.name}")
            ctx.log("info", f"Scope: {scope} | Limit: {product_limit or 'all'} | Workers: {MAX_SCRAPE_WORKERS}")
            ctx.log("info", f"Target: {config.base_url}")

            scraper_type = getattr(config, "scraper_type", "auto")
            # Detect known adapters by domain
            if scraper_type == "auto" and config.base_url:
                from urllib.parse import urlparse as _urlparse
                domain = _urlparse(config.base_url).netloc.lower()
                if "comercialgomes" in domain:
                    scraper_type = "comercial_gomes"
                elif is_vtex(config.base_url):
                    scraper_type = "vtex"
                elif is_shopify(config.base_url):
                    scraper_type = "shopify"
                elif is_nuvemshop(config.base_url):
                    scraper_type = "nuvemshop"
                elif is_woocommerce(config.base_url):
                    scraper_type = "woocommerce"

            ctx.log("info", f"Using scraper adapter: {scraper_type}")

            # Build full URL from base_url + scope fields
            from urllib.parse import urljoin
            base = config.base_url.rstrip("/")
            if scope == "categoria" and getattr(config, "categoria", ""):
                target_url = f"{base}/{config.categoria.strip('/')}/"
            elif scope == "subcategoria" and getattr(config, "subcategoria", ""):
                target_url = f"{base}/{config.subcategoria.strip('/')}/"
            elif scope == "pagina" and getattr(config, "pagina_especifica", ""):
                target_url = f"{base}/{config.pagina_especifica.strip('/')}/"
            else:
                target_url = config.base_url

            ctx.log("info", f"Target URL: {target_url}")

            if scraper_type == "comercial_gomes":
                products = _scrape_all_pages(config, ctx, scope=scope, limit=product_limit)
            elif scraper_type == "vtex":
                products = fetch_vtex_products(target_url, limit=product_limit, ctx=ctx)
            elif scraper_type == "shopify":
                products = fetch_shopify_products(target_url, limit=product_limit, ctx=ctx)
            elif scraper_type == "woocommerce":
                products = fetch_woocommerce_products(target_url, limit=product_limit, ctx=ctx)
            elif scraper_type == "nuvemshop":
                products = fetch_nuvemshop_products(target_url, limit=product_limit, ctx=ctx)
            else:
                products = scrape_generic(config, ctx, limit=product_limit)

            ctx.log("info", f"Scrape complete — {len(products)} products found")
            ctx.update_progress(scraped=len(products), pct=33)

            from app.tasks.enrich import enrich_products
            enrich_products.apply_async(
                args=[job_id, tenant_id, products],
                queue="enrich",
            )

        except Exception as e:
            ctx.fail(str(e))
            raise self.retry(exc=e, countdown=60)


def _scrape_all_pages(
    config: VendorConfig,
    ctx,
    scope: str = "pagina",
    limit: int | None = None,
) -> list[dict]:
    url_base = "https://www.comercialgomes.com.br/handlers/departamento/SubCategoriaResult.ashx"
    qtde_por_pagina = 26

    if scope == "categoria":
        categoria_api = config.categoria or ""
        subcategoria_api = ""
    elif scope == "subcategoria":
        categoria_api = config.subcategoria or ""
        subcategoria_api = config.pagina_especifica or ""
    else:
        categoria_api = config.subcategoria or ""
        subcategoria_api = config.pagina_especifica or ""

    listagem_url = _build_listing_url(config, scope)
    ctx.log("info", f"Listing URL: {listagem_url}")

    # Collect all raw listing items first
    raw_items = []
    pagina = 1
    while True:
        if limit and len(raw_items) >= limit:
            break

        ctx.log("info", f"Fetching page {pagina}...")
        params = {
            "subcategoria": subcategoria_api,
            "categoria": categoria_api,
            "marca": "",
            "ordenacao": "1",
            "preco": "",
            "qtdePorPagina": qtde_por_pagina,
            "paginaAtual": pagina,
            "atributoitemID": "",
            "URL": listagem_url,
        }
        try:
            resp = requests.get(
                url_base, params=params, timeout=20,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            ctx.log("warn", f"Page {pagina} failed: {e}")
            break

        if not data:
            break

        for item in data:
            if limit and len(raw_items) >= limit:
                break
            raw_items.append(item)

        pagina += 1

    ctx.log("info", f"Found {len(raw_items)} items — fetching details in parallel...")

    # Fetch product details in parallel
    all_products = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_SCRAPE_WORKERS) as executor:
        futures = {executor.submit(_scrape_product_detail, item, ctx): item for item in raw_items}
        for future in concurrent.futures.as_completed(futures):
            try:
                product = future.result()
                if product:
                    all_products.append(product)
            except Exception as e:
                ctx.log("warn", f"Detail fetch error: {e}")

    return all_products


def _build_listing_url(config: VendorConfig, scope: str = "pagina") -> str:
    base = "https://www.comercialgomes.com.br/"
    if scope == "categoria":
        parts = [p for p in [config.categoria] if p]
    elif scope == "subcategoria":
        parts = [p for p in [config.categoria, config.subcategoria] if p]
    else:
        parts = [p for p in [config.categoria, config.subcategoria, config.pagina_especifica] if p]
    path = "/".join(parts) + ".html" if parts else ""
    return urljoin(base, path)


def _scrape_product_detail(item: dict, ctx) -> dict | None:
    nome = item.get("nome", "").strip().replace("/", "-")
    link = item.get("url", "")
    preco = item.get("preco_consumidor", "")
    img = item.get("imagem", "")

    if not link:
        return None

    try:
        html = requests.get(link, timeout=20, headers={"User-Agent": "Mozilla/5.0"}).text
        soup = BeautifulSoup(html, "html.parser")
    except Exception as e:
        ctx.log("warn", f"Failed to fetch detail page for {nome}: {e}")
        return None

    meta_desc = soup.find("meta", attrs={"name": "description"})
    descricao = meta_desc["content"].strip() if meta_desc else ""

    blocos = soup.find_all("div", class_="divInformacaoAdicional")
    ficha = "\n".join(b.get_text(separator="\n").strip() for b in blocos) if blocos else ""

    ean = _extract_ean_from_image_url(img)
    if not ean:
        for tag in soup.find_all(string=re.compile(r"\bEAN\b", re.I)):
            m = re.search(r"(\d{12,14})", tag)
            if m:
                ean = m.group(1)
                break

    if not ean or not re.fullmatch(r"\d{12,14}", str(ean)):
        ctx.log("warn", f"No valid EAN for product: {nome} — skipping")
        return None

    images = _collect_image_urls(img, ean)
    # Compute image hash for change detection (used by image task to skip unchanged)
    image_hash = _hash_url(images[0]) if images else None

    ctx.log("info", f"Scraped: {nome} (EAN: {ean})")

    return {
        "ean": ean,
        "nome": nome,
        "link": link,
        "preco": preco,
        "descricao": descricao,
        "ficha_tecnica": ficha,
        "images": images,
        "image_hash": image_hash,
    }


def _extract_ean_from_image_url(img_url: str) -> str | None:
    if not img_url:
        return None
    nome = os.path.basename(urlparse(img_url).path)
    m = re.search(r"(\d{8,22})_media", nome)
    return m.group(1) if m else None


def _collect_image_urls(img_url: str, ean: str) -> list[str]:
    images = []
    if img_url:
        images.append(img_url)

    base_media = "https://www.comercialgomes.com.br/imagesp/media"
    for suffix in ["", "1", "2"]:
        url = f"{base_media}/{ean}_media{suffix}.jpg"
        try:
            r = requests.head(url, timeout=6, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                images.append(url)
        except Exception:
            pass

    seen, deduped = set(), []
    for u in images:
        fn = os.path.basename(urlparse(u).path)
        if fn not in seen:
            seen.add(fn)
            deduped.append(u)

    return deduped


def _hash_url(url: str) -> str:
    """Simple hash of URL for change detection."""
    return hashlib.md5(url.encode()).hexdigest()[:16]
