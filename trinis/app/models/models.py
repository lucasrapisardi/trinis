import uuid
import enum
from datetime import datetime
from sqlalchemy import (
    String, Text, Boolean, DateTime, Integer, Float,
    ForeignKey, Enum as SAEnum, JSON, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base


# ─────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────

class PlanName(str, enum.Enum):
    free = "free"
    starter = "starter"
    pro = "pro"
    business = "business"
    cancelled = "cancelled"


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    done = "done"
    done_with_errors = "done_with_errors"
    failed = "failed"
    cancelled = "cancelled"


class LogLevel(str, enum.Enum):
    info = "info"
    warn = "warn"
    error = "error"


# ─────────────────────────────────────────────
# Tenant  (one per paying customer / workspace)
# ─────────────────────────────────────────────

class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)

    # Billing
    plan: Mapped[PlanName] = mapped_column(
        SAEnum(PlanName), default=PlanName.free, nullable=False
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(64))
    payment_past_due: Mapped[bool] = mapped_column(Boolean, default=False)

    # Usage — reset monthly via Celery Beat
    products_synced_this_month: Mapped[int] = mapped_column(Integer, default=0)
    usage_reset_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )

    # Meta
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    users: Mapped[list["User"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    stores: Mapped[list["ShopifyStore"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    vendor_configs: Mapped[list["VendorConfig"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    jobs: Mapped[list["Job"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")

    @property
    def plan_limit(self) -> int:
        limits = {
            PlanName.free: 30,
            PlanName.starter: 300,
            PlanName.pro: 1000,
            PlanName.business: 4000,
            PlanName.cancelled: 0,
        }
        return limits[self.plan]

    @property
    def user_limit(self) -> int:
        limits = {
            PlanName.free: 1,
            PlanName.starter: 1,
            PlanName.pro: 5,
            PlanName.business: 20,
            PlanName.cancelled: 0,
        }
        return limits[self.plan]

    # Credits
    credits_balance: Mapped[int] = mapped_column(Integer, default=0)
    # Bulk enhance counter
    images_enhanced_this_month: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<Tenant {self.slug} ({self.plan})>"


# ─────────────────────────────────────────────
# User  (belongs to one Tenant)
# ─────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(120))
    locale: Mapped[str] = mapped_column(String(5), default="en")  # en, pt, es
    tour_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_owner: Mapped[bool] = mapped_column(Boolean, default=False)
    email_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)  # tenant owner

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tenant: Mapped["Tenant"] = relationship(back_populates="users")

    def __repr__(self) -> str:
        return f"<User {self.email}>"


# ─────────────────────────────────────────────
# ShopifyStore  (one Tenant can have many stores)
# ─────────────────────────────────────────────

class ShopifyStore(Base):
    __tablename__ = "shopify_stores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    shop_domain: Mapped[str] = mapped_column(String(120), unique=True, index=True)  # e.g. acme.myshopify.com

    # Token stored AES-encrypted — never plaintext
    encrypted_access_token: Mapped[str] = mapped_column(Text)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    webhooks_registered: Mapped[bool] = mapped_column(Boolean, default=False)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tenant: Mapped["Tenant"] = relationship(back_populates="stores")

    def __repr__(self) -> str:
        return f"<ShopifyStore {self.shop_domain}>"


# ─────────────────────────────────────────────
# VendorConfig  (one per vendor source per Tenant)
# Maps to your scraper.py config fields
# ─────────────────────────────────────────────

class VendorConfig(Base):
    __tablename__ = "vendor_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )

    name: Mapped[str] = mapped_column(String(120))          # e.g. "Comercial Gomes"
    base_url: Mapped[str] = mapped_column(String(255))      # scraper target
    categoria: Mapped[str | None] = mapped_column(String(80))
    subcategoria: Mapped[str | None] = mapped_column(String(80))
    pagina_especifica: Mapped[str | None] = mapped_column(String(80))

    # AI enrichment settings
    brand_name: Mapped[str | None] = mapped_column(String(120))    # e.g. "Dimora Mediterranea"
    brand_prompt: Mapped[str | None] = mapped_column(Text)         # custom GPT system prompt
    price_multiplier: Mapped[float] = mapped_column(Float, default=2.0)
    image_style_prompt: Mapped[str | None] = mapped_column(Text)   # image upgrade prompt

    # Schedule (cron expression)
    scrape_scope: Mapped[str] = mapped_column(String(20), default="pagina")  # "categoria", "subcategoria", "pagina"
    scraper_type: Mapped[str] = mapped_column(String(50), default="auto")  # "auto", "comercial_gomes", etc.
    sync_schedule: Mapped[str | None] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="vendor_configs")
    jobs: Mapped[list["Job"]] = relationship(back_populates="vendor_config")

    def __repr__(self) -> str:
        return f"<VendorConfig {self.name} ({self.tenant_id})>"


# ─────────────────────────────────────────────
# Job  (one sync run)
# ─────────────────────────────────────────────

class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    vendor_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vendor_configs.id", ondelete="SET NULL")
    )
    store_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shopify_stores.id", ondelete="SET NULL")
    )

    celery_task_id: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus), default=JobStatus.queued, index=True
    )

    # Progress counters
    products_scraped: Mapped[int] = mapped_column(Integer, default=0)
    products_enriched: Mapped[int] = mapped_column(Integer, default=0)
    products_pushed: Mapped[int] = mapped_column(Integer, default=0)
    products_failed: Mapped[int] = mapped_column(Integer, default=0)
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)

    # Retry tracking
    retry_of_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL")
    )
    attempt: Mapped[int] = mapped_column(Integer, default=1)

    product_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    skip_existing: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_model: Mapped[str] = mapped_column(String(64), default="gpt-4o-mini")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    error_message: Mapped[str | None] = mapped_column(Text)
    error_summary: Mapped[str | None] = mapped_column(Text)  # JSON summary of partial errors

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="jobs")
    vendor_config: Mapped["VendorConfig | None"] = relationship(back_populates="jobs")
    logs: Mapped[list["JobLog"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="JobLog.line_number"
    )

    def __repr__(self) -> str:
        return f"<Job {self.id} [{self.status}]>"


# ─────────────────────────────────────────────
# JobLog  (individual log lines per job)
# Stored in DB for replay on reconnect
# ─────────────────────────────────────────────

class JobLog(Base):
    __tablename__ = "job_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), index=True
    )
    line_number: Mapped[int] = mapped_column(Integer)
    level: Mapped[LogLevel] = mapped_column(SAEnum(LogLevel), default=LogLevel.info)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    job: Mapped["Job"] = relationship(back_populates="logs")

    def to_dict(self) -> dict:
        return {
            "line": self.line_number,
            "level": self.level,
            "message": self.message,
            "ts": self.created_at.isoformat(),
        }


# ─────────────────────────────────────────────
# AuditLog  (who did what)
# ─────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(80))      # e.g. "invite_sent", "member_removed"
    target: Mapped[str | None] = mapped_column(String(255))  # e.g. email or resource ID
    extra_data: Mapped[str | None] = mapped_column(Text)   # JSON extra info
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by {self.user_id}>"


# ─────────────────────────────────────────────
# Backup Add-on
# ─────────────────────────────────────────────

import enum as _enum

class BackupPlanName(str, _enum.Enum):
    basic    = "basic"      # +$9/mo  — manual only, 7 days, 5 snapshots
    standard = "standard"   # +$19/mo — manual + daily, 30 days, 30 snapshots
    premium  = "premium"    # +$39/mo — manual + daily, 90 days, unlimited

class BackupStatus(str, _enum.Enum):
    pending   = "pending"
    running   = "running"
    done      = "done"
    failed    = "failed"

class BackupSubscription(Base):
    """Tracks which tenants have the backup add-on active."""
    __tablename__ = "backup_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), unique=True, index=True)
    plan: Mapped[str] = mapped_column(String(20), default="basic")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    next_auto_backup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class BackupSnapshot(Base):
    """Metadata for each backup snapshot."""
    __tablename__ = "backup_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    store_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shopify_stores.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    trigger: Mapped[str] = mapped_column(String(20), default="manual")  # manual | auto
    product_count: Mapped[int] = mapped_column(Integer, default=0)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    minio_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ─────────────────────────────────────────────
# TenantCredits — saldo de créditos sob demanda
# ─────────────────────────────────────────────
class CreditTransaction(Base):
    __tablename__ = "credit_transactions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # purchase / consume
    amount: Mapped[int] = mapped_column(Integer, nullable=False)   # positive=purchase, negative=consume
    operation: Mapped[str] = mapped_column(String(100), nullable=True)  # e.g. "product_enrich", "bulk_enhance", "snapshot_extra"
    reference_id: Mapped[str] = mapped_column(String(255), nullable=True)  # job_id, snapshot_id, stripe_payment_intent
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tenant: Mapped["Tenant"] = relationship("Tenant", foreign_keys=[tenant_id])


# ─────────────────────────────────────────────
# BulkEnhanceSubscription
# ─────────────────────────────────────────────
class BulkEnhancePlan(str, enum.Enum):
    essencial = "essencial"
    avancado = "avancado"
    ilimitado = "ilimitado"

BULK_ENHANCE_LIMITS = {
    "essencial": 100,
    "avancado": 300,
    "ilimitado": 1000,
}

class BulkEnhanceSubscription(Base):
    __tablename__ = "bulk_enhance_subscriptions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True)
    plan: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    stripe_subscription_id: Mapped[str] = mapped_column(String(255), nullable=True)
    images_enhanced_this_month: Mapped[int] = mapped_column(Integer, default=0)
    next_reset_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tenant: Mapped["Tenant"] = relationship("Tenant", foreign_keys=[tenant_id])


# ─────────────────────────────────────────────
# ModelSubscription — AI model tier add-on
# ─────────────────────────────────────────────
class ModelTier(str, enum.Enum):
    standard = "standard"
    premium = "premium"
    ultra = "ultra"

MODEL_TIER_MODELS = {
    "economy": ["gpt-4o-mini", "gemini-2.5-flash-lite"],
    "standard": ["gpt-4.1", "gemini-2.5-flash", "claude-haiku-4-5"],
    "premium": ["gpt-4o", "gemini-2.5-pro", "claude-sonnet-4-6"],
    "ultra": ["claude-opus-4-7"],
}

class ModelSubscription(Base):
    __tablename__ = "model_subscriptions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)  # standard/premium/ultra
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    stripe_subscription_id: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tenant: Mapped["Tenant"] = relationship("Tenant", foreign_keys=[tenant_id])
