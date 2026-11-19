import uuid
from datetime import datetime, timezone
from typing import Optional

import jwt
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    dummy_verify_password_async,
    hash_password_async,
    hash_token,
    verify_password_async,
)
from app.models.audit import AuditLog
from app.models.user import RefreshToken, User, UserRole
from app.schemas.auth import CreateUserRequest, TokenResponse, UserResponse


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    normalized_email = email.strip().lower()
    result = await db.execute(select(User).where(User.email == normalized_email))
    user = result.scalar_one_or_none()

    if user is None:
        # Equalize response timing to mitigate email enumeration
        await dummy_verify_password_async(password)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    valid = await verify_password_async(password, user.password_hash)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )
    return user


async def issue_token_pair(db: AsyncSession, user: User) -> TokenResponse:
    access_token, expires_in = create_access_token(user.id, user.role.value)
    refresh_token, refresh_exp = create_refresh_token(user.id, user.role.value)

    token_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        expires_at=refresh_exp,
    )
    db.add(token_record)
    await db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        user=UserResponse.model_validate(user),
    )


async def revoke_all_user_refresh_tokens(db: AsyncSession, user_id: uuid.UUID, now: datetime) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await db.commit()


async def rotate_refresh_token(db: AsyncSession, raw_refresh_token: str) -> TokenResponse:
    try:
        payload = decode_token(raw_refresh_token, expected_type="refresh")
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    token_digest = hash_token(raw_refresh_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_digest,
            RefreshToken.user_id == user_id,
        )
    )
    stored_token = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if stored_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is unknown",
        )

    if stored_token.revoked_at is not None:
        # Reuse detection: replay of an already-rotated token revokes all active sessions for this user
        await revoke_all_user_refresh_tokens(db, user_id, now)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token reuse detected; all sessions revoked",
        )

    expires_at = stored_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired",
        )

    # Atomic conditional claim prevents concurrent double-rotation race (P1-6)
    claim_result = await db.execute(
        update(RefreshToken)
        .where(RefreshToken.id == stored_token.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    if claim_result.rowcount != 1:
        await revoke_all_user_refresh_tokens(db, user_id, now)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token already rotated",
        )

    user_res = await db.execute(select(User).where(User.id == user_id))
    user = user_res.scalar_one_or_none()
    if user is None or not user.is_active:
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or inactive",
        )

    return await issue_token_pair(db, user)


async def revoke_refresh_token(db: AsyncSession, raw_refresh_token: str) -> None:
    token_digest = hash_token(raw_refresh_token)
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == token_digest, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    await db.commit()


async def create_user_account(
    db: AsyncSession,
    payload: CreateUserRequest,
    actor: User,
) -> User:
    normalized_email = payload.email.strip().lower()
    if payload.role == UserRole.STUDENT and not payload.enrollment_no:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="enrollment_no is required for student accounts",
        )

    existing = await db.execute(select(User).where(User.email == normalized_email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    if payload.enrollment_no:
        existing_enr = await db.execute(
            select(User).where(User.enrollment_no == payload.enrollment_no.strip())
        )
        if existing_enr.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A student with this enrollment number already exists",
            )

    pw_hash = await hash_password_async(payload.password)
    new_user = User(
        email=normalized_email,
        password_hash=pw_hash,
        full_name=payload.full_name.strip(),
        role=payload.role,
        enrollment_no=payload.enrollment_no.strip() if payload.enrollment_no else None,
        is_active=True,
    )
    db.add(new_user)
    await db.flush()

    audit = AuditLog(
        actor_id=actor.id,
        action="USER_CREATED",
        entity_type="user",
        entity_id=str(new_user.id),
        old_value_json=None,
        new_value_json={
            "email": new_user.email,
            "full_name": new_user.full_name,
            "role": new_user.role.value,
            "enrollment_no": new_user.enrollment_no,
        },
    )
    db.add(audit)
    await db.commit()
    await db.refresh(new_user)
    return new_user


async def list_users(db: AsyncSession, role: Optional[UserRole] = None) -> list[User]:
    stmt = select(User).order_by(User.created_at.asc())
    if role is not None:
        stmt = stmt.where(User.role == role)
    result = await db.execute(stmt)
    return list(result.scalars().all())
