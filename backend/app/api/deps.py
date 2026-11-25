"""FastAPI dependencies: auth, RBAC, rate limiting, RAG singletons."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AuthenticationError, AuthorizationError
from app.core.rate_limit import client_ip, limiter, raise_if_blocked
from app.core.security import TokenType, decode_token
from app.db.session import get_db
from app.models.user import User
from app.services.auth_service import get_user_by_id
from app.services.embedding import EmbeddingService, get_embedding_service
from app.services.rag.chains import OllamaRAG

_bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: DbSession,
) -> User:
    """Resolve the Bearer access token to an active user."""
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Missing bearer token.")
    payload = decode_token(credentials.credentials, TokenType.ACCESS)
    try:
        user_id = uuid.UUID(payload.sub)
    except ValueError as exc:
        raise AuthenticationError("Malformed token subject.") from exc
    user = await get_user_by_id(db, user_id)
    if user is None:
        raise AuthenticationError("User no longer exists.")
    if not user.is_active:
        raise AuthenticationError("Account is deactivated.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise AuthorizationError("Admin privileges required.")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


# ---------------------------------------------------------------------------
# Rate limiting (user scope lives here to avoid a circular import with auth)
# ---------------------------------------------------------------------------


def user_rate_limit(scope: str, limit: int, window_seconds: int):
    """Return a dependency that rate-limits per authenticated user."""

    async def dependency(request: Request, user: CurrentUser) -> None:
        result = await limiter.hit(f"rl:{scope}:user:{user.id}", limit, window_seconds)
        raise_if_blocked(result)

    return dependency


def ip_rate_limit_strict(scope: str, limit: int, window_seconds: int):
    """Alias for symmetry at call sites (IP-scoped limiter lives in core)."""
    from app.core.rate_limit import ip_rate_limit

    return ip_rate_limit(scope, limit, window_seconds)


# ---------------------------------------------------------------------------
# RAG singletons
# ---------------------------------------------------------------------------

_rag_singleton: OllamaRAG | None = None


def get_rag() -> OllamaRAG:
    global _rag_singleton
    if _rag_singleton is None:
        _rag_singleton = OllamaRAG(get_settings())
    return _rag_singleton


def get_embedder() -> EmbeddingService:
    return get_embedding_service()


RAGDep = Annotated[OllamaRAG, Depends(get_rag)]
EmbedderDep = Annotated[EmbeddingService, Depends(get_embedder)]
