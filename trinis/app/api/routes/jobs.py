import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
import redis.asyncio as aioredis

from app.core.auth import get_current_tenant, check_sync_limit
from app.core.config import get_settings
from app.db.session import get_db
from app.models.models import Job, JobLog, JobStatus, Tenant, VendorConfig, ShopifyStore
from app.schemas.schemas import JobCreate, JobOut, JobLogOut, JobLogOut

settings = get_settings()
router = APIRouter(prefix="/jobs", tags=["jobs"])


def _get_redis():
    return aioredis.from_url(settings.redis_url, decode_responses=True)


# ─────────────────────────────────────────────
# List jobs (most recent first)
# ─────────────────────────────────────────────

@router.get("", response_model=list[JobOut])
async def list_jobs(
    limit: int = Query(50, le=200),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Job)
        .where(Job.tenant_id == tenant.id)
        .order_by(Job.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


# ─────────────────────────────────────────────
# Get single job
# ─────────────────────────────────────────────

@router.get("/{job_id}", response_model=JobOut)
async def get_job(
    job_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.tenant_id == tenant.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job




# ─────────────────────────────────────────────
# Worker health check
# ─────────────────────────────────────────────

@router.get("/workers/status")
async def workers_status(tenant: Tenant = Depends(get_current_tenant)):
    """Check if Celery workers are active."""
    try:
        from app.tasks.celery_app import celery_app
        inspect = celery_app.control.inspect(timeout=2.0)
        active = inspect.active()
        workers_online = bool(active)
        worker_count = len(active) if active else 0
        return {"online": workers_online, "count": worker_count}
    except Exception:
        return {"online": False, "count": 0}


# ─────────────────────────────────────────────
# Get stored logs for a completed job
# ─────────────────────────────────────────────

@router.get("/{job_id}/logs", response_model=list[JobLogOut])
async def get_job_logs(
    job_id: uuid.UUID,
    from_line: int = Query(0),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    # Verify job belongs to tenant
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.tenant_id == tenant.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Job not found")

    from app.models.models import JobLog
    logs_result = await db.execute(
        select(JobLog)
        .where(JobLog.job_id == job_id, JobLog.line_number >= from_line)
        .order_by(JobLog.line_number)
    )
    return [log.to_dict() for log in logs_result.scalars().all()]


# ─────────────────────────────────────────────
# Create / trigger a new job
# ─────────────────────────────────────────────

@router.post("", response_model=JobOut, status_code=201)
async def create_job(
    payload: JobCreate,
    tenant: Tenant = Depends(check_sync_limit),  # enforces plan limits
    db: AsyncSession = Depends(get_db),
):
    # Validate vendor config belongs to tenant
    vc_result = await db.execute(
        select(VendorConfig).where(
            VendorConfig.id == payload.vendor_config_id,
            VendorConfig.tenant_id == tenant.id,
            VendorConfig.is_active == True,
        )
    )
    if not vc_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Vendor config not found")

    # Validate store belongs to tenant
    store_result = await db.execute(
        select(ShopifyStore).where(
            ShopifyStore.id == payload.store_id,
            ShopifyStore.tenant_id == tenant.id,
            ShopifyStore.is_active == True,
        )
    )
    if not store_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Store not found or not connected")

    # Create job record
    job = Job(
        tenant_id=tenant.id,
        vendor_config_id=payload.vendor_config_id,
        store_id=payload.store_id,
        status=JobStatus.queued,
        product_limit=payload.product_limit,
        scheduled_at=payload.scheduled_at,
        skip_existing=payload.skip_existing,
    )
    db.add(job)
    await db.flush()
    await db.commit()

    # Enqueue Celery task — with ETA if scheduled
    from app.tasks.scrape import scrape_vendor
    eta = payload.scheduled_at if payload.scheduled_at else None
    task = scrape_vendor.apply_async(
        args=[str(job.id), str(tenant.id)],
        queue="scrape",
        eta=eta,
    )
    job.celery_task_id = task.id

    return job


# ─────────────────────────────────────────────
# Retry a failed job
# ─────────────────────────────────────────────

@router.post("/{job_id}/retry", response_model=JobOut, status_code=201)
async def retry_job(
    job_id: uuid.UUID,
    tenant: Tenant = Depends(check_sync_limit),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.tenant_id == tenant.id)
    )
    original = result.scalar_one_or_none()
    if not original:
        raise HTTPException(status_code=404, detail="Job not found")
    if original.status not in (JobStatus.failed, JobStatus.cancelled):
        raise HTTPException(status_code=400, detail="Only failed or cancelled jobs can be retried")

    new_job = Job(
        tenant_id=tenant.id,
        vendor_config_id=original.vendor_config_id,
        store_id=original.store_id,
        retry_of_job_id=original.id,
        attempt=original.attempt + 1,
        status=JobStatus.queued,
    )
    db.add(new_job)
    await db.flush()
    await db.commit()

    from app.tasks.scrape import scrape_vendor
    task = scrape_vendor.apply_async(
        args=[str(new_job.id), str(tenant.id)],
        queue="scrape",
    )
    new_job.celery_task_id = task.id

    return new_job


# ─────────────────────────────────────────────
# Stop a running job
# ─────────────────────────────────────────────

@router.post("/{job_id}/stop")
async def stop_job(
    job_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.tenant_id == tenant.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in (JobStatus.running, JobStatus.queued):
        raise HTTPException(status_code=400, detail="Job is not running")

    # Revoke Celery task
    if job.celery_task_id:
        from app.tasks.celery_app import celery_app
        celery_app.control.revoke(job.celery_task_id, terminate=True)

    job.status = JobStatus.cancelled
    job.finished_at = datetime.now(timezone.utc)

    return {"ok": True}


# ─────────────────────────────────────────────
# WebSocket — live log stream
# GET /jobs/{job_id}/logs/ws
# ─────────────────────────────────────────────

@router.websocket("/{job_id}/logs/ws")
async def job_log_stream(
    websocket: WebSocket,
    job_id: uuid.UUID,
    from_line: int = Query(0),
    token: str = Query(...),  # JWT passed as query param for WS
    db: AsyncSession = Depends(get_db),
):
    # Validate token manually (WS can't use headers easily)
    from app.core.auth import decode_token
    from app.models.models import User
    try:
        payload = decode_token(token)
        user_result = await db.execute(
            select(User).where(User.id == uuid.UUID(payload["sub"]))
        )
        user = user_result.scalar_one_or_none()
        if not user:
            await websocket.close(code=4001)
            return
    except Exception:
        await websocket.close(code=4001)
        return

    # Validate job belongs to user's tenant
    job_result = await db.execute(
        select(Job).where(Job.id == job_id, Job.tenant_id == user.tenant_id)
    )
    job = job_result.scalar_one_or_none()
    if not job:
        await websocket.close(code=4004)
        return

    await websocket.accept()

    # 1. Replay past log lines from DB (for reconnect support)
    past_logs = await db.execute(
        select(JobLog)
        .where(JobLog.job_id == job_id)
        .where(JobLog.line_number >= from_line)
        .order_by(JobLog.line_number)
    )
    for log_line in past_logs.scalars().all():
        await websocket.send_json(log_line.to_dict())

    # 2. Subscribe to live Redis pub/sub channel
    if job.status in (JobStatus.running, JobStatus.queued):
        redis = _get_redis()
        pubsub = redis.pubsub()
        await pubsub.subscribe(f"job:{job_id}:logs")
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    await websocket.send_json(json.loads(message["data"]))
        except WebSocketDisconnect:
            pass
        finally:
            await pubsub.unsubscribe(f"job:{job_id}:logs")
            await redis.aclose()
    else:
        await websocket.close()


# ─────────────────────────────────────────────
# Dashboard summary endpoint
# ─────────────────────────────────────────────

@router.get("/summary/dashboard")
async def dashboard_summary(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import extract
    now = datetime.now(timezone.utc)

    jobs_this_month = await db.execute(
        select(func.count(Job.id)).where(
            Job.tenant_id == tenant.id,
            extract("month", Job.created_at) == now.month,
            extract("year", Job.created_at) == now.year,
        )
    )
    failed_this_month = await db.execute(
        select(func.count(Job.id)).where(
            Job.tenant_id == tenant.id,
            Job.status == JobStatus.failed,
            extract("month", Job.created_at) == now.month,
            extract("year", Job.created_at) == now.year,
        )
    )
    running = await db.execute(
        select(func.count(Job.id)).where(
            Job.tenant_id == tenant.id,
            Job.status == JobStatus.running,
        )
    )
    last_sync = await db.execute(
        select(Job.finished_at)
        .where(Job.tenant_id == tenant.id, Job.status == JobStatus.done)
        .order_by(Job.finished_at.desc())
        .limit(1)
    )

    return {
        "products_synced_this_month": tenant.products_synced_this_month,
        "plan_limit": tenant.plan_limit,
        "plan": tenant.plan,
        "jobs_this_month": jobs_this_month.scalar() or 0,
        "jobs_failed_this_month": failed_this_month.scalar() or 0,
        "running_jobs": running.scalar() or 0,
        "last_sync_at": last_sync.scalar(),
    }
