"""Authentication flow tests: register, login, rotation, reuse detection, logout."""

from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import ADMIN, MEMBER, auth_headers, register_and_login


async def test_first_user_becomes_admin(client: AsyncClient):
    headers = await register_and_login(client, ADMIN)
    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["role"] == "admin"


async def test_second_user_is_member(client: AsyncClient, admin_headers, member_headers):
    me = await client.get("/api/v1/auth/me", headers=member_headers)
    assert me.json()["role"] == "user"


async def test_duplicate_email_conflict(client: AsyncClient, admin_headers):
    response = await client.post("/api/v1/auth/register", json=ADMIN)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


async def test_weak_password_rejected(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "weak@test.io", "password": "short", "full_name": "W"},
    )
    assert response.status_code == 422


async def test_login_wrong_password(client: AsyncClient, admin_headers):
    response = await client.post(
        "/api/v1/auth/login", json={"email": ADMIN["email"], "password": "Nope12345"}
    )
    assert response.status_code == 401


async def test_refresh_rotation_and_reuse_detection(client: AsyncClient, admin_headers):
    # Login again to grab a cookie we can replay.
    await client.post(
        "/api/v1/auth/login", json={"email": ADMIN["email"], "password": ADMIN["password"]}
    )
    old_cookie = client.cookies.get("ss_refresh_token")
    assert old_cookie

    first = await client.post("/api/v1/auth/refresh")
    assert first.status_code == 200
    new_cookie = client.cookies.get("ss_refresh_token")
    assert new_cookie and new_cookie != old_cookie

    # Replay the OLD (already rotated) token → reuse detection revokes everything.
    client.cookies.set("ss_refresh_token", old_cookie)
    replay = await client.post("/api/v1/auth/refresh")
    assert replay.status_code == 401
    assert "reuse" in replay.json()["error"]["message"].lower()

    # Even the newest token is dead now (whole family revoked).
    client.cookies.set("ss_refresh_token", new_cookie)
    second = await client.post("/api/v1/auth/refresh")
    assert second.status_code == 401


async def test_logout_revokes_cookie(client: AsyncClient, admin_headers):
    logout = await client.post("/api/v1/auth/logout")
    assert logout.status_code == 204
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 401


async def test_me_requires_token(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_update_me_full_name(client: AsyncClient, admin_headers):
    patched = await client.patch(
        "/api/v1/auth/me", json={"full_name": "Grace Hopper"}, headers=admin_headers
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["full_name"] == "Grace Hopper"

    me = await client.get("/api/v1/auth/me", headers=admin_headers)
    assert me.json()["full_name"] == "Grace Hopper"


async def test_update_me_requires_auth(client: AsyncClient):
    response = await client.patch("/api/v1/auth/me", json={"full_name": "X"})
    assert response.status_code == 401


async def test_update_me_rejects_blank_name(client: AsyncClient, admin_headers):
    response = await client.patch("/api/v1/auth/me", json={"full_name": ""}, headers=admin_headers)
    assert response.status_code == 422


async def test_change_password_flow(client: AsyncClient, admin_headers):
    # Wrong current password → 401.
    bad = await client.post(
        "/api/v1/auth/password",
        json={"current_password": "wrong-password", "new_password": "NewPass123"},
        headers=admin_headers,
    )
    assert bad.status_code == 401

    # Weak new password → 422.
    weak = await client.post(
        "/api/v1/auth/password",
        json={"current_password": ADMIN["password"], "new_password": "short"},
        headers=admin_headers,
    )
    assert weak.status_code == 422

    # Successful change: returns a fresh token pair and sets a new cookie.
    ok = await client.post(
        "/api/v1/auth/password",
        json={"current_password": ADMIN["password"], "new_password": "NewPass123"},
        headers=admin_headers,
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["access_token"]

    # The old password no longer works.
    old_login = await client.post(
        "/api/v1/auth/login", json={"email": ADMIN["email"], "password": ADMIN["password"]}
    )
    assert old_login.status_code == 401

    # The new password works.
    new_login = await client.post(
        "/api/v1/auth/login", json={"email": ADMIN["email"], "password": "NewPass123"}
    )
    assert new_login.status_code == 200

    # The cookie issued by the change call is valid (current device stays signed in).
    refreshed = await client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200


async def test_garbage_token_rejected(client: AsyncClient):
    response = await client.get("/api/v1/auth/me", headers=auth_headers("garbage"))
    assert response.status_code == 401
