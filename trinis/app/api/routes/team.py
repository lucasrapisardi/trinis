# PATH: /home/lumoura/trinis_ai/trinis/app/api/routes/team.py
"""
Team management — invite members, list team, remove members, audit logs.
Only available on Pro+ plans.
"""
import json
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import redis.asyncio as aioredis

from app.core.auth import get_current_user, get_current_tenant
from app.core.config import get_settings
from app.db.session import get_db
from app.models.models import User, Tenant, AuditLog, PlanName

router = APIRouter(prefix="/team", tags=["team"])
settings = get_settings()

INVITE_TOKEN_TTL = 60 * 60 * 72  # 72 hours


def _get_redis():
    return aioredis.from_url(settings.redis_url, decode_responses=True)


def _require_pro(tenant: Tenant):
    if tenant.plan in (PlanName.free, PlanName.starter, PlanName.cancelled):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "plan_upgrade_required",
                "message": "Team members are available on Pro and Business plans.",
                "upgrade_url": "/billing",
            }
        )


def _require_owner(user: User):
    if not user.is_owner:
        raise HTTPException(status_code=403, detail="Only the account owner can manage team members")


async def _log(db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID, action: str, target: str = None, metadata: dict = None):
    log = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        action=action,
        target=target,
        extra_data=json.dumps(metadata) if metadata else None,
    )
    db.add(log)


# ── List team members ──────────────────────────────────────────────────────

@router.get("/members")
async def list_members(
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_pro(tenant)
    result = await db.execute(
        select(User).where(User.tenant_id == tenant.id, User.is_active == True)
    )
    members = result.scalars().all()
    return [
        {
            "id": str(m.id),
            "email": m.email,
            "full_name": m.full_name,
            "is_owner": m.is_owner,
            "email_confirmed": m.email_confirmed,
            "created_at": m.created_at.isoformat(),
            "last_login_at": m.last_login_at.isoformat() if m.last_login_at else None,
        }
        for m in members
    ]


# ── Invite member ──────────────────────────────────────────────────────────

class InviteRequest(BaseModel):
    email: EmailStr
    full_name: str | None = None


@router.post("/invite", status_code=201)
async def invite_member(
    payload: InviteRequest,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_pro(tenant)
    _require_owner(current_user)

    # Check user limit
    count_result = await db.execute(
        select(func.count(User.id)).where(
            User.tenant_id == tenant.id,
            User.is_active == True,
        )
    )
    current_count = count_result.scalar()
    if current_count >= tenant.user_limit:
        raise HTTPException(
            status_code=402,
            detail={
                "code": "user_limit_reached",
                "message": f"Your plan allows up to {tenant.user_limit} users. Upgrade to add more.",
                "upgrade_url": "/billing",
            }
        )

    # Check if already a member
    existing = await db.execute(
        select(User).where(User.email == payload.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="This email is already registered")

    # Generate invite token
    token = secrets.token_urlsafe(32)
    redis = _get_redis()
    await redis.setex(
        f"team_invite:{token}",
        INVITE_TOKEN_TTL,
        json.dumps({
            "tenant_id": str(tenant.id),
            "email": payload.email,
            "full_name": payload.full_name,
            "invited_by": str(current_user.id),
        })
    )
    await redis.aclose()

    invite_url = f"{settings.app_base_url}/accept-invite?token={token}"

    # Send invite email
    try:
        from app.services.email import send_invite_email
        send_invite_email(
            to_email=payload.email,
            invite_url=invite_url,
            invited_by_name=current_user.full_name or current_user.email,
            workspace_name=tenant.name,
            user_name=payload.full_name,
        )
    except Exception as e:
        print(f"⚠️ Failed to send invite email: {e}")

    await _log(db, tenant.id, current_user.id, "invite_sent", payload.email)

    return {"message": f"Invite sent to {payload.email}", "invite_url": invite_url}


# ── Accept invite ──────────────────────────────────────────────────────────

class AcceptInviteRequest(BaseModel):
    token: str
    password: str
    full_name: str | None = None


@router.post("/accept-invite")
async def accept_invite(
    payload: AcceptInviteRequest,
    db: AsyncSession = Depends(get_db),
):
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    redis = _get_redis()
    data_str = await redis.get(f"team_invite:{payload.token}")
    if not data_str:
        raise HTTPException(status_code=400, detail="Invalid or expired invite link")

    data = json.loads(data_str)

    # Check if email already taken
    existing = await db.execute(select(User).where(User.email == data["email"]))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="This email is already registered")

    from app.core.auth import hash_password
    user = User(
        tenant_id=uuid.UUID(data["tenant_id"]),
        email=data["email"],
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name or data.get("full_name") or data["email"].split("@")[0],
        is_owner=False,
        is_active=True,
        email_confirmed=True,  # Invite = implicit email confirmation
    )
    db.add(user)
    await db.flush()

    await redis.delete(f"team_invite:{payload.token}")
    await redis.aclose()

    await _log(db, uuid.UUID(data["tenant_id"]), user.id, "member_joined", data["email"])

    return {"message": "Account created successfully. You can now log in."}


# ── Verify invite token ────────────────────────────────────────────────────

@router.get("/verify-invite/{token}")
async def verify_invite(token: str):
    redis = _get_redis()
    data_str = await redis.get(f"team_invite:{token}")
    await redis.aclose()

    if not data_str:
        raise HTTPException(status_code=400, detail="Invalid or expired invite link")

    data = json.loads(data_str)
    return {
        "valid": True,
        "email": data["email"],
        "workspace_name": data.get("workspace_name", ""),
        "full_name": data.get("full_name", ""),
    }


# ── Remove member ──────────────────────────────────────────────────────────

@router.delete("/members/{user_id}")
async def remove_member(
    user_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_owner(current_user)

    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == tenant.id)
    )
    member = result.scalar_one_or_none()

    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    if member.is_owner:
        raise HTTPException(status_code=400, detail="Cannot remove the account owner")

    member.is_active = False
    await _log(db, tenant.id, current_user.id, "member_removed", member.email)

    return {"ok": True}


# ── Audit logs ─────────────────────────────────────────────────────────────

@router.get("/audit-logs")
async def get_audit_logs(
    limit: int = 50,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_owner(current_user)

    result = await db.execute(
        select(AuditLog, User.email, User.full_name)
        .outerjoin(User, AuditLog.user_id == User.id)
        .where(AuditLog.tenant_id == tenant.id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )

    logs = []
    for log, email, full_name in result.all():
        logs.append({
            "id": str(log.id),
            "action": log.action,
            "target": log.target,
            "metadata": json.loads(log.extra_data) if log.extra_data else None,
            "performed_by": full_name or email or "System",
            "created_at": log.created_at.isoformat(),
        })

    return logs
