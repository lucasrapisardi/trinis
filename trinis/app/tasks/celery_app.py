from celery import Celery
from celery.schedules import crontab
from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "productsync",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.scrape",
        "app.tasks.enrich",
        "app.tasks.image",
        "app.tasks.sync",
        "app.tasks.sku",
        "app.tasks.tags",
        "app.tasks.pricing",
        "app.tasks.maintenance",
        "app.tasks.backup",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    task_default_retry_delay=30,  # reduced from 60s

    # Route tasks to specific queues
    task_routes={
        "app.tasks.scrape.*":      {"queue": "scrape"},
        "app.tasks.enrich.*":      {"queue": "enrich"},
        "app.tasks.image.*":       {"queue": "image"},
        "app.tasks.sync.*":        {"queue": "sync"},
        "app.tasks.sku.*":         {"queue": "sync"},
        "app.tasks.tags.*":        {"queue": "sync"},
        "app.tasks.pricing.*":     {"queue": "sync"},
        "app.tasks.maintenance.*": {"queue": "default"},
        "app.tasks.backup.*":     {"queue": "default"},
    },

    # Retry defaults
    task_max_retries=3,

    # Beat schedule — runs maintenance tasks
    beat_schedule={
        "reset-monthly-usage": {
            "task": "app.tasks.maintenance.reset_monthly_usage",
            "schedule": crontab(hour=0, minute=0, day_of_month=1),
        },
        "check-token-expiry": {
            "task": "app.tasks.maintenance.check_shopify_token_expiry",
            "schedule": crontab(hour=6, minute=0),  # daily at 6am UTC
        },
        "run-scheduled-syncs": {
            "task": "app.tasks.maintenance.trigger_scheduled_syncs",
            "schedule": crontab(minute="*/5"),  # every 5 min, checks cron expressions
        },
        "run-auto-backups": {
            "task": "app.tasks.maintenance.run_auto_backups",
            "schedule": crontab(hour=2, minute=0),  # daily at 2am UTC
        },
        "cleanup-expired-backups": {
            "task": "app.tasks.maintenance.cleanup_expired_backups",
            "schedule": crontab(hour=3, minute=0),  # daily at 3am UTC
        },
    },
)
