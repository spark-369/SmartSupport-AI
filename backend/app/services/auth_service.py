"""Authentication business logic: registration, login, refresh-token rotation.

Refresh tokens are stored hashed (SHA-256); rotation is mandatory on refresh,
and reuse of a revoked token revokes the *entire* family (theft detection).
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AuthenticationError, ConflictError
from app.core.security import (
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.models.enums import UserRole
from app.schemas.auth import TokenPair, UserCreate, UserUpdate


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _count_users(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.count()).select_from(User))) or 0


async def register_user(session: AsyncSession, data: UserCreate) -> User:
    """Create a user; the very first account is promoted to admin."""
    existing = await session.scalar(select(User).where(User.email == data.email.lower()))
    if existing is not None:
        raise ConflictError("Email is already registered.")

    is_first = await _count_users(session) == 0
    user = User(
        email=data.email.lower(),
        hashed_password=hash_password(data.password),
        full_name=data.full_name.strip(),
        role=UserRole.ADMIN if is_first else UserRole.USER,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(User.email == email.lower()))


async def get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    user = await get_user_by_email(session, email)
    if user is None or not verify_password(password, user.hashed_password):
        raise AuthenticationError("Incorrect email or password.")
    if not user.is_active:
        raise AuthenticationError("This account has been deactivated.")
    return user


async def issue_token_pair(session: AsyncSession, user: User) -> tuple[TokenPair, str]:
    """Create an access token and persist a hashed refresh-token session.

    Returns ``(token_pair, raw_refresh_token)`` — the raw token exists only at
    this moment (it is stored hashed and delivered via HttpOnly cookie).
    """
    settings = get_settings()
    access = create_access_token(user.id)
    raw_refresh, exp_epoch, _jti = create_refresh_token(user.id)
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_refresh),
            expires_at=datetime.fromtimestamp(exp_epoch, tz=UTC),
        )
    )
    await session.commit()
    pair = TokenPair(
        access_token=access,
        expires_in=settings.access_token_expire_minutes * 60,
    )
    return pair, raw_refresh


async def rotate_refresh_token(session: AsyncSession, raw_refresh: str) -> tuple[TokenPair, str]:
    """Validate + rotate a refresh token. Reuse of a revoked token nukes the family."""
    payload = decode_token(raw_refresh, TokenType.REFRESH)
    row = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_refresh))
    )
    if row is None:
        raise AuthenticationError("Refresh token is not recognized.")

    if row.revoked_at is not None:
        # Token replay → possible theft: revoke every active session of the user.
        await revoke_all_for_user(session, uuid.UUID(payload.sub))
        raise AuthenticationError("Refresh token reuse detected; all sessions revoked.")

    if row.expires_at <= datetime.now(UTC):
        raise AuthenticationError("Refresh token has expired.")

    user = await session.get(User, row.user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("Account is unavailable.")

    row.revoked_at = datetime.now(UTC)
    return await issue_token_pair(session, user)


async def revoke_refresh_token(session: AsyncSession, raw_refresh: str) -> None:
    """Best-effort revocation (logout)."""
    result = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_refresh))
    )
    row = result.scalar_one_or_none()
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        await session.commit()


async def revoke_all_for_user(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Revoke every active refresh-token session of a user."""
    from sqlalchemy import update

    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    await session.commit()


async def update_profile(session: AsyncSession, user: User, data: UserUpdate) -> User:
    user.full_name = data.full_name.strip()
    await session.commit()
    await session.refresh(user)
    return user


async def change_password(
    session: AsyncSession, user: User, current_password: str, new_password: str
) -> tuple[TokenPair, str]:
    """Verify the current password, rotate the hash, and re-issue sessions.

    Every refresh token is revoked (other devices are logged out) and a fresh
    token pair is returned for the device that performed the change.
    """
    if not verify_password(current_password, user.hashed_password):
        raise AuthenticationError("Current password is incorrect.")
    user.hashed_password = hash_password(new_password)
    await session.commit()
    await revoke_all_for_user(session, user.id)
    return await issue_token_pair(session, user)
