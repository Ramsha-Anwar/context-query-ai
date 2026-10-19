import pytest
from uuid import uuid4
from unittest.mock import patch
from app.models import Hub, Document, Chunk

def test_create_hub_idempotency(client, db_session):
    client.post("/api/v1/auth/signup", json={"email": "idem@example.com", "password": "Password123"})
    login = client.post("/api/v1/auth/login", json={"email": "idem@example.com", "password": "Password123"})
    token = login.json()["access_token"]
    
    key = str(uuid4())
    headers = {"Authorization": f"Bearer {token}", "X-Idempotency-Key": key}
    body = {"name": "HR Hub", "content": "This is a long text about HR policies and employee benefits."}

    with patch("app.routers.hubs.hub_insights", return_value=("Summary here", ["Q1?", "Q2?"])), \
         patch("app.routers.hubs.embed_texts", return_value=[[0.1]*768] * 3):
        
        # First Request
        r1 = client.post("/api/v1/hubs", headers=headers, json=body)
        if r1.status_code != 201:
            print("\n\nFAILED FIRST REQUEST:", r1.json(), "\n\n")
            
        assert r1.status_code == 201
        assert "Idempotent-Replayed" not in r1.headers

        # Second Request (Replay)
        r2 = client.post("/api/v1/hubs", headers=headers, json=body)
        
        # --- ADD THIS PRINT STATEMENT ---
        if r2.status_code != 201:
            print("\n\nFAILED SECOND REQUEST:", r2.json(), "\n\n")
        # --------------------------------

        assert r2.status_code == 201
        assert r2.headers["Idempotent-Replayed"] == "true"
        assert r1.json() == r2.json()

        # Check DB counts
        assert db_session.query(Hub).count() == 1
        assert db_session.query(Document).count() == 1
        assert db_session.query(Chunk).count() > 0

        # Third Request (Different Body)
        r3 = client.post("/api/v1/hubs", headers=headers, json={"name": "Finance Hub", "content": "Different text"})
        assert r3.status_code == 422
        assert r3.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"

def test_create_hub_missing_key(client):
    client.post("/api/v1/auth/signup", json={"email": "idem2@example.com", "password": "Password123"})
    login = client.post("/api/v1/auth/login", json={"email": "idem2@example.com", "password": "Password123"})
    token = login.json()["access_token"]
    
    r = client.post("/api/v1/hubs", headers={"Authorization": f"Bearer {token}"}, json={"name": "No Key"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "IDEMPOTENCY_KEY_MISSING"

def test_create_hub_missing_key(client):
    client.post("/api/v1/auth/signup", json={"email": "idem2@example.com", "password": "Password123"})
    login = client.post("/api/v1/auth/login", json={"email": "idem2@example.com", "password": "Password123"})
    token = login.json()["access_token"]
    
    r = client.post("/api/v1/hubs", headers={"Authorization": f"Bearer {token}"}, json={"name": "No Key"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "IDEMPOTENCY_KEY_MISSING"