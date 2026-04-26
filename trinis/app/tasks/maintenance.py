"""
Maintenance tasks — run via Celery Beat on schedule.

- reset_monthly_usage: resets product sync counters on the 1st of each month
- check_shopify_token_expiry: flags stores whose tokens are expiring soon
- trigger_scheduled_syncs: checks vendor cron expressions and fires sync jobs
"""
from datetime import datetime, timezone, timedelta

from app.tasks.celery_app import celery_app
from app.tasks.base import SyncSession
from app.models.models import Tenant, ShopifyStore, VendorConfig, Job, JobStatus


@celery_app.task(queue="default")
def reset_monthly_usage():
    """Reset products_synced_this_month for all tenants. Runs 1st of month."""
    db = SyncSession()
    try:
        tenants = db.query(Tenant).all()
        for tenant in tenants:
            tenant.products_synced_this_month = 0
            tenant.usage_reset_at = datetime.now(timezone.utc)
        db.commit()
        print(f"✓ Reset monthly usage for {len(tenants)} tenants")
    finally:
        db.close()


@celery_app.task(queue="default")
def check_shopify_token_expiry():
    """
    Flags stores whose access tokens expire within 7 days.
    Shopify permanent tokens don't actually expire, but this catches
    any stores that have been inactive or had their token revoked.
    """
    db = SyncSession()
    try:
        soon = datetime.now(timezone.utc) + timedelta(days=7)
        stores = db.query(ShopifyStore).filter(
            ShopifyStore.is_active == True,
            ShopifyStore.token_expires_at != None,
            ShopifyStore.token_expires_at <= soon,
        ).all()

        for store in stores:
            print(f"⚠️ Token expiring soon: {store.shop_domain}")
            # Could send email notification here

        print(f"✓ Token expiry check complete — {len(stores)} expiring soon")
    finally:
        db.close()


@celery_app.task(queue="default")
def trigger_scheduled_syncs():
    """
    Runs every 5 minutes. Checks each active VendorConfig's cron expression
    and fires a sync job if it's due.
    """
    from croniter import croniter

    db = SyncSession()
    try:
        configs = db.query(VendorConfig).filter(
            VendorConfig.is_active == True,
            VendorConfig.sync_schedule != None,
        ).all()

        now = datetime.now(timezone.utc)
        fired = 0

        for config in configs:
            if not config.sync_schedule:
                continue

            try:
                cron = croniter(config.sync_schedule, now - timedelta(minutes=5))
                next_run = cron.get_next(datetime)
                if next_run <= now:
                    _fire_sync_job(db, config)
                    fired += 1
            except Exception as e:
                print(f"⚠️ Bad cron for vendor {config.name}: {e}")

        if fired:
            print(f"✓ Triggered {fired} scheduled sync(s)")
    finally:
        db.close()


def _fire_sync_job(db, config: VendorConfig):
    """Create a queued Job and dispatch the Celery pipeline."""
    # Find the first active store for this tenant
    store = db.query(ShopifyStore).filter(
        ShopifyStore.tenant_id == config.tenant_id,
        ShopifyStore.is_active == True,
    ).first()

    if not store:
        print(f"⚠️ No active store for tenant {config.tenant_id} — skipping scheduled sync")
        return

    job = Job(
        tenant_id=config.tenant_id,
        vendor_config_id=config.id,
        store_id=store.id,
        status=JobStatus.queued,
    )
    db.add(job)
    db.flush()

    from app.tasks.scrape import scrape_vendor
    task = scrape_vendor.apply_async(
        args=[str(job.id), str(config.tenant_id)],
        queue="scrape",
    )
    job.celery_task_id = task.id
    db.commit()

    print(f"✓ Scheduled sync fired: {config.name} (job {job.id})")


@celery_app.task
def run_auto_backups():
    """Run automatic daily backups for Standard and Premium subscribers."""
    from datetime import datetime, timezone, timedelta
    from app.models.models import BackupSubscription, BackupSnapshot, ShopifyStore
    from sqlalchemy import select as sa_select

    with SyncSession() as db:
        # Get all active Standard/Premium subscriptions due for backup
        result = db.execute(
            sa_select(BackupSubscription).where(
                BackupSubscription.is_active == True,
                BackupSubscription.plan.in_(["standard", "premium"]),
            )
        )
        subs = result.scalars().all()

        for sub in subs:
            # Check if already ran today
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            recent = db.execute(
                sa_select(BackupSnapshot).where(
                    BackupSnapshot.tenant_id == sub.tenant_id,
                    BackupSnapshot.trigger == "auto",
                    BackupSnapshot.created_at >= today_start,
                )
            ).scalar_one_or_none()

            if recent:
                continue  # Already backed up today

            # Get active store
            store_result = db.execute(
                sa_select(ShopifyStore).where(
                    ShopifyStore.tenant_id == sub.tenant_id,
                    ShopifyStore.is_active == True,
                )
            ).scalars().first()

            if not store_result:
                continue

            # Create snapshot record
            snapshot = BackupSnapshot(
                tenant_id=sub.tenant_id,
                store_id=store_result.id,
                status="pending",
                trigger="auto",
            )
            db.add(snapshot)
            db.flush()
            db.commit()

            # Dispatch backup task
            from app.tasks.backup import run_backup
            run_backup.apply_async(
                args=[str(snapshot.id), str(sub.tenant_id)],
                queue="default",
            )
            print(f"✓ Auto backup triggered for tenant {sub.tenant_id}")


@celery_app.task
def cleanup_expired_backups():
    """Delete backup snapshots older than the plan retention period."""
    from datetime import datetime, timezone, timedelta
    from app.models.models import BackupSubscription, BackupSnapshot
    from sqlalchemy import select as sa_select
    import boto3
    from botocore.client import Config

    RETENTION = {"basic": 7, "standard": 30, "premium": 90}

    with SyncSession() as db:
        result = db.execute(
            sa_select(BackupSubscription).where(BackupSubscription.is_active == True)
        )
        subs = result.scalars().all()

        s3 = boto3.client(
            "s3",
            endpoint_url=settings.minio_endpoint_url,
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )

        for sub in subs:
            days = RETENTION.get(sub.plan, 7)
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)

            expired = db.execute(
                sa_select(BackupSnapshot).where(
                    BackupSnapshot.tenant_id == sub.tenant_id,
                    BackupSnapshot.created_at < cutoff,
                    BackupSnapshot.status == "done",
                )
            ).scalars().all()

            for snap in expired:
                # Delete from MinIO
                if snap.minio_key:
                    try:
                        s3.delete_object(Bucket="productsync-backups", Key=snap.minio_key)
                    except Exception as e:
                        print(f"⚠️ MinIO delete failed: {e}")
                db.delete(snap)
                print(f"✓ Deleted expired backup {snap.id} ({days}d retention)")

            db.commit()
