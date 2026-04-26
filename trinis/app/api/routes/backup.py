# PATH: /home/lumoura/trinis_ai/trinis/app/api/routes/backup.py
"""
Backup add-on routes.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.auth import get_current_user, get_current_tenant
from app.core.config import get_settings
settings = get_settings()
from app.db.session import get_db
from app.models.models import (
    BackupSnapshot, BackupSubscription, BackupStatus,
    BackupPlanName, ShopifyStore, Tenant, User, PlanName
)

router = APIRouter(prefix="/backup", tags=["backup"])

BACKUP_PLAN_LIMITS = {
    "basic":    {"max_snapshots": 5,  "retention_days": 7,  "auto": False},
    "standard": {"max_snapshots": 30, "retention_days": 30, "auto": True},
    "premium":  {"max_snapshots": None, "retention_days": 90, "auto": True},
}

BACKUP_PRICES = {
    "basic":    {"price": 9,  "label": "Basic",    "description": "Manual backups, 7-day retention, up to 5 snapshots"},
    "standard": {"price": 19, "label": "Standard", "description": "Manual + daily auto, 30-day retention, up to 30 snapshots"},
    "premium":  {"price": 39, "label": "Premium",  "description": "Manual + daily auto, 90-day retention, unlimited snapshots"},
}


def _require_backup_eligible(tenant: Tenant):
    """Backup is available for Starter and above."""
    if tenant.plan in (PlanName.free, PlanName.cancelled):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "plan_upgrade_required",
                "message": "Backup add-on is available on Starter and above plans.",
                "upgrade_url": "/billing",
            }
        )


# ── Get backup status ─────────────────────────────────────────────────────

@router.get("/status")
async def get_backup_status(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BackupSubscription).where(BackupSubscription.tenant_id == tenant.id)
    )
    sub = result.scalar_one_or_none()

    snapshots_result = await db.execute(
        select(BackupSnapshot)
        .where(BackupSnapshot.tenant_id == tenant.id)
        .order_by(BackupSnapshot.created_at.desc())
        .limit(20)
    )
    snapshots = snapshots_result.scalars().all()

    return {
        "subscription": {
            "active": sub.is_active if sub else False,
            "plan": sub.plan if sub else None,
            "next_auto_backup_at": sub.next_auto_backup_at.isoformat() if sub and sub.next_auto_backup_at else None,
        } if sub else None,
        "plans": BACKUP_PRICES,
        "snapshots": [
            {
                "id": str(s.id),
                "status": s.status,
                "trigger": s.trigger,
                "product_count": s.product_count,
                "file_size_bytes": s.file_size_bytes,
                "created_at": s.created_at.isoformat(),
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                "error_message": s.error_message,
            }
            for s in snapshots
        ],
    }


# ── Activate backup add-on ────────────────────────────────────────────────

@router.post("/subscribe/{plan}")
async def subscribe_backup(
    plan: BackupPlanName,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_backup_eligible(tenant)

    import stripe
    stripe.api_key = settings.stripe_secret_key

    price_map = {
        "basic":    settings.stripe_backup_basic_price_id,
        "standard": settings.stripe_backup_standard_price_id,
        "premium":  settings.stripe_backup_premium_price_id,
    }
    plan_str = plan.value if hasattr(plan, "value") else str(plan)
    price_id = price_map.get(plan_str)
    if not price_id:
        raise HTTPException(status_code=400, detail="Invalid backup plan")

    # Get or create Stripe customer
    customer_id = tenant.stripe_customer_id
    if not customer_id:
        customer = stripe.Customer.create(
            email=current_user.email,
            name=tenant.name,
            metadata={"tenant_id": str(tenant.id)},
        )
        customer_id = customer.id
        tenant.stripe_customer_id = customer_id
        await db.flush()

    # Create checkout session
    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        success_url=f"{settings.app_base_url}/backup?backup_success=1",
        cancel_url=f"{settings.app_base_url}/backup",
        metadata={
            "tenant_id": str(tenant.id),
            "backup_plan": plan_str,
            "type": "backup_addon",
        },
    )
    await db.commit()
    return {"checkout_url": session.url}


# ── Trigger manual backup ─────────────────────────────────────────────────

@router.post("/run/{store_id}")
async def trigger_backup(
    store_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_backup_eligible(tenant)

    # Check subscription
    result = await db.execute(
        select(BackupSubscription).where(
            BackupSubscription.tenant_id == tenant.id,
            BackupSubscription.is_active == True,
        )
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=402, detail={"code": "no_backup_subscription", "message": "Subscribe to a backup plan first."})

    # Check snapshot limit
    limits = BACKUP_PLAN_LIMITS.get(sub.plan, BACKUP_PLAN_LIMITS["basic"])
    if limits["max_snapshots"]:
        count_result = await db.execute(
            select(BackupSnapshot).where(
                BackupSnapshot.tenant_id == tenant.id,
                BackupSnapshot.status == BackupStatus.done,
            )
        )
        count = len(count_result.scalars().all())
        if count >= limits["max_snapshots"]:
            raise HTTPException(
                status_code=402,
                detail={"code": "snapshot_limit_reached", "message": f"Your backup plan allows up to {limits['max_snapshots']} snapshots. Upgrade or delete old backups."}
            )

    # Verify store belongs to tenant
    store_result = await db.execute(
        select(ShopifyStore).where(
            ShopifyStore.id == store_id,
            ShopifyStore.tenant_id == tenant.id,
            ShopifyStore.is_active == True,
        )
    )
    store = store_result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    # Create snapshot record
    snapshot = BackupSnapshot(
        tenant_id=tenant.id,
        store_id=store_id,
        status=BackupStatus.pending,
        trigger="manual",
    )
    db.add(snapshot)
    await db.flush()
    await db.commit()

    # Dispatch Celery task
    from app.tasks.backup import run_backup
    run_backup.apply_async(
        args=[str(snapshot.id), str(tenant.id)],
        queue="default",
    )

    return {"ok": True, "snapshot_id": str(snapshot.id)}


# ── Download backup ───────────────────────────────────────────────────────

@router.get("/download/{snapshot_id}")
async def download_backup(
    snapshot_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BackupSnapshot).where(
            BackupSnapshot.id == snapshot_id,
            BackupSnapshot.tenant_id == tenant.id,
            BackupSnapshot.status == BackupStatus.done,
        )
    )
    snapshot = result.scalar_one_or_none()
    if not snapshot or not snapshot.minio_key:
        raise HTTPException(status_code=404, detail="Backup not found")

    # Stream file from MinIO through backend
    import boto3
    from botocore.client import Config
    from fastapi.responses import StreamingResponse
    s3 = boto3.client(
        "s3",
        endpoint_url=settings.minio_endpoint_url,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )
    obj = s3.get_object(Bucket="productsync-backups", Key=snapshot.minio_key)
    filename = f"backup-{snapshot_id}.json"
    return StreamingResponse(
        obj["Body"].iter_chunks(),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Delete backup ─────────────────────────────────────────────────────────

@router.delete("/{snapshot_id}")
async def delete_backup(
    snapshot_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BackupSnapshot).where(
            BackupSnapshot.id == snapshot_id,
            BackupSnapshot.tenant_id == tenant.id,
        )
    )
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Backup not found")

    # Delete from MinIO
    if snapshot.minio_key:
        try:
            from app.services.storage import get_minio_client
            client = get_minio_client()
            client.remove_object("productsync-backups", snapshot.minio_key)
        except Exception:
            pass

    await db.delete(snapshot)
    await db.commit()
    return {"ok": True}


# ── Cancel backup subscription ────────────────────────────────────────────

@router.post("/cancel")
async def cancel_backup(
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BackupSubscription).where(BackupSubscription.tenant_id == tenant.id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="No active backup subscription")

    # Cancel on Stripe if has subscription
    if sub.stripe_subscription_id:
        try:
            import stripe
            stripe.api_key = settings.stripe_secret_key
            stripe.Subscription.cancel(sub.stripe_subscription_id)
        except Exception as e:
            print(f"⚠️ Failed to cancel Stripe subscription: {e}")

    sub.is_active = False
    sub.stripe_subscription_id = None
    await db.commit()
    return {"ok": True, "message": "Backup subscription cancelled"}


# ── Change backup plan ────────────────────────────────────────────────────

@router.put("/subscribe/{plan}")
async def change_backup_plan(
    plan: BackupPlanName,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_backup_eligible(tenant)

    result = await db.execute(
        select(BackupSubscription).where(BackupSubscription.tenant_id == tenant.id)
    )
    sub = result.scalar_one_or_none()
    if not sub or not sub.is_active:
        raise HTTPException(status_code=404, detail="No active backup subscription")

    sub.plan = plan.value if hasattr(plan, "value") else plan
    await db.commit()
    return {"ok": True, "plan": sub.plan}


# ── Restore backup ────────────────────────────────────────────────────────

@router.post("/restore/{snapshot_id}")
async def restore_backup_endpoint(
    snapshot_id: uuid.UUID,
    mode: str = "all",
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Restore products from a snapshot.
    mode: "all" = restore all products, "new_only" = only missing products
    """
    result = await db.execute(
        select(BackupSnapshot).where(
            BackupSnapshot.id == snapshot_id,
            BackupSnapshot.tenant_id == tenant.id,
            BackupSnapshot.status == "done",
        )
    )
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    from app.tasks.backup import restore_backup
    restore_backup.apply_async(
        args=[str(snapshot_id), str(tenant.id), mode],
        queue="default",
    )
    return {"ok": True, "message": f"Restore started in {mode} mode"}
