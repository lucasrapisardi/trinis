# PATH: /home/lumoura/trinis_ai/trinis/app/api/routes/password_reset.py
"""
Password reset flow:
  POST /auth/forgot-password  — generate token and send email
  POST /auth/reset-password   — validate token and set new password
"""
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.auth import hash_password
from app.db.session import get_db
from app.models.models import User
from app.services.email import send_password_reset_email

router = APIRouter(tags=["auth"])
settings = get_settings()

RESET_TOKEN_TTL = 3600  # 1 hour


def _get_redis():
    return aioredis.from_url(settings.redis_url, decode_responses=True)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@router.post("/auth/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a password reset token and send it via email.
    Always returns 200 to avoid email enumeration attacks.
    """
    result = await db.execute(
        select(User).where(User.email == payload.email, User.is_active == True)
    )
    user = result.scalar_one_or_none()

    if user:
        token = secrets.token_urlsafe(32)
        redis = _get_redis()
        await redis.setex(
            f"pwd_reset:{token}",
            RESET_TOKEN_TTL,
            str(user.id),
        )
        await redis.aclose()

        reset_url = f"{settings.app_base_url}/reset-password?token={token}"
        send_password_reset_email(
            to_email=user.email,
            reset_url=reset_url,
            user_name=user.full_name,
        )

    # Always return 200 — don't reveal if email exists
    return {
        "message": "If an account with that email exists, a reset link has been sent."
    }


@router.post("/auth/reset-password")
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Validate reset token and update password."""
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    redis = _get_redis()
    user_id_str = await redis.get(f"pwd_reset:{payload.token}")

    if not user_id_str:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    result = await db.execute(
        select(User).where(User.id == uuid.UUID(user_id_str), User.is_active == True)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    # Update password
    user.hashed_password = hash_password(payload.new_password)
    await db.flush()

    # Invalidate token
    await redis.delete(f"pwd_reset:{payload.token}")
    await redis.aclose()

    return {"message": "Password updated successfully"}


@router.get("/auth/verify-reset-token/{token}")
async def verify_reset_token(token: str):
    """Check if a reset token is valid before showing the reset form."""
    redis = _get_redis()
    user_id = await redis.get(f"pwd_reset:{token}")
    await redis.aclose()

    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    return {"valid": True}


# ─────────────────────────────────────────────
# Email confirmation
# ─────────────────────────────────────────────

CONFIRM_TOKEN_TTL = 86400  # 24 hours


@router.post("/auth/resend-confirmation")
async def resend_confirmation(
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Resend confirmation email."""
    result = await db.execute(
        select(User).where(User.email == payload.email, User.is_active == True)
    )
    user = result.scalar_one_or_none()

    if user and not user.email_confirmed:
        token = secrets.token_urlsafe(32)
        redis = _get_redis()
        await redis.setex(f"email_confirm:{token}", CONFIRM_TOKEN_TTL, str(user.id))
        await redis.aclose()

        confirm_url = f"{settings.app_base_url}/confirm-email?token={token}"
        from app.services.email import send_confirmation_email
        send_confirmation_email(
            to_email=user.email,
            confirm_url=confirm_url,
            user_name=user.full_name,
        )

    return {"message": "If your email is registered and unconfirmed, a new link has been sent."}


@router.get("/auth/confirm-email/{token}")
async def confirm_email(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Confirm email address via token."""
    redis = _get_redis()
    user_id_str = await redis.get(f"email_confirm:{token}")

    if not user_id_str:
        raise HTTPException(status_code=400, detail="Invalid or expired confirmation link")

    result = await db.execute(
        select(User).where(User.id == uuid.UUID(user_id_str))
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    user.email_confirmed = True
    await db.flush()

    await redis.delete(f"email_confirm:{token}")
    await redis.aclose()

    return {"message": "Email confirmed successfully. You can now log in."}
