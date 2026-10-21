import pytest
import time
from uuid import uuid4
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from app.main import app
from app.models import Chunk
from app.chunking import chunk_text as original_chunk_text

def test_concurrent_process_locks(client, db_session):
    client.post("/api/v1/auth/signup", json={"email": "race_doc@test.com", "password": "Password123"})
    token = client.post("/api/v1/auth/login", json={"email": "race_doc@test.com", "password": "Password123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    hub_res = client.post("/api/v1/hubs", headers={**headers, "X-Idempotency-Key": str(uuid4())}, json={"name": "Race Hub"})
    hub_id = hub_res.json()["id"]

    files = {"file": ("test.txt", b"Test text for race condition.", "text/plain")}
    upload_res = client.post(f"/api/v1/hubs/{hub_id}/documents", headers={**headers, "X-Idempotency-Key": str(uuid4())}, files=files)
    doc_id = upload_res.json()["id"]

    client.post(f"/api/v1/hubs/{hub_id}/documents/{doc_id}/process", headers=headers)

    def send_process(_):
        with TestClient(app) as c:
            return c.post(f"/api/v1/hubs/{hub_id}/documents/{doc_id}/process", headers=headers)

    def slow_chunk_text(*args, **kwargs):
        time.sleep(0.5)
        return original_chunk_text(*args, **kwargs)

    with patch("app.routers.documents.chunk_text", side_effect=slow_chunk_text) as mock_chunk:
        with ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(send_process, 1)
            future2 = executor.submit(send_process, 2)
            r1 = future1.result()
            r2 = future2.result()

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert mock_chunk.call_count == 1
    assert db_session.query(Chunk).count() > 0