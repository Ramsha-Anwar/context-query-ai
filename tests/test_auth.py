def test_signup_valid(client):
    response = client.post("/api/v1/auth/signup", json={
        "email": "test@example.com",
        "password": "ValidPass123"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["role"] == "owner"
    assert "password_hash" not in data
    assert "id" in data

def test_signup_duplicate_email_case_insensitive(client):
    # First signup
    client.post("/api/v1/auth/signup", json={
        "email": "Test@Example.com",
        "password": "ValidPass123"
    })
    # Second signup with different casing
    response = client.post("/api/v1/auth/signup", json={
        "email": "test@example.com",
        "password": "ValidPass123"
    })
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"

def test_signup_weak_password(client):
    response = client.post("/api/v1/auth/signup", json={
        "email": "weak@example.com",
        "password": "abc"
    })
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
    # Check that the field is mapped correctly
    fields = [d["field"] for d in data["error"]["details"]]
    assert "body.password" in fields

def test_signup_password_over_72_bytes(client):
    # 40 emojis * 4 bytes = 160 bytes
    emoji_password = "😀" * 40
    response = client.post("/api/v1/auth/signup", json={
        "email": "emoji@example.com",
        "password": emoji_password
    })
    assert response.status_code == 422
    data = response.json()
    fields = [d["field"] for d in response.json()["error"]["details"]]
    assert "body.password" in fields

def test_signup_extra_field_forbidden(client):
    response = client.post("/api/v1/auth/signup", json={
        "email": "hacker@example.com",
        "password": "ValidPass123",
        "role": "admin"  # This should be forbidden!
    })
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
    fields = [d["field"] for d in data["error"]["details"]]
    assert "body.role" in fields