"""Celery application factory (Redis broker + result backend)."""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "smartsupport",
    broker=settings.broker_url,
    backend=settings.result_backend_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=1800,
    task_soft_time_limit=1500,
    broker_connection_retry_on_startup=True,
    worker_prefetch_multiplier=1,
    result_expires=86400,
    task_default_queue="ingestion",
)
