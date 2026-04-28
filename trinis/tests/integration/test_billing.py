import pytest
from httpx import AsyncClient


async def test_billing_status_requires_auth(client: AsyncClient):
    r = await client.get("/api/tenant")
    assert r.status_code in (401, 403)


async def test_tenant_info_authenticated(client: AsyncClient, auth_headers):
    r = await client.get("/api/tenant", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "plan" in data
    assert "credits_balance" in data
    assert "products_synced_this_month" in data
    assert "plan_limit" in data


async def test_model_addon_status(client: AsyncClient, auth_headers):
    r = await client.get("/api/billing/model-addon/status", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "tier" in data
    assert data["tier"] == "economy"  # no subscription yet
    assert "available_models" in data
    assert "gpt-4o-mini" in data["available_models"]


async def test_credits_checkout_invalid_pack(client: AsyncClient, auth_headers):
    r = await client.post("/api/billing/credits/checkout/invalid_pack", headers=auth_headers)
    assert r.status_code == 400


async def test_bulk_enhance_checkout_invalid_plan(client: AsyncClient, auth_headers):
    r = await client.post("/api/billing/bulk-enhance/checkout/invalid_plan", headers=auth_headers)
    assert r.status_code == 400
