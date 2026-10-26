import pytest
from uuid import uuid4
from unittest.mock import patch
from app.models import Document, Chunk

def test_upload_and_process_pdf(client, db_session):
    client.post("/api/v1/auth/signup", json={"email": "doc@test.com", "password": "Password123"})
    token = client.post("/api/v1/auth/login", json={"email": "doc@test.com", "password": "Password123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    key = str(uuid4())
    hub_res = client.post("/api/v1/hubs", headers={**headers, "X-Idempotency-Key": key}, json={"name": "PDF Hub"})
    hub_id = hub_res.json()["id"]

    file_content = b"This is a test document. It has multiple sentences to chunk."
    upload_key = str(uuid4())
    files = {"file": ("test.txt", file_content, "text/plain")}
    
    upload_res = client.post(f"/api/v1/hubs/{hub_id}/documents", headers={**headers, "X-Idempotency-Key": upload_key}, files=files)
    assert upload_res.status_code == 202
    doc_id = upload_res.json()["id"]
    assert upload_res.json()["status"] == "pending"

    with patch("app.routers.documents.embed_texts", return_value=[[0.1]*384]):
        res1 = client.post(f"/api/v1/hubs/{hub_id}/documents/{doc_id}/process", headers=headers)
        assert res1.json()["status"] == "chunking"

        res2 = client.post(f"/api/v1/hubs/{hub_id}/documents/{doc_id}/process", headers=headers)
        assert res2.json()["status"] == "embedding"
        
        res3 = client.post(f"/api/v1/hubs/{hub_id}/documents/{doc_id}/process", headers=headers)
        assert res3.json()["status"] == "ready"

    assert db_session.query(Chunk).count() > 0

def test_process_is_idempotent(client, db_session):
    client.post("/api/v1/auth/signup", json={"email": "idem_doc@test.com", "password": "Password123"})
    token = client.post("/api/v1/auth/login", json={"email": "idem_doc@test.com", "password": "Password123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    hub_res = client.post("/api/v1/hubs", headers={**headers, "X-Idempotency-Key": str(uuid4())}, json={"name": "Idem Doc Hub"})
    hub_id = hub_res.json()["id"]

    files = {"file": ("test.txt", b"Test text for idempotency.", "text/plain")}
    upload_res = client.post(f"/api/v1/hubs/{hub_id}/documents", headers={**headers, "X-Idempotency-Key": str(uuid4())}, files=files)
    doc_id = upload_res.json()["id"]

    key1 = str(uuid4())
    
    with patch("app.routers.documents.embed_texts", return_value=[[0.1]*384]):
        res1 = client.post(f"/api/v1/hubs/{hub_id}/documents/{doc_id}/process", headers={**headers, "X-Idempotency-Key": key1})
        assert res1.json()["status"] == "chunking"

        res1_retry = client.post(f"/api/v1/hubs/{hub_id}/documents/{doc_id}/process", headers={**headers, "X-Idempotency-Key": key1})
        assert res1_retry.json()["status"] == "chunking"

        key2 = str(uuid4())
        res2 = client.post(f"/api/v1/hubs/{hub_id}/documents/{doc_id}/process", headers={**headers, "X-Idempotency-Key": key2})
        assert res2.json()["status"] == "embedding"
def test_upload_unsupported_mime_type(client):
    client.post("/api/v1/auth/signup", json={"email": "mime@test.com", "password": "Password123"})
    token = client.post("/api/v1/auth/login", json={"email": "mime@test.com", "password": "Password123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    hub_res = client.post("/api/v1/hubs", headers={**headers, "X-Idempotency-Key": str(uuid4())}, json={"name": "Mime Hub"})
    hub_id = hub_res.json()["id"]

    files = {"file": ("test.png", b"fake image data", "image/png")}
    res = client.post(f"/api/v1/hubs/{hub_id}/documents", headers={**headers, "X-Idempotency-Key": str(uuid4())}, files=files)
    assert res.status_code == 415
    assert res.json()["error"]["code"] == "UNSUPPORTED_MIME_TYPE"

def test_upload_file_too_large(client):
    client.post("/api/v1/auth/signup", json={"email": "large@test.com", "password": "Password123"})
    token = client.post("/api/v1/auth/login", json={"email": "large@test.com", "password": "Password123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    hub_res = client.post("/api/v1/hubs", headers={**headers, "X-Idempotency-Key": str(uuid4())}, json={"name": "Large Hub"})
    hub_id = hub_res.json()["id"]

    # 11MB file
    large_content = b"a" * (11 * 1024 * 1024)
    files = {"file": ("large.txt", large_content, "text/plain")}
    res = client.post(f"/api/v1/hubs/{hub_id}/documents", headers={**headers, "X-Idempotency-Key": str(uuid4())}, files=files)
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "DOCUMENT_TOO_LARGE"

def test_process_document_not_found(client):
    client.post("/api/v1/auth/signup", json={"email": "notfound@test.com", "password": "Password123"})
    token = client.post("/api/v1/auth/login", json={"email": "notfound@test.com", "password": "Password123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    hub_res = client.post("/api/v1/hubs", headers={**headers, "X-Idempotency-Key": str(uuid4())}, json={"name": "NF Hub"})
    hub_id = hub_res.json()["id"]

    random_doc_id = uuid4()
    res = client.post(f"/api/v1/hubs/{hub_id}/documents/{random_doc_id}/process", headers=headers)
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"        
