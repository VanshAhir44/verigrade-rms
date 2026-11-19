from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_roles
from app.core.rate_limit import enforce_login_rate_limit, enforce_refresh_rate_limit
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.auth import (
    CreateUserRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    TokenResponse,
    UserResponse,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication & RBAC"])


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(enforce_login_rate_limit)],
)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    user = await auth_service.authenticate_user(db, payload.email, payload.password)
    return await auth_service.issue_token_pair(db, user)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    dependencies=[Depends(enforce_refresh_rate_limit)],
)
async def refresh_tokens(
    payload: RefreshRequest, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    return await auth_service.rotate_refresh_token(db, payload.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: LogoutRequest,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Revokes the supplied refresh token directly so logout works even after access token expiry."""
    await auth_service.revoke_refresh_token(db, payload.refresh_token)


@router.get("/me", response_model=UserResponse)
async def read_current_user(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    payload: CreateUserRequest,
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    created = await auth_service.create_user_account(db, payload, actor=admin_user)
    return UserResponse.model_validate(created)


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    role: Optional[UserRole] = Query(default=None),
    _admin_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> list[UserResponse]:
    users = await auth_service.list_users(db, role=role)
    return [UserResponse.model_validate(u) for u in users]
