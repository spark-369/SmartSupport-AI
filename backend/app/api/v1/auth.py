"""Authentication endpoints: register, login, refresh (HttpOnly cookie), logout, me."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.deps import CurrentUser, DbSession, ip_rate_limit_strict
from app.core.config import get_settings
from app.core.errors import AuthenticationError
from app.schemas.auth import (
    LoginRequest,
    PasswordChange,
    TokenPair,
    UserCreate,
    UserPublic,
    UserUpdate,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

_register_limit = ip_rate_limit_strict("register", get_settings().rate_limit_register_per_minute, 60)
_login_limit = ip_rate_limit_strict("login", get_settings().rate_limit_login_per_minute, 60)
_refresh_limit = ip_rate_limit_strict("refresh", 30, 60)


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        max_age=settings.refresh_token_expire_days * 86400,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/api/v1/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(get_settings().refresh_cookie_name, path="/api/v1/auth")


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserCreate,
    db: DbSession,
    _: None = Depends(_register_limit),
) -> UserPublic:
    """Create an account. The first account in a fresh deployment becomes admin."""
    user = await auth_service.register_user(db, payload)
    return UserPublic.model_validate(user)


@router.post("/login", response_model=TokenPair)
async def login(
    payload: LoginRequest,
    response: Response,
    db: DbSession,
    _: None = Depends(_login_limit),
) -> TokenPair:
    """Password login → access token in body + HttpOnly refresh cookie."""
    user = await auth_service.authenticate(db, payload.email, payload.password)
    tokens, raw_refresh = await auth_service.issue_token_pair(db, user)
    _set_refresh_cookie(response, raw_refresh)
    return tokens


@router.post("/refresh", response_model=TokenPair)
async def refresh(request: Request, response: Response, db: DbSession, _: None = Depends(_refresh_limit)) -> TokenPair:
    """Rotate the refresh cookie and mint a fresh access token."""
    raw = request.cookies.get(get_settings().refresh_cookie_name)
    if not raw:
        raise AuthenticationError("Missing refresh token.")
    tokens, new_raw = await auth_service.rotate_refresh_token(db, raw)
    _set_refresh_cookie(response, new_raw)
    return tokens


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, db: DbSession, _: None = Depends(_refresh_limit)) -> Response:
    raw = request.cookies.get(get_settings().refresh_cookie_name)
    if raw:
        await auth_service.revoke_refresh_token(db, raw)
    _clear_refresh_cookie(response)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserPublic)
async def me(user: CurrentUser) -> UserPublic:
    return UserPublic.model_validate(user)


@router.patch("/me", response_model=UserPublic)
async def update_me(payload: UserUpdate, user: CurrentUser, db: DbSession) -> UserPublic:
    """Update the signed-in user's profile (display name)."""
    updated = await auth_service.update_profile(db, user, payload)
    return UserPublic.model_validate(updated)


@router.post("/password", response_model=TokenPair)
async def change_password(
    payload: PasswordChange,
    response: Response,
    user: CurrentUser,
    db: DbSession,
) -> TokenPair:
    """Rotate the password.

    Every refresh session is revoked (other devices are signed out) and a
    fresh token pair + cookie is issued for the current device.
    """
    tokens, raw_refresh = await auth_service.change_password(
        db, user, payload.current_password, payload.new_password
    )
    _set_refresh_cookie(response, raw_refresh)
    return tokens
