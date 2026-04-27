"""
Credits service — atomic debit with Redis lock.
1 credit = 1 product enriched (text + hero enhance)
5 credits = 1 bulk enhance product or 1 extra snapshot
"""
import uuid
import logging
from sqlalchemy.orm import Session
from sqlalchemy import select, update

logger = logging.getLogger(__name__)

CREDIT_COSTS = {
    "product_enrich": 1,
    "bulk_enhance": 5,
    "snapshot_extra": 5,
}


def get_balance(db: Session, tenant_id: uuid.UUID) -> int:
    from app.models.models import Tenant
    tenant = db.get(Tenant, tenant_id)
    return tenant.credits_balance if tenant else 0


def debit_credits(
    db: Session,
    tenant_id: uuid.UUID,
    operation: str,
    quantity: int = 1,
    reference_id: str = None,
) -> bool:
    """
    Atomically debit credits for an operation.
    Returns True if debited, False if insufficient balance.
    Uses DB-level atomic UPDATE to avoid race conditions.
    """
    from app.models.models import Tenant, CreditTransaction

    cost = CREDIT_COSTS.get(operation, 1) * quantity

    # Atomic update — only succeeds if balance >= cost
    result = db.execute(
        update(Tenant)
        .where(Tenant.id == tenant_id, Tenant.credits_balance >= cost)
        .values(credits_balance=Tenant.credits_balance - cost)
        .returning(Tenant.credits_balance)
    )
    row = result.fetchone()

    if not row:
        logger.warning(f"Insufficient credits for tenant {tenant_id}: op={operation} cost={cost}")
        return False

    # Log transaction
    tx = CreditTransaction(
        tenant_id=tenant_id,
        type="consume",
        amount=-cost,
        operation=operation,
        reference_id=reference_id,
    )
    db.add(tx)
    db.commit()
    logger.info(f"Debited {cost} credits from tenant {tenant_id} for {operation} (ref={reference_id})")
    return True


def add_credits(
    db: Session,
    tenant_id: uuid.UUID,
    amount: int,
    reference_id: str = None,
    operation: str = "purchase",
) -> int:
    """Add credits to tenant balance. Returns new balance."""
    from app.models.models import Tenant, CreditTransaction

    result = db.execute(
        update(Tenant)
        .where(Tenant.id == tenant_id)
        .values(credits_balance=Tenant.credits_balance + amount)
        .returning(Tenant.credits_balance)
    )
    new_balance = result.fetchone()[0]

    tx = CreditTransaction(
        tenant_id=tenant_id,
        type="purchase",
        amount=amount,
        operation=operation,
        reference_id=reference_id,
    )
    db.add(tx)
    db.commit()
    logger.info(f"Added {amount} credits to tenant {tenant_id} (ref={reference_id}), new balance={new_balance}")
    return new_balance
