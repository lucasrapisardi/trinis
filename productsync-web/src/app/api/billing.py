import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from typing import Literal

from app.core.auth import get_current_user, get_current_tenant
from app.core.config import get_settings
from app.db.session import get_db
from app.models.models import User, Tenant, PlanName

settings = get_settings()
stripe.api_key = settings.stripe_secret_key
router = APIRouter(prefix="/billing", tags=["billing"])

# Substituir os dois mapas atuais por:

PLAN_PRICE_MAP = {
    PlanName.free: None,
    PlanName.starter: settings.stripe_starter_price_id,
    PlanName.pro: settings.stripe_pro_price_id,
    PlanName.business: settings.stripe_business_price_id,
}

PLAN_ANNUAL_PRICE_MAP = {
    PlanName.starter: settings.stripe_starter_annual_price_id,
    PlanName.pro: settings.stripe_pro_annual_price_id,
    PlanName.business: settings.stripe_business_annual_price_id,
}

PRICE_PLAN_MAP = {
    settings.stripe_starter_price_id: PlanName.starter,
    settings.stripe_pro_price_id: PlanName.pro,
    settings.stripe_business_price_id: PlanName.business,
    settings.stripe_starter_annual_price_id: PlanName.starter,
    settings.stripe_pro_annual_price_id: PlanName.pro,
    settings.stripe_business_annual_price_id: PlanName.business,
}


# ─────────────────────────────────────────────
# Checkout — redirect to Stripe hosted checkout
# ─────────────────────────────────────────────

@router.post("/checkout/{plan}")
async def create_checkout(
    plan: PlanName,
    interval: Literal["monthly", "yearly"] = "monthly",
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
):
    if plan == PlanName.free:
        raise HTTPException(400, "Cannot checkout to free plan")

    if interval == "yearly":
        price_id = PLAN_ANNUAL_PRICE_MAP.get(plan)
    else:
        price_id = PLAN_PRICE_MAP.get(plan)

    if not price_id:
        raise HTTPException(400, "Invalid plan")

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
        tenant = await _get_tenant_by_customer(data["customer"])
        if tenant:
            new_plan = data.get("metadata", {}).get("plan", "pro")
            tenant.plan = PlanName(new_plan)
            tenant.stripe_subscription_id = data.get("subscription")

    elif event_type == "customer.subscription.updated":
        tenant = await _get_tenant_by_customer(data["customer"])
        if tenant and data.get("items", {}).get("data"):
            price_id = data["items"]["data"][0]["price"]["id"]
            tenant.plan = PRICE_PLAN_MAP.get(price_id, PlanName.free)

    elif event_type == "customer.subscription.deleted":
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
