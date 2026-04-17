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
