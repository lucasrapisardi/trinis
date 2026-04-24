# PATH: /home/lumoura/trinis_ai/trinis/app/tasks/enrich.py
"""
Enrich task — parallel GPT-4o with batch processing and EAN cache.

Optimizations:
  1. Parallel: 4 concurrent GPT calls via ThreadPoolExecutor
  2. Batch: sends 3 products per GPT call (less overhead, fewer tokens)
  3. EAN cache: skips products already enriched (re-uses cached description)
"""
import concurrent.futures
import json
import queue
import threading
from openai import OpenAI

from app.tasks.celery_app import celery_app
from app.tasks.base import JobTask
from app.models.models import VendorConfig
from app.core.config import get_settings
from app.services.ean_cache import get_cached, set_cached

settings = get_settings()

MAX_WORKERS = 4
BATCH_SIZE = 3  # products per GPT call


@celery_app.task(bind=True, base=JobTask, queue="enrich", max_retries=3)
def enrich_products(self, job_id: str, tenant_id: str, products: list[dict]):
    with self.job_context(job_id) as ctx:
        try:
            db = ctx.db
            job = ctx.job
            config = db.get(VendorConfig, job.vendor_config_id)

            if not config:
                ctx.fail("VendorConfig not found")
                return

            client = OpenAI(api_key=settings.openai_api_key)

            from app.models.models import User, ShopifyStore
            from sqlalchemy import select as sa_select

            tenant_result = db.execute(
                sa_select(User).where(
                    User.tenant_id == job.tenant_id,
                    User.is_owner == True,
                )
            ).scalar_one_or_none()
            locale = getattr(tenant_result, "locale", "pt") if tenant_result else "pt"

            store_result = db.execute(
                sa_select(ShopifyStore).where(ShopifyStore.id == job.store_id)
            ).scalar_one_or_none()
            store_id = str(store_result.id) if store_result else "unknown"

            system_prompt = config.brand_prompt or _default_brand_prompt(
                config.brand_name or "", locale=locale
            )

            total = len(products)

            # ── Step 1: Check EAN cache ──────────────────────────────────
            cached_count = 0
            to_enrich = []
            for product in products:
                cached = get_cached(tenant_id, store_id, product["ean"])
                if cached and cached.get("enriched_description"):
                    product["enriched_description"] = cached["enriched_description"]
                    product["price_multiplier"] = config.price_multiplier
                    product["_from_cache"] = True
                    cached_count += 1
                else:
                    to_enrich.append(product)

            if cached_count:
                ctx.log("info", f"  ✓ {cached_count}/{total} products loaded from cache — skipping AI")

            if not to_enrich:
                ctx.log("info", "All products from cache — skipping enrichment entirely")
                _finish_enrich(ctx, job_id, tenant_id, products, total, config)
                return

            ctx.log("info", f"Enriching {len(to_enrich)}/{total} products with GPT-4o (batch={BATCH_SIZE}, workers={MAX_WORKERS})...")

            # ── Step 2: Batch enrichment in parallel ──────────────────────
            batches = [to_enrich[i:i+BATCH_SIZE] for i in range(0, len(to_enrich), BATCH_SIZE)]
            completed = [0]
            log_queue = queue.Queue()

            def enrich_batch(batch):
                try:
                    results = _call_gpt_batch(client, system_prompt, batch, config, locale)
                    for product, description in zip(batch, results):
                        product["enriched_description"] = description
                        product["price_multiplier"] = config.price_multiplier
                        ctx.log("info", f"  ✓ Enriched: {product['nome'][:50]}")
                except Exception as e:
                    ctx.log("warn", f"  ✗ Batch GPT failed: {e} — using original descriptions")
                    for product in batch:
                        product["enriched_description"] = product.get("descricao", "")
                        product["price_multiplier"] = config.price_multiplier

                completed[0] += len(batch)
                for p in batch:
                    log_queue.put(("info", f"  ✓ Enriched: {p['nome'][:50]}"))
                return batch

            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                list(executor.map(enrich_batch, batches))

            # Drain log queue on main thread
            while not log_queue.empty():
                level, msg = log_queue.get_nowait()
                ctx.log(level, msg)
            pct = 66
            ctx.update_progress(scraped=total, enriched=total, pct=pct)
            ctx.log("info", f"Enrichment complete — {len(products)} products ready")
            _finish_enrich(ctx, job_id, tenant_id, products, total, config)

        except Exception as e:
            ctx.fail(str(e))
            raise self.retry(exc=e, countdown=60)


def _finish_enrich(ctx, job_id, tenant_id, products, total, config):
    ctx.update_progress(scraped=total, enriched=total, pct=66)
    from app.tasks.image import upgrade_images
    upgrade_images.apply_async(
        args=[job_id, tenant_id, products],
        queue="image",
    )


def _call_gpt_batch(client, system_prompt, batch, config, locale) -> list[str]:
    """
    Send multiple products in a single GPT-4o call.
    Returns list of descriptions in the same order as batch.
    """
    lang_instruction = {
        "pt": "Responda em português.",
        "en": "Respond in English.",
        "es": "Responde en español.",
    }.get(locale, "Responda em português.")

    products_text = ""
    for i, p in enumerate(batch):
        products_text += f"""
--- PRODUTO {i+1} ---
Nome: {p['nome']}
Preço (custo): {p.get('preco', '')}
Descrição original: {p.get('descricao', '')}
Ficha técnica: {p.get('ficha_tecnica', '')}
EAN: {p['ean']}
"""

    user_content = f"""Reescreva {len(batch)} produtos no padrão da marca. {lang_instruction}

{products_text}

Retorne um JSON com esta estrutura exata (sem markdown, sem texto extra):
{{
  "products": [
    {{"index": 0, "description": "descrição completa do produto 1"}},
    {{"index": 1, "description": "descrição completa do produto 2"}},
    {{"index": 2, "description": "descrição completa do produto 3"}}
  ]
}}
"""

    resp = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.7,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    )

    raw = resp.choices[0].message.content or "{}"
    data = json.loads(raw)
    items = data.get("products", [])

    # Map back by index, fallback to original if missing
    result = [p.get("descricao", "") for p in batch]
    for item in items:
        idx = item.get("index", -1)
        if 0 <= idx < len(batch):
            result[idx] = item.get("description", batch[idx].get("descricao", ""))

    return result


def _default_brand_prompt(brand_name: str, locale: str = "pt") -> str:
    prompts = {
        "pt": f"Você é especialista em criar descrições de produto para a marca {brand_name}. Gere descrições com SEO otimizado, storytelling e estrutura técnica. Não use emojis. Retorne JSON conforme solicitado.",
        "en": f"You are a product description expert for {brand_name}. Generate SEO-optimized descriptions with storytelling and technical structure. No emojis. Return JSON as requested.",
        "es": f"Eres experto en crear descripciones de producto para {brand_name}. Genera descripciones con SEO optimizado y estructura técnica. Sin emojis. Devuelve JSON como se solicita.",
    }
    return prompts.get(locale) or prompts["pt"]
