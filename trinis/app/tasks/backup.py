# PATH: /home/lumoura/trinis_ai/trinis/app/tasks/backup.py
"""
Backup task — collects all products from Shopify and stores
as a JSON snapshot in MinIO.
"""
import json
import uuid
from datetime import datetime, timezone

import requests

from app.tasks.celery_app import celery_app
from app.core.config import get_settings
from app.core.encryption import decrypt_token
from app.tasks.base import SyncSession
from app.models.models import BackupSnapshot, BackupStatus, ShopifyStore

settings = get_settings()


@celery_app.task(bind=True, queue="default", max_retries=2)
def run_backup(self, snapshot_id: str, tenant_id: str):
    """Collect all Shopify products and store as JSON in MinIO."""
    with SyncSession() as db:
        snapshot = db.get(BackupSnapshot, uuid.UUID(snapshot_id))
        if not snapshot:
            return

        snapshot.status = BackupStatus.running
        db.commit()

        try:
            store = db.get(ShopifyStore, snapshot.store_id)
            if not store:
                raise ValueError("Store not found")

            access_token = decrypt_token(store.encrypted_access_token)
            base_url = f"https://{store.shop_domain}/admin/api/{settings.shopify_api_version}"
            headers = {"X-Shopify-Access-Token": access_token}

            # Fetch all products with pagination
            all_products = []
            params = {"limit": 250}
            while True:
                resp = requests.get(
                    f"{base_url}/products.json",
                    headers=headers,
                    params=params,
                    timeout=30,
                )
                resp.raise_for_status()
                products = resp.json().get("products", [])
                all_products.extend(products)

                import re
                link = resp.headers.get("Link", "")
                if 'rel="next"' not in link:
                    break
                next_url = re.search(r'<([^>]+)>;\s*rel="next"', link)
                if not next_url:
                    break
                params = {"page_info": next_url.group(1).split("page_info=")[-1], "limit": 250}

            # Build snapshot payload
            payload = {
                "snapshot_id": snapshot_id,
                "tenant_id": tenant_id,
                "store_domain": store.shop_domain,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "product_count": len(all_products),
                "products": all_products,
            }

            json_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")

            # Upload to MinIO via boto3
            import boto3
            from botocore.client import Config
            s3 = boto3.client(
                "s3",
                endpoint_url=settings.minio_endpoint_url,
                aws_access_key_id=settings.minio_access_key,
                aws_secret_access_key=settings.minio_secret_key,
                config=Config(signature_version="s3v4"),
                region_name="us-east-1",
            )
            bucket = "productsync-backups"
            try:
                s3.head_bucket(Bucket=bucket)
            except Exception:
                s3.create_bucket(Bucket=bucket)

            minio_key = f"{tenant_id}/backups/{snapshot_id}.json"
            import io
            s3.put_object(
                Bucket=bucket,
                Key=minio_key,
                Body=json_bytes,
                ContentType="application/json",
            )

            snapshot.status = BackupStatus.done
            snapshot.product_count = len(all_products)
            snapshot.file_size_bytes = len(json_bytes)
            snapshot.minio_key = minio_key
            snapshot.completed_at = datetime.now(timezone.utc)
            db.commit()

        except Exception as e:
            snapshot.status = BackupStatus.failed
            snapshot.error_message = str(e)
            snapshot.completed_at = datetime.now(timezone.utc)
            db.commit()
            raise self.retry(exc=e, countdown=60)


@celery_app.task(bind=True, queue="default", max_retries=2)
def restore_backup(self, snapshot_id: str, tenant_id: str, mode: str = "all"):
    """
    Restore products from a backup snapshot to Shopify.
    mode: "all" = update all products, "new_only" = only products not in Shopify
    """
    with SyncSession() as db:
        from app.models.models import BackupSnapshot, BackupStatus, ShopifyStore
        import json, boto3, io, requests
        from botocore.client import Config
        from app.core.encryption import decrypt_token

        snapshot = db.get(BackupSnapshot, uuid.UUID(snapshot_id))
        if not snapshot:
            return

        try:
            # Download JSON from MinIO
            s3 = boto3.client(
                "s3",
                endpoint_url=settings.minio_endpoint_url,
                aws_access_key_id=settings.minio_access_key,
                aws_secret_access_key=settings.minio_secret_key,
                config=Config(signature_version="s3v4"),
                region_name="us-east-1",
            )
            obj = s3.get_object(Bucket="productsync-backups", Key=snapshot.minio_key)
            data = json.loads(obj["Body"].read().decode("utf-8"))
            products = data.get("products", [])

            # Get store
            store = db.get(ShopifyStore, snapshot.store_id)
            if not store:
                raise ValueError("Store not found")

            access_token = decrypt_token(store.encrypted_access_token)
            base_url = f"https://{store.shop_domain}/admin/api/{settings.shopify_api_version}"
            headers = {
                "X-Shopify-Access-Token": access_token,
                "Content-Type": "application/json",
            }

            # Get existing product IDs from Shopify if mode is new_only
            existing_ids = set()
            if mode == "new_only":
                params = {"limit": 250, "fields": "id"}
                while True:
                    resp = requests.get(f"{base_url}/products.json", headers=headers, params=params, timeout=30)
                    resp.raise_for_status()
                    for p in resp.json().get("products", []):
                        existing_ids.add(str(p["id"]))
                    import re
                    link = resp.headers.get("Link", "")
                    if 'rel="next"' not in link:
                        break
                    next_url = re.search(r'<([^>]+)>;\s*rel="next"', link)
                    if not next_url:
                        break
                    params = {"page_info": next_url.group(1).split("page_info=")[-1], "limit": 250}

            pushed, skipped, failed = 0, 0, 0
            for product in products:
                product_id = str(product.get("id", ""))
                if mode == "new_only" and product_id in existing_ids:
                    skipped += 1
                    continue
                try:
                    payload = {
                        "product": {
                            "title": product.get("title", ""),
                            "body_html": product.get("body_html", ""),
                            "vendor": product.get("vendor", ""),
                            "product_type": product.get("product_type", ""),
                            "tags": product.get("tags", ""),
                            "status": product.get("status", "active"),
                            "variants": product.get("variants", []),
                        }
                    }
                    if product_id and product_id in existing_ids or mode == "all":
                        # Try update first
                        resp = requests.put(
                            f"{base_url}/products/{product_id}.json",
                            headers=headers,
                            json=payload,
                            timeout=30,
                        )
                        if resp.status_code == 404:
                            # Product deleted — recreate
                            resp = requests.post(f"{base_url}/products.json", headers=headers, json=payload, timeout=30)
                    else:
                        resp = requests.post(f"{base_url}/products.json", headers=headers, json=payload, timeout=30)
                    resp.raise_for_status()
                    pushed += 1
                except Exception as e:
                    failed += 1
                    print(f"⚠️ Restore failed for {product.get('title')}: {e}")

            print(f"✓ Restore complete — {pushed} pushed, {skipped} skipped, {failed} failed")

        except Exception as e:
            raise self.retry(exc=e, countdown=60)
