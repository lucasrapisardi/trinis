"""
Image upgrade task — refactored from imagem_upgrader.py

Downloads product images, sends them to gpt-image-1 for
background replacement and quality enhancement, then
chains into the Shopify sync task.
"""
import base64
import io
import time

import requests
from openai import OpenAI
from PIL import Image

from app.tasks.celery_app import celery_app
from app.tasks.base import JobTask, SyncSession
from app.models.models import VendorConfig
from app.core.config import get_settings

settings = get_settings()

DEFAULT_IMAGE_PROMPT = """
Sempre que receber uma imagem de produto, transforme-a em uma foto de produto
profissional em alta resolução.

Regras:
1. NÃO altere o produto — não modificar cor, formato, textura ou proporção.
2. Se o fundo for branco ou neutro → substitua por:
   Pedra Clara Texturizada — superfície de pedra clara em tons de bege e areia,
   com iluminação natural suave e elegante.
3. Se o fundo NÃO for branco → mantenha o cenário, apenas melhore iluminação,
   nitidez e contraste.
4. Remova qualquer marca d'água ou logotipo.
5. Estilo final: fotografia de produto profissional, iluminação suave e natural.

Retorne apenas a imagem final processada.
"""


@celery_app.task(bind=True, base=JobTask, queue="image", max_retries=3)
def upgrade_images(self, job_id: str, tenant_id: str, products: list[dict]):
    """
    Downloads and upgrades images for each product using gpt-image-1,
    then chains into the Shopify sync task.
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
            # Get tenant locale
            from app.models.models import User
            from sqlalchemy import select as sa_select
            owner = ctx.db.execute(
                sa_select(User).where(User.tenant_id == job.tenant_id, User.is_owner == True)
            ).scalar_one_or_none()
            locale = getattr(owner, "locale", "pt") if owner else "pt"
            image_prompt = config.image_style_prompt or _default_image_prompt(locale)

            ctx.log("info", f"Upgrading images for {len(products)} products...")

            image_errors = 0
            for i, product in enumerate(products):
                if not product.get("images"):
                    ctx.log("warn", f"No images for {product['nome']} — skipping")
                    product["upgraded_images"] = []
                    product["image_error"] = "No images available"
                    image_errors += 1
                    continue

                ctx.log("info", f"Processing image [{i+1}/{len(products)}]: {product['nome']}")
                upgraded = _upgrade_product_images(
                    client, product["images"], image_prompt, ctx
                )

                # Store upgraded images in MinIO
                minio_keys = []
                for idx, img_bytes in enumerate(upgraded):
                    try:
                        key = upload_image(
                            image_bytes=img_bytes,
                            tenant_id=tenant_id,
                            ean=product["ean"],
                            index=idx,
                        )
                        minio_keys.append(key)
                        ctx.log("info", f"  ✓ Stored in MinIO: {key}")
                    except Exception as e:
                        ctx.log("warn", f"  ✗ MinIO upload failed: {e}")

                product["upgraded_images"] = upgraded
                product["minio_keys"] = minio_keys
                if not upgraded:
                    product["image_error"] = "Image upgrade failed"
                    image_errors += 1

                pct = 66 + int((i + 1) / len(products) * 17)  # 66–83%
                ctx.update_progress(
                    scraped=len(products),
                    enriched=len(products),
                    pct=pct,
                )
                time.sleep(0.3)  # rate limit breathing room

            ctx.log("info", "Image upgrade complete — pushing to Shopify")

            ctx.log("info", f"Image upgrade complete — {image_errors} failed out of {len(products)}")

            # Chain into sync task
            from app.tasks.sync import push_to_shopify
            push_to_shopify.apply_async(
                args=[job_id, tenant_id, products],
                queue="sync",
            )

        except Exception as e:
            ctx.fail(str(e))
            raise self.retry(exc=e, countdown=60)


def _upgrade_product_images(
    client: OpenAI,
    image_urls: list[str],
    prompt: str,
    ctx,
) -> list[bytes]:
    """Download + upgrade each image URL. Returns list of PNG bytes."""
    upgraded = []

    for url in image_urls[:3]:  # max 3 images per product
        try:
            resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()

            # Convert to RGBA PNG for OpenAI
            img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)

            result = client.images.edit(
                model="gpt-image-1",
                image=("image.png", buf.getvalue(), "image/png"),
                prompt=prompt,
                size="1024x1024",
            )
            image_bytes = base64.b64decode(result.data[0].b64_json)
            upgraded.append(image_bytes)
            ctx.log("info", f"  ✓ Image upgraded: {url.split('/')[-1]}")

        except Exception as e:
            ctx.log("warn", f"  ✗ Image failed ({url.split('/')[-1]}): {e}")

    return upgraded
