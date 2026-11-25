"""Auth & user schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import UserRole


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128, description="Plaintext password (bcrypt-hashed server-side).")
    full_name: str = Field(min_length=1, max_length=120)


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


class TokenPair(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserUpdate(BaseModel):
    """Editable profile fields (email/role are immutable by design)."""

    full_name: str = Field(min_length=1, max_length=120)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
