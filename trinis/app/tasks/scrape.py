"""
Scrape task — refactored from scraper.py

Scrapes product listings from a vendor (e.g. Comercial Gomes),
stores raw data per EAN, and chains into the enrich task.
Respects scrape_scope (categoria / subcategoria / pagina) and product_limit.
"""
import os
import re
import uuid
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

from app.tasks.celery_app import celery_app
from app.tasks.base import JobTask, SyncSession
from app.models.models import VendorConfig


@celery_app.task(bind=True, base=JobTask, queue="scrape", max_retries=3)
def scrape_vendor(self, job_id: str, tenant_id: str):
    """
    Scrapes all products from the configured vendor URL.
    Respects scrape_scope and product_limit from the job record.
    """
    with self.job_context(job_id) as ctx:
        try:
            db = ctx.db
            job = ctx.job
            config = db.get(VendorConfig, job.vendor_config_id)

            if not config:
                ctx.fail("VendorConfig not found")
                return

            product_limit = job.product_limit  # None = unlimited
            scope = getattr(config, "scrape_scope", "pagina")

            ctx.log("info", f"Starting scrape: {config.name}")
            ctx.log("info", f"Scope: {scope} | Limit: {product_limit or 'all'}")
            ctx.log("info", f"Target: {config.base_url}")

            products = _scrape_all_pages(config, ctx, scope=scope, limit=product_limit)

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
    """
    Paginate through the vendor listing API and collect raw product data.

    scope:
      - "categoria"    → scrape all subcategories under the categoria
      - "subcategoria" → scrape all pages under categoria/subcategoria
      - "pagina"       → scrape only the specific pagina_especifica (default)

    limit: max number of products to collect (None = all)
    """
    url_base = "https://www.comercialgomes.com.br/handlers/departamento/SubCategoriaResult.ashx"
    qtde_por_pagina = 26
    all_products = []

    # Build the API params based on scope
    if scope == "categoria":
        # Scrape everything under the categoria — leave subcategoria empty
        categoria_api = config.categoria or ""
        subcategoria_api = ""
        pagina_api = ""
    elif scope == "subcategoria":
        # Scrape all pages under categoria/subcategoria
        categoria_api = config.subcategoria or ""
        subcategoria_api = config.pagina_especifica or ""
        pagina_api = ""
    else:
        # "pagina" — scrape the specific page (original behaviour)
        categoria_api = config.subcategoria or ""
        subcategoria_api = config.pagina_especifica or ""
        pagina_api = config.pagina_especifica or ""

    listagem_url = _build_listing_url(config, scope)
    ctx.log("info", f"Listing URL: {listagem_url}")

    pagina = 1
    while True:
        if limit and len(all_products) >= limit:
            ctx.log("info", f"Product limit ({limit}) reached — stopping scrape")
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
            ctx.log("info", "No more products — pagination complete")
            break

        for item in data:
            if limit and len(all_products) >= limit:
                break
            product = _scrape_product_detail(item, ctx)
            if product:
                all_products.append(product)

        pagina += 1

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
    """Fetch the product detail page and extract all fields."""
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
    ctx.log("info", f"Scraped: {nome} (EAN: {ean})")

    return {
        "ean": ean,
        "nome": nome,
        "link": link,
        "preco": preco,
        "descricao": descricao,
        "ficha_tecnica": ficha,
        "images": images,
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
