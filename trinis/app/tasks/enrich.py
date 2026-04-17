"""
Enrich task — refactored from dimora_gpt.py

Calls GPT-4o to generate SEO-optimized product descriptions
using the tenant's custom brand prompt.
"""
from openai import OpenAI

from app.tasks.celery_app import celery_app
from app.tasks.base import JobTask, SyncSession
from app.models.models import VendorConfig
from app.core.config import get_settings

settings = get_settings()


@celery_app.task(bind=True, base=JobTask, queue="enrich", max_retries=3)
def enrich_products(self, job_id: str, tenant_id: str, products: list[dict]):
    """
    Takes a list of raw product dicts from the scrape task,
    enriches each with GPT-4o descriptions, then chains into image task.
    """
    with self.job_context(job_id) as ctx:
        try:
            db = ctx.db
            job = ctx.job
            config = db.get(VendorConfig, job.vendor_config_id)

            if not config:
                ctx.fail("VendorConfig not found")
                return

            client = OpenAI(api_key=settings.openai_api_key)
            system_prompt = config.brand_prompt or _default_brand_prompt(config.brand_name or "")

            ctx.log("info", f"Enriching {len(products)} products with GPT-4o...")

            enriched = []
            for i, product in enumerate(products):
                ctx.log("info", f"Enriching [{i+1}/{len(products)}]: {product['nome']}")
                try:
                    description = _call_gpt(client, system_prompt, product, config)
                    product["enriched_description"] = description
                    product["price_multiplier"] = config.price_multiplier
                    enriched.append(product)
                except Exception as e:
                    ctx.log("warn", f"GPT failed for {product['nome']}: {e}")
                    product["enriched_description"] = product.get("descricao", "")
                    enriched.append(product)  # still push with original description

                pct = 33 + int((i + 1) / len(products) * 33)
                ctx.update_progress(
                    scraped=len(products),
                    enriched=i + 1,
                    pct=pct,
                )

            ctx.log("info", f"Enrichment complete — {len(enriched)} products ready")

            # Chain into image task
            from app.tasks.image import upgrade_images
            upgrade_images.apply_async(
                args=[job_id, tenant_id, enriched],
                queue="image",
            )

        except Exception as e:
            ctx.fail(str(e))
            raise self.retry(exc=e, countdown=60)


def _call_gpt(client: OpenAI, system_prompt: str, product: dict, config: VendorConfig) -> str:
    """Send product data to GPT-4o and return the enriched description."""
    user_content = f"""Reescreva no padrão da marca. INPUT:

## Nome
{product['nome']}

## Preço (custo)
{product['preco']}

## Descrição original
{product['descricao']}

## Ficha Técnica
{product.get('ficha_tecnica', '')}

## EAN
{product['ean']}
"""

    resp = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.7,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    )
    return (resp.choices[0].message.content or "").strip()


def _default_brand_prompt(brand_name: str) -> str:
    return f"""
Você é um especialista em criar descrições de produto para a marca {brand_name}.
Gere descrições com SEO otimizado, storytelling e estrutura técnica clara.
Inclua: título H1, subtítulo, storytelling, informações técnicas, meta descrição e tags SEO.
Não use emojis. Retorne apenas o texto final formatado.
"""
