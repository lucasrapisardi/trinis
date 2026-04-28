import pytest
from httpx import AsyncClient


async def test_register_and_login(client: AsyncClient):
    # Register
    r = await client.post("/api/auth/register", json={
        "email": "newuser@example.com",
        "password": "securepass123",
        "full_name": "New User",
        "workspace_name": "New Tenant",
        "locale": "en",
    })
    assert r.status_code == 201

async def test_login_invalid_password(client: AsyncClient, user):
    r = await client.post("/api/auth/login", json={
        "email": user.email,
        "password": "wrongpassword",
    })
    assert r.status_code in (401, 403)

async def test_me_authenticated(client: AsyncClient, auth_headers):
    r = await client.get("/api/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert "email" in r.json()
    assert "tour_completed" in r.json()

async def test_me_unauthenticated(client: AsyncClient):
    r = await client.get("/api/auth/me")
    assert r.status_code in (401, 403)

async def test_tour_complete(client: AsyncClient, auth_headers):
    r = await client.patch("/api/auth/tour-complete", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["ok"] is True
