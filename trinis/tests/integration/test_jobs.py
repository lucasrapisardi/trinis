import pytest
import uuid
from httpx import AsyncClient
from app.models.models import ShopifyStore, VendorConfig


@pytest.fixture
async def store(db, tenant):
    from app.core.encryption import encrypt_token
    s = ShopifyStore(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        shop_domain="test-store.myshopify.com",
        encrypted_access_token=encrypt_token("test-token"),
        is_active=True,
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


@pytest.fixture
async def vendor(db, tenant):
    v = VendorConfig(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name="Test Vendor",
        base_url="https://example.com",
        scrape_scope="pagina",
        is_active=True,
    )
    db.add(v)
    await db.commit()
    await db.refresh(v)
    return v


async def test_list_jobs_empty(client: AsyncClient, auth_headers):
    r = await client.get("/api/jobs", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_create_job_missing_store(client: AsyncClient, auth_headers, vendor):
    r = await client.post("/api/jobs", headers=auth_headers, json={
        "vendor_config_id": str(vendor.id),
        "store_id": str(uuid.uuid4()),  # non-existent store
        "ai_model": "gpt-4o-mini",
    })
    assert r.status_code == 404


async def test_create_job_free_plan_gate(client: AsyncClient, auth_headers, db, tenant, vendor, store):
    from app.models.models import PlanName
    tenant.plan = PlanName.free
    tenant.products_synced_this_month = 100  # over free limit (30)
    tenant.credits_balance = 0
    await db.commit()

    r = await client.post("/api/jobs", headers=auth_headers, json={
        "vendor_config_id": str(vendor.id),
        "store_id": str(store.id),
        "ai_model": "gpt-4o-mini",
    })
    assert r.status_code == 402


async def test_job_summary(client: AsyncClient, auth_headers):
    r = await client.get("/api/jobs/summary/dashboard", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "products_synced_this_month" in data
    assert "plan_limit" in data
