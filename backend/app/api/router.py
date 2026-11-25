"""Aggregate API router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import analytics, auth, chat, documents, health, products, search, tickets

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(products.router)
api_router.include_router(documents.router)
api_router.include_router(chat.router)
api_router.include_router(search.router)
api_router.include_router(analytics.router)
api_router.include_router(tickets.router)
