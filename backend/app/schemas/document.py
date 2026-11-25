"""Document schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import DocumentStatus


class DocumentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    original_filename: str
    file_type: str
    size_bytes: int
    status: DocumentStatus
    error: str | None
    chunk_count: int
    created_at: datetime
    updated_at: datetime
