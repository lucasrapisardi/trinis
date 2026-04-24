"""
Image upgrade task — parallel gpt-image-1 with MD5 hash skip.
Uses queue-based logging to avoid SQLAlchemy thread-safety issues.
"""
import base64
import concurrent.futures
import io
import queue
import time

import requests
from openai import OpenAI
from PIL import Image

from app.tasks.celery_app import celery_app
from app.tasks.base import JobTask
from app.models.models import VendorConfig
from app.core.config import get_settings
from app.services.storage import upload_image
from app.services.ean_cache import get_cached, set_cached

settings = get_settings()
MAX_WORKERS = 2


@celery_app.task(bind=True, base=JobTask, queue="image", max_retries=3)
def upgrade_images(self, job_id: str, tenant_id: str, products: list[dict]):
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

            owner = db.execute(
                sa_select(User).where(User.tenant_id == job.tenant_id, User.is_owner == True)
            ).scalar_one_or_none()
            locale = getattr(owner, "locale", "pt") if owner else "pt"

            store_result = db.execute(
                sa_select(ShopifyStore).where(ShopifyStore.id == job.store_id)
            ).scalar_one_or_none()
            store_id = str(store_result.id) if store_result else "unknown"

            image_prompt = config.image_style_prompt or _default_image_prompt(locale)
            total = len(products)

            ctx.log("info", f"Upgrading images for {total} products (parallel={MAX_WORKERS}, hash-skip enabled)...")

            log_queue = queue.Queue()
            completed = [0]
            image_errors = [0]
            skipped = [0]

            def upgrade_one(item):
                i, product = item
                ean = product.get("ean", "")
                image_hash = product.get("image_hash")

                # Hash skip
                if image_hash:
                    cached = get_cached(tenant_id, store_id, ean)
                    if cached and cached.get("image_hash") == image_hash and cached.get("minio_keys"):
                        log_queue.put(("info", f"  ⏭ Skipped [{i+1}/{total}] {product['nome'][:40]} (image unchanged)"))
                        skipped[0] += 1
                        completed[0] += 1
                        product["upgraded_images"] = []
                        product["minio_keys"] = cached["minio_keys"]
                        return i, product

                if not product.get("images"):
                    log_queue.put(("warn", f"  No images for {product['nome'][:40]} — skipping"))
                    product["upgraded_images"] = []
                    product["image_error"] = "No images available"
                    image_errors[0] += 1
                    completed[0] += 1
                    return i, product

                log_queue.put(("info", f"  Processing [{i+1}/{total}]: {product['nome'][:40]}"))
                upgraded = _upgrade_product_images(client, product["images"], image_prompt)

                minio_keys = []
                for idx, img_bytes in enumerate(upgraded):
                    try:
                        key = upload_image(
                            image_bytes=img_bytes,
                            tenant_id=tenant_id,
                            ean=ean,
                            index=idx,
                        )
                        minio_keys.append(key)
                    except Exception as e:
                        log_queue.put(("warn", f"    ✗ MinIO upload failed: {e}"))

                product["upgraded_images"] = upgraded
                product["minio_keys"] = minio_keys

                if not upgraded:
                    product["image_error"] = "Image upgrade failed"
                    image_errors[0] += 1
                else:
                    set_cached(tenant_id, store_id, ean, {
                        "image_hash": image_hash,
                        "minio_keys": minio_keys,
                        "enriched_description": product.get("enriched_description", ""),
                    })
                    log_queue.put(("info", f"  ✓ Done [{i+1}/{total}]: {len(minio_keys)} images stored"))

                completed[0] += 1
                time.sleep(0.2)
                return i, product

            result_map = {}
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = {
                    executor.submit(upgrade_one, (i, product)): i
                    for i, product in enumerate(products)
                }
                for future in concurrent.futures.as_completed(futures):
                    try:
                        i, product = future.result()
                        result_map[i] = product
                    except Exception as e:
                        idx = futures[future]
                        log_queue.put(("warn", f"  ✗ Unexpected error product {idx}: {e}"))
                        result_map[idx] = products[idx]

            products_out = [result_map[i] for i in range(len(products))]

            # Drain log queue on main thread (thread-safe DB writes)
            while not log_queue.empty():
                level, msg = log_queue.get_nowait()
                ctx.log(level, msg)

            ctx.update_progress(enriched=total, pct=83)
            ctx.log("info", f"Image upgrade complete — {skipped[0]} skipped, {image_errors[0]} failed, {total - image_errors[0] - skipped[0]} upgraded")

            from app.tasks.sync import push_to_shopify
            push_to_shopify.apply_async(
                args=[job_id, tenant_id, products_out],
                queue="sync",
            )

        except Exception as e:
            ctx.fail(str(e))
            raise self.retry(exc=e, countdown=60)


def _upgrade_product_images(client, image_urls, prompt) -> list[bytes]:
    upgraded = []
    for url in image_urls[:3]:
        try:
            resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            result = client.with_options(timeout=120.0).images.edit(
                model="gpt-image-1",
                image=("image.png", buf.getvalue(), "image/png"),
                prompt=prompt,
                size="1024x1024",
            )
            image_bytes = base64.b64decode(result.data[0].b64_json)
            upgraded.append(image_bytes)
        except Exception:
            pass
    return upgraded


def _default_image_prompt(locale: str = "pt") -> str:
    prompts = {
        "pt": "Transforme esta imagem de produto em foto profissional de alta resolução. NÃO altere o produto. Substitua fundo branco/neutro por: superfície de pedra clara em tons de bege e areia, iluminação natural suave. Remova marcas d'água. Estilo: fotografia de produto profissional.",
        "en": "Transform this product image into a professional high-resolution photo. DO NOT alter the product. Replace white/neutral background with: light stone surface in beige and sand tones, soft natural lighting. Remove watermarks. Style: professional product photography.",
        "es": "Transforma esta imagen de producto en foto profesional de alta resolución. NO alteres el producto. Reemplaza fondo blanco/neutro con: superficie de piedra clara en tonos beige y arena, iluminación natural suave. Elimina marcas de agua. Estilo: fotografía de producto profesional.",
    }
    return prompts.get(locale) or prompts["pt"]
