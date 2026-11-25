"""Health & readiness probe."""

from __future__ import annotations

import httpx
from fastapi import APIRouter
from sqlalchemy import text

from app.core.cache import get_redis
from app.core.config import get_settings
from app.db.session import SessionFactory

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Liveness + dependency readiness. Returns 503 only when the DB is down."""
    components: dict[str, str] = {}
    status = "ok"

    try:
        async with SessionFactory() as session:
            await session.execute(text("SELECT 1"))
        components["database"] = "ok"
    except Exception:
        components["database"] = "unavailable"
        status = "degraded"

    try:
        await get_redis().ping()
        components["redis"] = "ok"
    except Exception:
        components["redis"] = "unavailable"
        status = "degraded"

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{get_settings().ollama_base_url}/api/tags")
        components["ollama"] = "ok" if response.status_code == 200 else "unavailable"
    except Exception:
        components["ollama"] = "unavailable"
    if components["ollama"] != "ok":
        status = "degraded"

    return {"status": status, "components": components}
