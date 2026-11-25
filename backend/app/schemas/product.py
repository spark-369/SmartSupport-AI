"""Product schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


class ProductCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str | None = Field(default=None, pattern=SLUG_PATTERN, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    version: str | None = Field(default=None, max_length=40)


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    slug: str | None = Field(default=None, pattern=SLUG_PATTERN, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    version: str | None = Field(default=None, max_length=40)
    is_active: bool | None = None


class ProductPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    version: str | None
    is_active: bool
    document_count: int = 0
    pending_count: int = 0
    processing_count: int = 0
    ready_count: int = 0
    failed_count: int = 0
    total_chunks: int = 0
    created_at: datetime
