"""Domain error hierarchy + FastAPI exception handlers (consistent error envelopes)."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger("errors")


class AppError(Exception):
    """Base class for all expected, user-facing application errors."""

    status_code: int = 500
    code: str = "internal_error"
    message: str = "Internal server error."

    def __init__(
        self,
        message: str | None = None,
        *,
        status_code: int | None = None,
        code: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.message
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code
        self.headers = headers
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    message = "Resource not found."


class AuthenticationError(AppError):
    status_code = 401
    code = "unauthorized"
    message = "Invalid or expired credentials."

    def __init__(self, message: str | None = None, **kwargs) -> None:
        kwargs.setdefault("headers", {"WWW-Authenticate": "Bearer"})
        super().__init__(message, **kwargs)


class AuthorizationError(AppError):
    status_code = 403
    code = "forbidden"
    message = "You do not have permission to perform this action."


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
    message = "Resource conflict."


class RateLimitError(AppError):
    status_code = 429
    code = "rate_limited"
    message = "Too many requests. Please slow down."


class ExternalServiceError(AppError):
    status_code = 502
    code = "external_service_error"
    message = "An external dependency is unavailable."


def _sanitize_details(details: list[dict]) -> list[dict]:
    """Make pydantic error details JSON-safe without echoing user input."""
    clean: list[dict] = []
    for item in details:
        item = dict(item)
        item.pop("input", None)  # never echo user input back
        item.pop("url", None)
        ctx = item.get("ctx")
        if isinstance(ctx, dict):
            # Custom validators put the raw exception in ctx["error"], which is
            # not JSON-serializable — coerce every ctx value to a primitive.
            item["ctx"] = {
                key: value if isinstance(value, (str, int, float, bool)) or value is None else str(value)
                for key, value in ctx.items()
            }
        clean.append(item)
    return clean


def register_exception_handlers(app: FastAPI) -> None:
    """Attach uniform JSON error handlers to the app."""

    @app.exception_handler(AppError)
    async def _app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed.",
                    "details": _sanitize_details(exc.errors()),
                }
            },
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": "Internal server error."}},
        )
