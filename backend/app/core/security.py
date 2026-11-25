"""Password hashing (bcrypt) and JWT issuing/verification (PyJWT)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum

import bcrypt
import jwt

from app.core.config import get_settings
from app.core.errors import AuthenticationError

_BCRYPT_ROUNDS = 12
_MAX_BCRYPT_BYTES = 72  # bcrypt silently truncates beyond this


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"


@dataclass(frozen=True)
class TokenPayload:
    sub: str
    type: TokenType
    jti: str
    exp: int
    iat: int


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt (12 rounds)."""
    return bcrypt.hashpw(password.encode("utf-8")[:_MAX_BCRYPT_BYTES], bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Constant-time password verification; returns False on any mismatch/malform."""
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:_MAX_BCRYPT_BYTES], hashed.encode("utf-8"))
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------


def _create_token(user_id: uuid.UUID, token_type: TokenType, lifetime: timedelta) -> tuple[str, int, str]:
    """Build a signed JWT. Returns ``(token, exp_epoch, jti)``."""
    settings = get_settings()
    now = datetime.now(UTC)
    jti = uuid.uuid4().hex
    exp = int((now + lifetime).timestamp())
    payload = {
        "sub": str(user_id),
        "type": token_type.value,
        "iat": int(now.timestamp()),
        "exp": exp,
        "jti": jti,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, exp, jti


def create_access_token(user_id: uuid.UUID) -> str:
    settings = get_settings()
    token, _, _ = _create_token(
        user_id, TokenType.ACCESS, timedelta(minutes=settings.access_token_expire_minutes)
    )
    return token


def create_refresh_token(user_id: uuid.UUID) -> tuple[str, int, str]:
    """Returns ``(token, exp_epoch, jti)`` — the hash of ``token`` is persisted server-side."""
    settings = get_settings()
    return _create_token(user_id, TokenType.REFRESH, timedelta(days=settings.refresh_token_expire_days))


def decode_token(token: str, expected_type: TokenType) -> TokenPayload:
    """Verify signature/expiry/type and return the payload.

    Raises :class:`AuthenticationError` for any invalid token.
    """
    settings = get_settings()
    try:
        raw = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "iat", "sub", "type", "jti"]},
        )
    except jwt.PyJWTError as exc:
        raise AuthenticationError(f"Invalid token: {exc.__class__.__name__}") from exc

    if raw.get("type") != expected_type.value:
        raise AuthenticationError(f"Expected a {expected_type.value} token.")

    return TokenPayload(
        sub=str(raw["sub"]),
        type=expected_type,
        jti=str(raw["jti"]),
        exp=int(raw["exp"]),
        iat=int(raw["iat"]),
    )
