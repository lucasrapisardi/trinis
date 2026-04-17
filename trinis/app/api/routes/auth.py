# PATH: /home/lumoura/trinis_ai/trinis/app/api/routes/auth.py
import re
import uuid
import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as aioredis

from app.db.session import get_db
from app.models.models import User, Tenant, PlanName
from app.schemas.schemas import RegisterRequest, LoginRequest, TokenResponse, RefreshRequest
from app.core.auth import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
    get_current_user,
)
from app.core.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

CONFIRM_TOKEN_TTL = 86400  # 24 hours


def _get_redis():
    return aioredis.from_url(settings.redis_url, decode_responses=True)


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")[:80]


@router.post("/register", status_code=201)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Create a new tenant + owner user and send confirmation email."""

    # Check email uniqueness
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    # Ensure slug is unique
    base_slug = _slugify(payload.workspace_name)
    slug = base_slug
    counter = 1
    while True:
        taken = await db.execute(select(Tenant).where(Tenant.slug == slug))
        if not taken.scalar_one_or_none():
            break
        slug = f"{base_slug}-{counter}"
        counter += 1

    # Create tenant
    tenant = Tenant(name=payload.workspace_name, slug=slug, plan=PlanName.free)
    db.add(tenant)
    await db.flush()

    # Create owner user — not confirmed yet
    user = User(
        tenant_id=tenant.id,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        is_owner=True,
        email_confirmed=False,
    )
    db.add(user)
    await db.flush()

    # Generate confirmation token and store in Redis
    confirm_token = secrets.token_urlsafe(32)
    redis = _get_redis()
    await redis.setex(f"email_confirm:{confirm_token}", CONFIRM_TOKEN_TTL, str(user.id))
    await redis.aclose()

    # Send confirmation email
    confirm_url = f"{settings.app_base_url}/confirm-email?token={confirm_token}"
    try:
        from app.services.email import send_confirmation_email
        send_confirmation_email(
            to_email=user.email,
            confirm_url=confirm_url,
            user_name=user.full_name,
        )
    except Exception as e:
        print(f"⚠️ Failed to send confirmation email: {e}")

    return {"message": "Account created. Please check your email to confirm your account."}


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive")

    if not user.email_confirmed:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "email_not_confirmed",
                "message": "Please confirm your email before logging in. Check your inbox for the confirmation link.",
            }
        )

    # Update last login
    user.last_login_at = datetime.now(timezone.utc)

    return TokenResponse(
        access_token=create_access_token(user.id, user.tenant_id),
        refresh_token=create_refresh_token(user.id, user.tenant_id),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    decoded = decode_token(payload.refresh_token)
    if decoded.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = uuid.UUID(decoded["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")

    return TokenResponse(
        access_token=create_access_token(user.id, user.tenant_id),
        refresh_token=create_refresh_token(user.id, user.tenant_id),
    )


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "tenant_id": str(current_user.tenant_id),
        "is_owner": current_user.is_owner,
    }
