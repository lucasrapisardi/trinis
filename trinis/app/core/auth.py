from datetime import datetime, timedelta, timezone
from typing import Annotated
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import get_db
from app.models.models import User, Tenant

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()


# ─────────────────────────────────────────────
# Password helpers
# ─────────────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ─────────────────────────────────────────────
# JWT helpers
# ─────────────────────────────────────────────

def create_access_token(user_id: uuid.UUID, tenant_id: uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: uuid.UUID, tenant_id: uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.jwt_refresh_token_expire_days
    )
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ─────────────────────────────────────────────
# FastAPI dependencies
# ─────────────────────────────────────────────

async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Validates JWT and returns the authenticated User."""
    payload = decode_token(credentials.credentials)

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return user


async def get_current_tenant(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Tenant:
    """Returns the Tenant for the authenticated user."""
    result = await db.execute(
        select(Tenant).where(Tenant.id == current_user.tenant_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


async def require_plan(min_plan: str):
    """
    Returns a dependency that raises 402 if tenant is below the required plan.
    Usage: Depends(require_plan("pro"))
    """
    plan_order = {"free": 0, "pro": 1, "business": 2}

    async def _check(tenant: Annotated[Tenant, Depends(get_current_tenant)]):
        if plan_order.get(tenant.plan, 0) < plan_order.get(min_plan, 0):
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "plan_upgrade_required",
                    "required": min_plan,
                    "current": tenant.plan,
                    "upgrade_url": "/billing",
                },
            )
        return tenant

    return _check


async def check_sync_limit(
    tenant: Annotated[Tenant, Depends(get_current_tenant)],
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    """Raises 402 if tenant has hit their monthly product sync limit AND has no credits."""
    if tenant.products_synced_this_month >= tenant.plan_limit:
        # Check if tenant has credits to continue
        if tenant.credits_balance <= 0:
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "plan_limit_reached",
                    "limit": tenant.plan_limit,
                    "used": tenant.products_synced_this_month,
                    "credits": tenant.credits_balance,
                    "upgrade_url": "/billing",
                },
            )
    return tenant
