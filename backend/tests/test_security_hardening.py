import pytest
from httpx import AsyncClient

from app.core.rate_limit import login_rate_limiter


@pytest.mark.asyncio
async def test_security_headers_are_present(client: AsyncClient):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert "max-age=" in resp.headers.get("strict-transport-security", "")
    assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


@pytest.mark.asyncio
async def test_login_rate_limiter_blocks_brute_force(client: AsyncClient):
    login_rate_limiter.reset()
    headers = {"X-Forwarded-For": "203.0.113.42"}

    # First 15 wrong-password attempts return 401
    for _ in range(15):
        resp = await client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={"email": "admin@university.edu", "password": "WrongPassword99!"},
        )
        assert resp.status_code == 401

    # 16th attempt within the 60s window is blocked with 429 Too Many Requests
    blocked = await client.post(
        "/api/v1/auth/login",
        headers=headers,
        json={"email": "admin@university.edu", "password": "WrongPassword99!"},
    )
    assert blocked.status_code == 429
    assert blocked.headers.get("retry-after") == "60"
    login_rate_limiter.reset()
