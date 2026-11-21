import pytest
from httpx import AsyncClient

from app.core.config import normalize_async_database_url
from app.core.rate_limit import login_rate_limiter, refresh_rate_limiter
from tests.conftest import TEST_ADMIN_PW


@pytest.mark.asyncio
async def test_security_headers_are_present(client: AsyncClient):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert "max-age=" in resp.headers.get("strict-transport-security", "")
    assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


@pytest.mark.asyncio
async def test_login_rate_limiter_ignores_spoofed_xff_headers(client: AsyncClient):
    """P0-1 regression: sending a different spoofed X-Forwarded-For per request must not bypass rate limit."""
    login_rate_limiter.reset()

    for idx in range(15):
        resp = await client.post(
            "/api/v1/auth/login",
            headers={"X-Forwarded-For": f"198.51.100.{idx + 1}"},
            json={"email": "admin@university.edu", "password": "WrongPassword99!"},
        )
        assert resp.status_code == 401

    blocked = await client.post(
        "/api/v1/auth/login",
        headers={"X-Forwarded-For": "203.0.113.250"},
        json={"email": "admin@university.edu", "password": "WrongPassword99!"},
    )
    assert blocked.status_code == 429
    assert blocked.headers.get("retry-after") == "60"
    login_rate_limiter.reset()


@pytest.mark.asyncio
async def test_refresh_token_reuse_revokes_active_family(client: AsyncClient):
    """P1-6 regression: replaying an already-rotated refresh token revokes the newly issued token too."""
    login_rate_limiter.reset()
    refresh_rate_limiter.reset()

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@university.edu", "password": TEST_ADMIN_PW},
    )
    assert login_resp.status_code == 200
    token_1 = login_resp.json()["refresh_token"]

    # Legitimate rotation -> issues token_2, revokes token_1
    rot = await client.post("/api/v1/auth/refresh", json={"refresh_token": token_1})
    assert rot.status_code == 200
    token_2 = rot.json()["refresh_token"]

    # Replay stolen token_1 -> must fail AND revoke token_2
    replay = await client.post("/api/v1/auth/refresh", json={"refresh_token": token_1})
    assert replay.status_code == 401

    # Now token_2 must also be revoked
    after_replay = await client.post("/api/v1/auth/refresh", json={"refresh_token": token_2})
    assert after_replay.status_code == 401


@pytest.mark.asyncio
async def test_password_over_72_utf8_bytes_returns_422(client: AsyncClient):
    """P2-2 regression: >72 UTF-8 byte passwords (e.g. 25 Gujarati chars = 75 bytes) return 422, not 500."""
    login_rate_limiter.reset()
    gujarati_75_bytes = "અ" * 25
    assert len(gujarati_75_bytes.encode("utf-8")) == 75

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@university.edu", "password": gujarati_75_bytes},
    )
    assert resp.status_code == 422


def test_database_url_normalization():
    """S3 regression: Render/Neon postgres:// and sslmode params normalize cleanly for asyncpg."""
    raw = "postgres://user:pass@ep-test.neon.tech/neondb?sslmode=require&channel_binding=require"
    normalized = normalize_async_database_url(raw)
    assert normalized == "postgresql+asyncpg://user:pass@ep-test.neon.tech/neondb?ssl=require"
