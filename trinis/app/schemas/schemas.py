import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, EmailStr, field_validator


# ─────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    workspace_name: str
    locale: str
    tour_completed: bool = "en"

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


# ─────────────────────────────────────────────
# Tenant
# ─────────────────────────────────────────────

class TenantOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    plan: str
    products_synced_this_month: int
    plan_limit: int
    credits_balance: int
    user_limit: int
    payment_past_due: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────
# User
# ─────────────────────────────────────────────

class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    is_owner: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────
# Shopify Store
# ─────────────────────────────────────────────

class StoreConnectRequest(BaseModel):
    shop_domain: str

    @field_validator("shop_domain")
    @classmethod
    def clean_domain(cls, v: str) -> str:
        v = v.lower().strip()
        v = v.replace(".myshopify.com", "")
        if not v:
            raise ValueError("Invalid shop domain")
        return f"{v}.myshopify.com"


class StoreOut(BaseModel):
    id: uuid.UUID
    shop_domain: str
    is_active: bool
    webhooks_registered: bool
    connected_at: datetime
    last_synced_at: datetime | None

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────
# Vendor Config
# ─────────────────────────────────────────────

class VendorConfigCreate(BaseModel):
    name: str
    base_url: str

    # Scrape scope — customer chooses which level to scrape
    scrape_scope: Literal["categoria", "subcategoria", "pagina"] = "pagina"
    categoria: str | None = None
    subcategoria: str | None = None
    pagina_especifica: str | None = None

    brand_name: str | None = None
    brand_prompt: str | None = None
    price_multiplier: float = 2.0
    image_style_prompt: str | None = None
    sync_schedule: str | None = None


class VendorConfigOut(VendorConfigCreate):
    id: uuid.UUID
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────
# Job
# ─────────────────────────────────────────────

class JobCreate(BaseModel):
    vendor_config_id: uuid.UUID
    store_id: uuid.UUID
    product_limit: int | None = None      # None = all products
    scheduled_at: datetime | None = None  # None = run immediately
    skip_existing: bool = False
    ai_model: str = "gpt-4o-mini"


class JobOut(BaseModel):
    id: uuid.UUID
    status: str
    products_scraped: int
    products_enriched: int
    products_pushed: int
    products_failed: int
    progress_pct: int
    product_limit: int | None
    error_message: str | None
    error_summary: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    attempt: int

    model_config = {"from_attributes": True}


class JobLogOut(BaseModel):
    line: int
    level: str
    message: str
    ts: str


# ─────────────────────────────────────────────
# Dashboard summary
# ─────────────────────────────────────────────

class DashboardSummary(BaseModel):
    products_synced_this_month: int
    plan_limit: int
    plan: str
    jobs_this_month: int
    jobs_failed_this_month: int
    running_jobs: int
    last_sync_at: datetime | None
