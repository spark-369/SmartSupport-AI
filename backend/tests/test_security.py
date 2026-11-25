"""Unit tests for password hashing and JWT helpers."""

from __future__ import annotations

import uuid

import jwt as pyjwt
import pytest

from app.core.config import get_settings
from app.core.errors import AuthenticationError
from app.core.security import (
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

USER_ID = uuid.uuid4()


def test_password_hash_roundtrip():
    hashed = hash_password("S3cure-Pass!")
    assert hashed != "S3cure-Pass!"
    assert hashed.startswith("$2b$")
    assert verify_password("S3cure-Pass!", hashed)
    assert not verify_password("wrong", hashed)


def test_verify_password_malformed_hash():
    assert not verify_password("x", "not-a-bcrypt-hash")


def test_access_token_roundtrip():
    token = create_access_token(USER_ID)
    payload = decode_token(token, TokenType.ACCESS)
    assert payload.sub == str(USER_ID)
    assert payload.type is TokenType.ACCESS


def test_refresh_token_roundtrip_and_jti():
    token, exp, jti = create_refresh_token(USER_ID)
    payload = decode_token(token, TokenType.REFRESH)
    assert payload.jti == jti
    assert payload.exp == exp
    assert payload.exp > payload.iat


def test_wrong_token_type_rejected():
    access = create_access_token(USER_ID)
    with pytest.raises(AuthenticationError):
        decode_token(access, TokenType.REFRESH)


def test_tampered_token_rejected():
    token = create_access_token(USER_ID)[:-3] + "abc"
    with pytest.raises(AuthenticationError):
        decode_token(token, TokenType.ACCESS)


def test_wrong_secret_rejected():
    token = create_access_token(USER_ID)
    original = get_settings().jwt_secret
    try:
        get_settings().jwt_secret = "another-secret"
        with pytest.raises(AuthenticationError):
            decode_token(token, TokenType.ACCESS)
    finally:
        get_settings().jwt_secret = original
