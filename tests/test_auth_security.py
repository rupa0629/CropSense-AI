from fastapi.testclient import TestClient

from api_server import app
from utils.auth_db import (
    create_password_reset_token,
    get_user_by_email,
    init_db,
)


client = TestClient(app)
PASSWORD = "StrongPass1!"


def register_and_login(email="farmer@example.com"):
    registration = client.post(
        "/auth/register",
        json={"full_name": "Test Farmer", "email": email, "password": PASSWORD},
    )
    assert registration.status_code == 200
    login = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200
    return login.json()


def test_register_login_refresh_logout_flow():
    init_db()
    tokens = register_and_login()

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "farmer@example.com"

    refreshed = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200
    assert refreshed.json()["refresh_token"] != tokens["refresh_token"]

    reused = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reused.status_code == 401


def test_duplicate_registration_and_weak_password_are_rejected():
    init_db()
    register_and_login()
    duplicate = client.post(
        "/auth/register",
        json={"full_name": "Duplicate", "email": "farmer@example.com", "password": PASSWORD},
    )
    weak = client.post(
        "/auth/register",
        json={"full_name": "Weak", "email": "weak@example.com", "password": "password"},
    )
    assert duplicate.status_code == 400
    assert weak.status_code == 400


def test_password_reset_token_is_single_use_and_revokes_old_password():
    init_db()
    register_and_login()
    user = get_user_by_email("farmer@example.com")
    token = "test-reset-token"
    create_password_reset_token(user["id"], token)

    reset = client.post(
        "/auth/reset-password",
        json={"reset_token": token, "new_password": "NewStrongPass2!"},
    )
    assert reset.status_code == 200
    assert client.post(
        "/auth/reset-password",
        json={"reset_token": token, "new_password": "AnotherPass3!"},
    ).status_code == 400
    assert client.post(
        "/auth/login", json={"email": "farmer@example.com", "password": PASSWORD}
    ).status_code == 401


def test_protected_endpoint_and_invalid_upload_are_rejected():
    init_db()
    assert client.get("/dashboard").status_code == 401
    tokens = register_and_login()
    response = client.post(
        "/predict",
        files={"image": ("leaf.txt", b"not an image", "text/plain")},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 400
