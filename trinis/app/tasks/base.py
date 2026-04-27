"""
Base Celery task that every pipeline task inherits from.

Provides:
- Sync SQLAlchemy session (Celery workers are sync)
- log() helper that writes to DB + publishes to Redis pub/sub
- Job state transitions (start, finish, fail)
"""
import json
import uuid
from datetime import datetime, timezone

from celery import Task
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
import redis

from app.core.config import get_settings
from app.models.models import Job, JobLog, JobStatus, LogLevel, Tenant

settings = get_settings()

# Sync engine for Celery workers (asyncpg → psycopg2)
_sync_db_url = settings.database_url.replace("+asyncpg", "")
_engine = create_engine(_sync_db_url, pool_pre_ping=True, pool_size=5)
SyncSession = sessionmaker(bind=_engine, autocommit=False, autoflush=False)

_redis_client = redis.from_url(settings.redis_url, decode_responses=True)


class JobTask(Task):
    """
    Base task class. All pipeline tasks should inherit from this.

    Usage:
        @celery_app.task(bind=True, base=JobTask)
        def my_task(self, job_id: str, tenant_id: str):
            with self.job_context(job_id) as ctx:
                ctx.log("info", "Starting...")
                # do work
    """

    abstract = True

    def job_context(self, job_id: str):
        return _JobContext(job_id, self)


class _JobContext:
    def __init__(self, job_id: str, task: Task):
        self.job_id = uuid.UUID(job_id)
        self.task = task
        self.db: Session | None = None
        self.job: Job | None = None
        self._line_counter = 0

    def __enter__(self):
        self.db = SyncSession()
        self.job = self.db.get(Job, self.job_id)
        if not self.job:
            raise ValueError(f"Job {self.job_id} not found")

        self.job.status = JobStatus.running
        self.job.started_at = datetime.now(timezone.utc)
        self.job.celery_task_id = self.task.request.id
        self.db.commit()

        # Seed line counter from existing logs
        from sqlalchemy import func, select
        result = self.db.execute(
            select(func.max(JobLog.line_number)).where(JobLog.job_id == self.job_id)
        )
        self._line_counter = (result.scalar() or 0) + 1

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.db:
            self.db.close()

    def log(self, level: str, message: str):
        """Write a log line to DB and publish to Redis pub/sub."""
        log_entry = JobLog(
            job_id=self.job_id,
            line_number=self._line_counter,
            level=LogLevel(level),
            message=message,
        )
        self.db.add(log_entry)
        self.db.commit()

        # Publish to Redis for live WebSocket clients
        payload = json.dumps({
            "line": self._line_counter,
            "level": level,
            "message": message,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        _redis_client.publish(f"job:{self.job_id}:logs", payload)
        self._line_counter += 1

        # Print to Celery worker stdout (visible in Flower)
        print(f"[{level.upper()}] {message}")

    def update_progress(self, scraped=0, enriched=0, pushed=0, failed=0, pct=0):
        """Update job progress counters."""
        if not self.job:
            return
        self.job.products_scraped = scraped
        self.job.products_enriched = enriched
        self.job.products_pushed = pushed
        self.job.products_failed = failed
        self.job.progress_pct = pct
        self.db.commit()

    def finish(self):
        """Mark job as done."""
        self.job.status = JobStatus.done
        self.job.finished_at = datetime.now(timezone.utc)
        self.job.progress_pct = 100
        self.db.commit()

        # Increment tenant's monthly usage counter + debit credits if over limit
        from app.models.models import Tenant
        from app.services.credits import debit_credits
        tenant = self.db.get(Tenant, self.job.tenant_id)
        if tenant:
            pushed = self.job.products_pushed
            before = tenant.products_synced_this_month
            limit = tenant.plan_limit
            tenant.products_synced_this_month += pushed
            self.db.commit()
            # Debit credits for products that exceeded the plan limit
            over_limit = max(0, (before + pushed) - limit)
            if over_limit > 0:
                debited = debit_credits(
                    self.db, tenant.id,
                    operation="product_enrich",
                    quantity=over_limit,
                    reference_id=str(self.job_id),
                )
                if debited:
                    self.log("info", f"Debited {over_limit} credits for {over_limit} products over plan limit")
                else:
                    self.log("warn", f"Could not debit {over_limit} credits — balance may be insufficient")

        # Close WebSocket channel
        _redis_client.publish(
            f"job:{self.job_id}:logs",
            json.dumps({"type": "done", "ts": datetime.now(timezone.utc).isoformat()}),
        )

    def fail(self, error: str):
        """Mark job as failed."""
        self.job.status = JobStatus.failed
        self.job.finished_at = datetime.now(timezone.utc)
        self.job.error_message = error
        self.db.commit()

        self.log("error", f"Job failed: {error}")

        _redis_client.publish(
            f"job:{self.job_id}:logs",
            json.dumps({"type": "failed", "error": error, "ts": datetime.now(timezone.utc).isoformat()}),
        )

    def finish_with_errors(self, error_summary: dict):
        """Mark job as done but with partial errors."""
        import json as _json
        self.job.status = JobStatus.done_with_errors
        self.job.finished_at = datetime.now(timezone.utc)
        self.job.progress_pct = 100
        self.job.error_summary = _json.dumps(error_summary)
        self.db.commit()

        # Increment tenant usage for successfully pushed products + debit credits if over limit
        from app.models.models import Tenant
        from app.services.credits import debit_credits
        tenant = self.db.get(Tenant, self.job.tenant_id)
        if tenant:
            pushed = self.job.products_pushed
            before = tenant.products_synced_this_month
            limit = tenant.plan_limit
            tenant.products_synced_this_month += pushed
            self.db.commit()
            over_limit = max(0, (before + pushed) - limit)
            if over_limit > 0:
                debit_credits(
                    self.db, tenant.id,
                    operation="product_enrich",
                    quantity=over_limit,
                    reference_id=str(self.job_id),
                )

        summary_msg = f"Completed with errors — pushed: {error_summary.get('pushed', 0)}, failed: {error_summary.get('failed', 0)}"
        self.log("warn", summary_msg)

        _redis_client.publish(
            f"job:{self.job_id}:logs",
            json.dumps({"type": "done_with_errors", "summary": error_summary, "ts": datetime.now(timezone.utc).isoformat()}),
        )
