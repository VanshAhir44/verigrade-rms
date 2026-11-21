import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.user import User
from tests.conftest import TEST_ADMIN_PW, TEST_FACULTY_PW, TEST_STUDENT1_PW


async def _login(client: AsyncClient, email: str, password: str) -> dict:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": "connected"}


@pytest.mark.asyncio
async def test_login_me_refresh_rotation_and_logout(client: AsyncClient):
    # Wrong password rejected
    bad = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@university.edu", "password": "WrongPassword99!"},
    )
    assert bad.status_code == 401

    # Valid login returns access + refresh tokens
    tokens = await _login(client, "admin@university.edu", TEST_ADMIN_PW)
    assert tokens["token_type"] == "bearer"
    assert tokens["user"]["role"] == "admin"

    # /me works with access token
    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == "admin@university.edu"

    # Refresh token rotates and invalidates previous refresh token
    refreshed = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refreshed.status_code == 200
    new_tokens = refreshed.json()
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    # Reusing the rotated (old) refresh token fails
    reused = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert reused.status_code == 401

    # Logout revokes the active refresh token
    logout_resp = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {new_tokens['access_token']}"},
        json={"refresh_token": new_tokens["refresh_token"]},
    )
    assert logout_resp.status_code == 204

    after_logout = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": new_tokens["refresh_token"]},
    )
    assert after_logout.status_code == 401


@pytest.mark.asyncio
async def test_rbac_admin_can_create_and_list_users_with_audit_log(
    client: AsyncClient, seeded_db: AsyncSession
):
    admin_tokens = await _login(client, "admin@university.edu", TEST_ADMIN_PW)
    faculty_tokens = await _login(client, "faculty@university.edu", TEST_FACULTY_PW)
    student_tokens = await _login(client, "student1@university.edu", TEST_STUDENT1_PW)

    new_student_payload = {
        "email": "student3@university.edu",
        "password": "NewStudent@2026!",
        "full_name": "Kabir Mehta",
        "role": "student",
        "enrollment_no": "ENR2026CS003",
    }

    # Unauthenticated request -> 401
    unauth = await client.post("/api/v1/auth/users", json=new_student_payload)
    assert unauth.status_code == 401

    # Faculty & Student -> 403 Forbidden
    for non_admin in (faculty_tokens, student_tokens):
        res = await client.post(
            "/api/v1/auth/users",
            headers={"Authorization": f"Bearer {non_admin['access_token']}"},
            json=new_student_payload,
        )
        assert res.status_code == 403

        list_res = await client.get(
            "/api/v1/auth/users",
            headers={"Authorization": f"Bearer {non_admin['access_token']}"},
        )
        assert list_res.status_code == 403

    # Admin -> 201 Created
    created = await client.post(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
        json=new_student_payload,
    )
    assert created.status_code == 201, created.text
    created_body = created.json()
    assert created_body["enrollment_no"] == "ENR2026CS003"

    # Verify AuditLog recorded the creation
    audit_rows = (
        await seeded_db.execute(
            select(AuditLog).where(
                AuditLog.action == "USER_CREATED",
                AuditLog.entity_id == created_body["id"],
            )
        )
    ).scalars().all()
    assert len(audit_rows) == 1
    assert audit_rows[0].new_value_json["email"] == "student3@university.edu"

    # Admin can filter listed users by role
    students_resp = await client.get(
        "/api/v1/auth/users?role=student",
        headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
    )
    assert students_resp.status_code == 200
    assert len(students_resp.json()) == 3


@pytest.mark.asyncio
async def test_inactive_user_cannot_login(client: AsyncClient, seeded_db: AsyncSession):
    res = await seeded_db.execute(select(User).where(User.email == "student2@university.edu"))
    student2 = res.scalar_one()
    student2.is_active = False
    await seeded_db.commit()

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "student2@university.edu", "password": "Student2Test@2026!"},
    )
    assert resp.status_code == 403
