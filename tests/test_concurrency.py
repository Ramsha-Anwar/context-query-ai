import pytest
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from app.main import app
from app.models import Hub
from unittest.mock import patch

def test_concurrent_same_name_different_keys(client, db_session):
    # Setup User
    client.post("/api/v1/auth/signup", json={"email": "race@example.com", "password": "Password123"})
    login = client.post("/api/v1/auth/login", json={"email": "race@example.com", "password": "Password123"})
    token = login.json()["access_token"]
    
    body = {"name": "Race Hub", "content": "Test text"}
    
    # Worker function for the threads
    def send_request(key):
        # Each thread gets its own client to avoid session clashes
        with TestClient(app) as c:
            headers = {"Authorization": f"Bearer {token}", "X-Idempotency-Key": key}
            return c.post("/api/v1/hubs", headers=headers, json=body)

    key1 = str(uuid4())
    key2 = str(uuid4())

    with patch("app.routers.hubs.hub_insights", return_value=("Summary", [])), \
         patch("app.routers.hubs.embed_texts", return_value=[[0.1]*768]):
        
        # Fire two requests at the exact same time
        with ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(send_request, key1)
            future2 = executor.submit(send_request, key2)
            
            r1 = future1.result()
            r2 = future2.result()

    statuses = [r1.status_code, r2.status_code]
    
    # Assert exactly one succeeded and one failed with 409
    assert 201 in statuses
    assert 409 in statuses
    
    # Verify the 409 was for Name Conflict
    failed_response = r1 if r1.status_code == 409 else r2
    assert failed_response.json()["error"]["code"] == "HUB_NAME_CONFLICT"

    # Verify only ONE hub was created in the database
    assert db_session.query(Hub).count() == 1