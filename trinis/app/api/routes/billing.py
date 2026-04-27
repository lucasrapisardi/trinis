import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.auth import get_current_user, get_current_tenant
from app.core.config import get_settings
from app.db.session import get_db
from app.models.models import User, Tenant, PlanName

settings = get_settings()
stripe.api_key = settings.stripe_secret_key
router = APIRouter(prefix="/billing", tags=["billing"])

PLAN_PRICE_MAP = {
    PlanName.free: None,
    PlanName.starter: settings.stripe_starter_price_id,
    PlanName.pro: settings.stripe_pro_price_id,
    PlanName.business: settings.stripe_business_price_id,
}

PRICE_PLAN_MAP = {
    settings.stripe_starter_price_id: PlanName.starter,
    settings.stripe_pro_price_id: PlanName.pro,
    settings.stripe_business_price_id: PlanName.business,
}


# ─────────────────────────────────────────────
# Checkout — redirect to Stripe hosted checkout
# ─────────────────────────────────────────────

@router.post("/checkout/{plan}")
async def create_checkout(
    plan: PlanName,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
):
    if plan == PlanName.free:
        raise HTTPException(400, "Cannot checkout to free plan")

    price_id = PLAN_PRICE_MAP.get(plan)
    if not price_id:
        raise HTTPException(400, "Invalid plan")

    # Create or retrieve Stripe customer
    if not tenant.stripe_customer_id:
        customer = stripe.Customer.create(
            email=current_user.email,
            name=tenant.name,
            metadata={"tenant_id": str(tenant.id)},
        )
        tenant.stripe_customer_id = customer.id

    session = stripe.checkout.Session.create(
        customer=tenant.stripe_customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{settings.app_base_url}/billing?upgraded=1",
        cancel_url=f"{settings.app_base_url}/billing",
        metadata={"tenant_id": str(tenant.id), "plan": plan},
    )

    return {"checkout_url": session.url}


# ─────────────────────────────────────────────
# Customer portal — manage subscription
# ─────────────────────────────────────────────

@router.post("/portal")
async def billing_portal(tenant: Tenant = Depends(get_current_tenant)):
    if not tenant.stripe_customer_id:
        raise HTTPException(400, "No billing account found. Please subscribe first.")

    session = stripe.billing_portal.Session.create(
        customer=tenant.stripe_customer_id,
        return_url=f"{settings.app_base_url}/billing",
    )

    return {"portal_url": session.url}


# ─────────────────────────────────────────────
# Stripe webhook handler
# ─────────────────────────────────────────────

@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]
    data = event["data"]["object"]

    # Retrieve tenant from Stripe customer ID
    async def _get_tenant_by_customer(customer_id: str) -> Tenant | None:
        result = await db.execute(
            select(Tenant).where(Tenant.stripe_customer_id == customer_id)
        )
        return result.scalar_one_or_none()

    if event_type == "checkout.session.completed":
        metadata = data.get("metadata", {})
        # Handle credits purchase
        if metadata.get("type") == "credits":
            tenant_id = metadata.get("tenant_id")
            credits = int(metadata.get("credits", 0))
            pack = metadata.get("pack", "")
            if tenant_id and credits:
                from app.services.credits import add_credits
                t_result = await db.execute(select(Tenant).where(Tenant.id == uuid.UUID(tenant_id)))
                t = t_result.scalar_one_or_none()
                if t:
                    payment_intent = data.get("payment_intent", "")
                    add_credits(db, t.id, credits, reference_id=payment_intent, operation=f"purchase_{pack}")
        # Handle bulk enhance checkout
        elif metadata.get("type") == "bulk_enhance":
            tenant_id = metadata.get("tenant_id")
            bulk_plan = metadata.get("bulk_plan")
            stripe_sub_id = data.get("subscription")
            if tenant_id and bulk_plan:
                from app.models.models import BulkEnhanceSubscription
                t_result = await db.execute(select(Tenant).where(Tenant.id == uuid.UUID(tenant_id)))
                t = t_result.scalar_one_or_none()
                if t:
                    sub_result = await db.execute(select(BulkEnhanceSubscription).where(BulkEnhanceSubscription.tenant_id == t.id))
                    sub = sub_result.scalar_one_or_none()
                    if sub:
                        sub.plan = bulk_plan
                        sub.is_active = True
                        sub.stripe_subscription_id = stripe_sub_id
                    else:
                        db.add(BulkEnhanceSubscription(tenant_id=t.id, plan=bulk_plan, is_active=True, stripe_subscription_id=stripe_sub_id))
        # Handle backup addon checkout
        elif metadata.get("type") == "backup_addon":
            tenant_id = metadata.get("tenant_id")
            backup_plan = metadata.get("backup_plan")
            stripe_sub_id = data.get("subscription")
            if tenant_id and backup_plan:
                from app.models.models import BackupSubscription
                t_result = await db.execute(select(Tenant).where(Tenant.id == uuid.UUID(tenant_id)))
                t = t_result.scalar_one_or_none()
                if t:
                    sub_result = await db.execute(select(BackupSubscription).where(BackupSubscription.tenant_id == t.id))
                    sub = sub_result.scalar_one_or_none()
                    if sub:
                        sub.plan = backup_plan
                        sub.is_active = True
                        sub.stripe_subscription_id = stripe_sub_id
                    else:
                        db.add(BackupSubscription(tenant_id=t.id, plan=backup_plan, is_active=True, stripe_subscription_id=stripe_sub_id))
        else:
            tenant = await _get_tenant_by_customer(data["customer"])
            if tenant:
                new_plan = metadata.get("plan", "pro")
                tenant.plan = PlanName(new_plan)
                tenant.stripe_subscription_id = data.get("subscription")

    elif event_type == "customer.subscription.updated":
        from app.models.models import BackupSubscription
        # Check if it's a backup addon subscription
        backup_result = await db.execute(
            select(BackupSubscription).where(
                BackupSubscription.stripe_subscription_id == data["id"]
            )
        )
        backup_sub = backup_result.scalar_one_or_none()
        if backup_sub:
            # Backup plan change
            if data.get("items", {}).get("data"):
                price_id = data["items"]["data"][0]["price"]["id"]
                backup_price_map = {
                    settings.stripe_backup_basic_price_id: "basic",
                    settings.stripe_backup_standard_price_id: "standard",
                    settings.stripe_backup_premium_price_id: "premium",
                }
                new_plan = backup_price_map.get(price_id)
                if new_plan:
                    backup_sub.plan = new_plan
                backup_sub.is_active = data.get("status") == "active"
        else:
            # Main plan change
            tenant = await _get_tenant_by_customer(data["customer"])
            if tenant and data.get("items", {}).get("data"):
                price_id = data["items"]["data"][0]["price"]["id"]
                tenant.plan = PRICE_PLAN_MAP.get(price_id, PlanName.free)

    elif event_type == "customer.subscription.deleted":
        # Check if it's a backup addon subscription
        from app.models.models import BackupSubscription
        backup_result = await db.execute(
            select(BackupSubscription).where(
                BackupSubscription.stripe_subscription_id == data["id"]
            )
        )
        backup_sub = backup_result.scalar_one_or_none()
        if backup_sub:
            backup_sub.is_active = False
            backup_sub.stripe_subscription_id = None
        else:
            tenant = await _get_tenant_by_customer(data["customer"])
            if tenant:
                tenant.plan = PlanName.free
                tenant.stripe_subscription_id = None

    elif event_type == "invoice.payment_failed":
        tenant = await _get_tenant_by_customer(data["customer"])
        if tenant:
            tenant.payment_past_due = True

    elif event_type == "invoice.paid":
        tenant = await _get_tenant_by_customer(data["customer"])
        if tenant:
            tenant.payment_past_due = False
            # Reset monthly usage on invoice paid (new billing cycle)
            from datetime import datetime, timezone
            tenant.products_synced_this_month = 0
            tenant.usage_reset_at = datetime.now(timezone.utc)

    return {"received": True}


# ── Credits checkout ──────────────────────────────────────────────────────────
CREDITS_PRICE_MAP = {
    "starter": (settings.stripe_credits_starter_price_id, 90),
    "growth": (settings.stripe_credits_growth_price_id, 250),
    "scale": (settings.stripe_credits_scale_price_id, 550),
    "pro": (settings.stripe_credits_pro_price_id, 1200),
}

@router.post("/credits/checkout/{pack}")
async def credits_checkout(
    pack: str,
    tenant: Tenant = Depends(get_current_tenant),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if pack not in CREDITS_PRICE_MAP:
        raise HTTPException(400, "Invalid credits pack")
    price_id, credits = CREDITS_PRICE_MAP[pack]
    if not tenant.stripe_customer_id:
        customer = stripe.Customer.create(email=current_user.email, name=tenant.name)
        tenant.stripe_customer_id = customer.id
        await db.commit()
    session = stripe.checkout.Session.create(
        customer=tenant.stripe_customer_id,
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="payment",
        success_url="http://localhost:3000/en/billing?credits=success",
        cancel_url="http://localhost:3000/en/billing?credits=cancelled",
        metadata={"tenant_id": str(tenant.id), "type": "credits", "pack": pack, "credits": credits},
    )
    return {"checkout_url": session.url}


# ── Bulk Enhance checkout ─────────────────────────────────────────────────────
BULK_ENHANCE_PRICE_MAP = {
    "essencial": settings.stripe_bulk_enhance_essencial_price_id,
    "avancado": settings.stripe_bulk_enhance_avancado_price_id,
    "ilimitado": settings.stripe_bulk_enhance_ilimitado_price_id,
}

@router.post("/bulk-enhance/checkout/{plan}")
async def bulk_enhance_checkout(
    plan: str,
    tenant: Tenant = Depends(get_current_tenant),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if plan not in BULK_ENHANCE_PRICE_MAP:
        raise HTTPException(400, "Invalid bulk enhance plan")
    # Ilimitado requires Pro or Business
    if plan == "ilimitado" and tenant.plan not in ("pro", "business"):
        raise HTTPException(403, "Ilimitado plan requires Pro or Business subscription")
    price_id = BULK_ENHANCE_PRICE_MAP[plan]
    if not tenant.stripe_customer_id:
        customer = stripe.Customer.create(email=current_user.email, name=tenant.name)
        tenant.stripe_customer_id = customer.id
        await db.commit()
    session = stripe.checkout.Session.create(
        customer=tenant.stripe_customer_id,
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        success_url="http://localhost:3000/en/billing?bulk_enhance=success",
        cancel_url="http://localhost:3000/en/billing?bulk_enhance=cancelled",
        metadata={"tenant_id": str(tenant.id), "type": "bulk_enhance", "bulk_plan": plan},
    )
    return {"checkout_url": session.url}
