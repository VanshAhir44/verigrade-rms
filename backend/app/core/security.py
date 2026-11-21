import asyncio
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import settings

MAX_BCRYPT_PASSWORD_BYTES = 72
# Precomputed dummy hash used to equalize timing when a login email does not exist
_DUMMY_BCRYPT_HASH = bcrypt.hashpw(b"dummy-timing-equalization-password", bcrypt.gensalt(rounds=12)).decode("utf-8")


def validate_password_byte_length(plain_password: str) -> None:
    if len(plain_password.encode("utf-8")) > MAX_BCRYPT_PASSWORD_BYTES:
        raise ValueError(f"Password must not exceed {MAX_BCRYPT_PASSWORD_BYTES} UTF-8 bytes")


def hash_password(plain_password: str) -> str:
    validate_password_byte_length(plain_password)
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    pw_bytes = plain_password.encode("utf-8")
    if len(pw_bytes) > MAX_BCRYPT_PASSWORD_BYTES:
        return False
    try:
        return bcrypt.checkpw(pw_bytes, password_hash.encode("utf-8"))
    except ValueError:
        return False


async def hash_password_async(plain_password: str) -> str:
    return await asyncio.to_thread(hash_password, plain_password)


async def verify_password_async(plain_password: str, password_hash: str) -> bool:
    return await asyncio.to_thread(verify_password, plain_password, password_hash)


async def dummy_verify_password_async(plain_password: str) -> None:
    await asyncio.to_thread(verify_password, plain_password, _DUMMY_BCRYPT_HASH)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _require_signing_key() -> str:
    key = settings.JWT_SIGNING_KEY
    if not key or len(key) < 32:
        raise RuntimeError(
            "JWT_SIGNING_KEY must be configured via environment variable (minimum 32 characters)."
        )
    return key


def create_access_token(user_id: uuid.UUID, role: str) -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire_at = now + expires_delta
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int(expire_at.timestamp()),
    }
    encoded = jwt.encode(payload, _require_signing_key(), algorithm=settings.JWT_ALGORITHM)
    return encoded, int(expires_delta.total_seconds())


def create_refresh_token(user_id: uuid.UUID, role: str) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expire_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "type": "refresh",
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int(expire_at.timestamp()),
    }
    encoded = jwt.encode(payload, _require_signing_key(), algorithm=settings.JWT_ALGORITHM)
    return encoded, expire_at


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    payload = jwt.decode(
        token,
        _require_signing_key(),
        algorithms=[settings.JWT_ALGORITHM],
    )
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"Expected {expected_type} token")
    return payload
