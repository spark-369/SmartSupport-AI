"""FastAPI application factory and ASGI entrypoint (``uvicorn app.main:app``)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core import cache
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import get_logger, setup_logging

logger = get_logger("main")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(settings.log_level)
    try:
        cache.init_redis(settings.redis_url)
        logger.info("Redis cache initialized (%s)", settings.redis_url)
    except Exception as exc:  # rate limiter/caches degrade gracefully
        logger.warning("Redis unavailable at startup (%s) — running degraded", exc)

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    logger.info(
        "%s v%s ready | env=%s | models: embed=%s llm=%s",
        settings.app_name,
        settings.app_version,
        settings.environment,
        settings.embedding_model,
        settings.llm_model,
    )
    yield
    await cache.close_redis()
    logger.info("Shutdown complete.")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "RAG-based customer support bot over product manuals.\n\n"
            "* FastAPI + Pydantic v2 + JWT auth\n"
            "* Celery/Redis ingestion, Redis rate limiting & caching\n"
            "* LangChain orchestration with Ollama native JSON-schema outputs\n"
            "* PostgreSQL 16 (JSONB / float4[] embeddings) + NumPy cosine retrieval"
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/", tags=["meta"])
    async def root() -> dict:
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
            "docs": "/docs",
            "health": f"{settings.api_v1_prefix}/health",
        }

    return app


app = create_app()
