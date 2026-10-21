import pytest
from uuid import uuid4
from unittest.mock import patch
from app.models import Document, Chunk

def test_upload_and_process_pdf(client, db_session):
    # Setup user and hub
    client.post("/api/v1/auth/signup", json={"email": "doc@test.com", "password": "Password123"})
    token = client.post("/api/v1/auth/login", json={"email": "doc@test.com", "password": "Password123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create a hub
    key = str(uuid4())
    hub_res = client.post("/api/v1/hubs", headers={**headers, "X-Idempotency-Key": key}, json={"name": "PDF Hub"})
    hub_id = hub_res.json()["id"]

    # Upload a fake text file
    file_content = b"This is a test document. It has multiple sentences to chunk."
    upload_key = str(uuid4())
    files = {"file": ("test.txt", file_content, "text/plain")}
    
    upload_res = client.post(f"/api/v1/hubs/{hub_id}/documents", headers={**headers, "X-Idempotency-Key": upload_key}, files=files)
    assert upload_res.status_code == 202
    doc_id = upload_res.json()["id"]
    assert upload_res.json()["status"] == "pending"

    # Process Stage 1 (chunking)
    with patch("app.routers.documents.embed_texts", return_value=[[0.1]*768]):
        res1 = client.post(f"/api/v1/hubs/{hub_id}/documents/{doc_id}/process", headers=headers)
        assert res1.json()["status"] == "chunking"

        # Process Stage 2 (embedding)
        res2 = client.post(f"/api/v1/hubs/{hub_id}/documents/{doc_id}/process", headers=headers)
        assert res2.json()["status"] == "embedding"
        
        # Process Stage 3 (ready)
        res3 = client.post(f"/api/v1/hubs/{hub_id}/documents/{doc_id}/process", headers=headers)
        assert res3.json()["status"] == "ready"

    # Verify chunks exist in DB
    assert db_session.query(Chunk).count() > 0

def test_process_is_idempotent(client, db_session):
    # Setup user and hub
    client.post("/api/v1/auth/signup", json={"email": "idem_doc@test.com", "password": "Password123"})
    token = client.post("/api/v1/auth/login", json={"email": "idem_doc@test.com", "password": "Password123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    hub_res = client.post("/api/v1/hubs", headers={**headers, "X-Idempotency-Key": str(uuid4())}, json={"name": "Idem Doc Hub"})
    hub_id = hub_res.json()["id"]

    files = {"file": ("test.txt", b"Test text for idempotency.", "text/plain")}
    upload_res = client.post(f"/api/v1/hubs/{hub_id}/documents", headers={**headers, "X-Idempotency-Key": str(uuid4())}, files=files)
    doc_id = upload_res.json()["id"]

    key1 = str(uuid4())
    
    with patch("app.routers.documents.embed_texts", return_value=[[0.1]*768]):
        # 1. Advance to chunking
        res1 = client.post(f"/api/v1/hubs/{hub_id}/documents/{doc_id}/process", headers={**headers, "X-Idempotency-Key": key1})
        assert res1.json()["status"] == "chunking"

        # 2. Retry the exact same request with key1
        res1_retry = client.post(f"/api/v1/hubs/{hub_id}/documents/{doc_id}/process", headers={**headers, "X-Idempotency-Key": key1})
        # It should return "chunking", NOT "embedding"!
        assert res1_retry.json()["status"] == "chunking"

        # 3. Advance to embedding with a NEW key
        key2 = str(uuid4())
        res2 = client.post(f"/api/v1/hubs/{hub_id}/documents/{doc_id}/process", headers={**headers, "X-Idempotency-Key": key2})
        assert res2.json()["status"] == "embedding"   