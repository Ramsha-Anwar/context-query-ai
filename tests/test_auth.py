from datetime import datetime, timedelta, timezone
import jwt
from app.config import settings

def test_signup_valid(client):
    response = client.post("/api/v1/auth/signup", json={"email": "test@example.com", "password": "ValidPass123"})
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["role"] == "owner"
    assert "password_hash" not in data

def test_signup_duplicate_email_case_insensitive(client):
    client.post("/api/v1/auth/signup", json={"email": "Test@Example.com", "password": "ValidPass123"})
    response = client.post("/api/v1/auth/signup", json={"email": "test@example.com", "password": "ValidPass123"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"

def test_signup_weak_password(client):
    response = client.post("/api/v1/auth/signup", json={"email": "weak@example.com", "password": "abc"})
    assert response.status_code == 422
    fields = [d["field"] for d in response.json()["error"]["details"]]
    assert "body.password" in fields

def test_signup_password_over_72_bytes(client):
    response = client.post("/api/v1/auth/signup", json={"email": "emoji@example.com", "password": "😀" * 40})
    assert response.status_code == 422
    fields = [d["field"] for d in response.json()["error"]["details"]]
    assert "body.password" in fields

def test_signup_extra_field_forbidden(client):
    response = client.post("/api/v1/auth/signup", json={"email": "hacker@example.com", "password": "ValidPass123", "role": "admin"})
    assert response.status_code == 422
    fields = [d["field"] for d in response.json()["error"]["details"]]
    assert "body.role" in fields

def test_login_valid(client):
    client.post("/api/v1/auth/signup", json={"email": "login@example.com", "password": "ValidPass123"})
    response = client.post("/api/v1/auth/login", json={"email": "login@example.com", "password": "ValidPass123"})
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_login_wrong_password_and_unknown_email_look_identical(client):
    client.post("/api/v1/auth/signup", json={"email": "real@example.com", "password": "ValidPass123"})
    r1 = client.post("/api/v1/auth/login", json={"email": "real@example.com", "password": "WrongPass123"})
    r2 = client.post("/api/v1/auth/login", json={"email": "unknown@example.com", "password": "ValidPass123"})
    
    assert r1.status_code == 401
    assert r2.status_code == 401
    
    # Compare the error fields, ignoring the request_id (which is unique per request)
    err1 = r1.json()["error"]
    err2 = r2.json()["error"]
    
    assert err1["code"] == err2["code"]
    assert err1["message"] == err2["message"]
    assert err1["status"] == err2["status"]
    assert err1["details"] == err2["details"]
def test_protected_route_no_header(client):
    response = client.get("/api/v1/protected")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_MISSING"

def test_protected_route_garbage_token(client):
    response = client.get("/api/v1/protected", headers={"Authorization": "Bearer not.a.jwt"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_INVALID"

def test_protected_route_expired_token(client):
    client.post("/api/v1/auth/signup", json={"email": "expired@example.com", "password": "ValidPass123"})
    login = client.post("/api/v1/auth/login", json={"email": "expired@example.com", "password": "ValidPass123"})
    user_id = jwt.decode(login.json()["access_token"], options={"verify_signature": False})["sub"]
    
    now = datetime.now(timezone.utc)
    expired_token = jwt.encode(
        {"sub": user_id, "role": "owner", "iat": now - timedelta(hours=2), "exp": now - timedelta(hours=1)},
        settings.JWT_SECRET_KEY, algorithm="HS256"
    )
    response = client.get("/api/v1/protected", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_EXPIRED"

def test_protected_route_valid_token(client):
    client.post("/api/v1/auth/signup", json={"email": "valid@example.com", "password": "ValidPass123"})
    login = client.post("/api/v1/auth/login", json={"email": "valid@example.com", "password": "ValidPass123"})
    response = client.get("/api/v1/protected", headers={"Authorization": f"Bearer {login.json()['access_token']}"})
    assert response.status_code == 200

def test_change_password_success_and_login(client):
    client.post("/api/v1/auth/signup", json={"email": "change@example.com", "password": "OldPass123"})
    login = client.post("/api/v1/auth/login", json={"email": "change@example.com", "password": "OldPass123"})
    token = login.json()["access_token"]

    response = client.put(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "OldPass123", "new_password": "NewPass456"}
    )
    assert response.status_code == 200

    old_login = client.post("/api/v1/auth/login", json={"email": "change@example.com", "password": "OldPass123"})
    assert old_login.status_code == 401

    new_login = client.post("/api/v1/auth/login", json={"email": "change@example.com", "password": "NewPass456"})
    assert new_login.status_code == 200

def test_change_password_wrong_current_password(client):
    client.post("/api/v1/auth/signup", json={"email": "wrongcur@example.com", "password": "OldPass123"})
    login = client.post("/api/v1/auth/login", json={"email": "wrongcur@example.com", "password": "OldPass123"})
    response = client.put(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        json={"current_password": "WrongOldPass", "new_password": "NewPass456"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"

def test_change_password_requires_auth(client):
    response = client.put("/api/v1/auth/change-password", json={"current_password": "OldPass123", "new_password": "NewPass456"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_MISSING"

def test_change_password_weak_new_password(client):
    client.post("/api/v1/auth/signup", json={"email": "weaknew@example.com", "password": "OldPass123"})
    login = client.post("/api/v1/auth/login", json={"email": "weaknew@example.com", "password": "OldPass123"})
    response = client.put(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        json={"current_password": "OldPass123", "new_password": "abc"}
    )
    assert response.status_code == 422
    assert "body.new_password" in [d["field"] for d in response.json()["error"]["details"]]