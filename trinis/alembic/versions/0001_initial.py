"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2026-04-11 00:00:00.000000

"""
from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    # ── tenants ───────────────────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column(
            "plan",
            sa.Enum("free", "pro", "business", name="planname"),
            nullable=False,
            server_default="free",
        ),
        sa.Column("stripe_customer_id", sa.String(64), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(64), nullable=True),
        sa.Column("payment_past_due", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("products_synced_this_month", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "usage_reset_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)

    # ── users ─────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(120), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_owner", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])

    # ── shopify_stores ────────────────────────────────────────────────────
    op.create_table(
        "shopify_stores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("shop_domain", sa.String(120), nullable=False),
        sa.Column("encrypted_access_token", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("webhooks_registered", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "connected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_shopify_stores_shop_domain", "shopify_stores", ["shop_domain"], unique=True)
    op.create_index("ix_shopify_stores_tenant_id", "shopify_stores", ["tenant_id"])

    # ── vendor_configs ────────────────────────────────────────────────────
    op.create_table(
        "vendor_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("base_url", sa.String(255), nullable=False),
        sa.Column("categoria", sa.String(80), nullable=True),
        sa.Column("subcategoria", sa.String(80), nullable=True),
        sa.Column("pagina_especifica", sa.String(80), nullable=True),
        sa.Column("brand_name", sa.String(120), nullable=True),
        sa.Column("brand_prompt", sa.Text(), nullable=True),
        sa.Column("price_multiplier", sa.Float(), nullable=False, server_default="2.0"),
        sa.Column("image_style_prompt", sa.Text(), nullable=True),
        sa.Column("sync_schedule", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_vendor_configs_tenant_id", "vendor_configs", ["tenant_id"])

    # ── jobs ──────────────────────────────────────────────────────────────
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "vendor_config_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vendor_configs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "store_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("shopify_stores.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "retry_of_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("celery_task_id", sa.String(64), nullable=True),
        sa.Column(
            "status",
            sa.Enum("queued", "running", "done", "failed", "cancelled", name="jobstatus"),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("products_scraped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("products_enriched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("products_pushed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("products_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_pct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_jobs_tenant_id", "jobs", ["tenant_id"])
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_celery_task_id", "jobs", ["celery_task_id"])

    # ── job_logs ──────────────────────────────────────────────────────────
    op.create_table(
        "job_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column(
            "level",
            sa.Enum("info", "warn", "error", name="loglevel"),
            nullable=False,
            server_default="info",
        ),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_job_logs_job_id", "job_logs", ["job_id"])


def downgrade() -> None:
    op.drop_table("job_logs")
    op.drop_table("jobs")
    op.drop_table("vendor_configs")
    op.drop_table("shopify_stores")
    op.drop_table("users")
    op.drop_table("tenants")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS loglevel")
    op.execute("DROP TYPE IF EXISTS jobstatus")
    op.execute("DROP TYPE IF EXISTS planname")
