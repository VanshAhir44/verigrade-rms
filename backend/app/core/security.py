import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import settings


def hash_password(plain_password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


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
