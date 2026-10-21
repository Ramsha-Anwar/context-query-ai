import pytest
from uuid import uuid4
from unittest.mock import patch
from app.models import Hub, Document, Chunk

def test_empty_retrieval_returns_ungrounded(client, db_session):
    client.post("/api/v1/auth/signup", json={"email": "rag@test.com", "password": "Password123"})
    token = client.post("/api/v1/auth/login", json={"email": "rag@test.com", "password": "Password123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    hub_res = client.post("/api/v1/hubs", headers={**headers, "X-Idempotency-Key": str(uuid4())}, json={"name": "Empty Hub"})
    hub_id = hub_res.json()["id"]

    # Query without any documents/chunks
    with patch("app.routers.hubs.embed_texts", return_value=[[0.1]*768]), \
         patch("app.routers.hubs.answer_question") as mock_answer:
        
        res = client.post(f"/api/v1/hubs/{hub_id}/query", headers=headers, json={"question": "What is the policy?"})
        
        assert res.status_code == 200
        assert res.json()["grounded"] is False
        assert res.json()["evidence"] is None
        assert res.json()["sources"] == []
        # CRITICAL: Gemini was never called
        mock_answer.assert_not_called()


def test_vector_search_is_scoped_to_owner(client, db_session):
    # Create User A and User B
    client.post("/api/v1/auth/signup", json={"email": "usera@rag.com", "password": "Password123"})
    token_a = client.post("/api/v1/auth/login", json={"email": "usera@rag.com", "password": "Password123"}).json()["access_token"]
    
    client.post("/api/v1/auth/signup", json={"email": "userb@rag.com", "password": "Password123"})
    token_b = client.post("/api/v1/auth/login", json={"email": "userb@rag.com", "password": "Password123"}).json()["access_token"]

    # User A creates a hub and a document (we mock the ingestion for speed)
    hub_a = client.post("/api/v1/hubs", headers={"Authorization": f"Bearer {token_a}", "X-Idempotency-Key": str(uuid4())}, json={"name": "A's Secret Hub"}).json()
    
    # Insert a chunk manually
    from app.models import User, Hub
    user_a = db_session.query(User).filter(User.email == "usera@rag.com").first()
    hub = db_session.query(Hub).filter(Hub.id == hub_a["id"]).first()
    
    doc = Document(id=uuid4(), hub_id=hub.id, owner_id=user_a.id, origin="upload", filename="a.txt", mime_type="text/plain", size_bytes=10, checksum_sha256="0"*64, status="ready")
    db_session.add(doc)
    db_session.commit()
    
    chunk = Chunk(id=uuid4(), document_id=doc.id, hub_id=hub.id, owner_id=user_a.id, chunk_index=0, text="The secret is 42.", token_count=5, embedding=[0.1]*768)
    db_session.add(chunk)
    db_session.commit()

    # User B tries to query User A's hub
    with patch("app.routers.hubs.embed_texts", return_value=[[0.1]*768]):
        res = client.post(f"/api/v1/hubs/{hub.id}/query", headers={"Authorization": f"Bearer {token_b}"}, json={"question": "What is the secret?"})
        assert res.status_code == 404
        assert res.json()["error"]["code"] == "HUB_NOT_FOUND"


def test_expansion_fallback_when_gemini_fails(client, db_session):
    # Setup user and hub
    client.post("/api/v1/auth/signup", json={"email": "fallback@test.com", "password": "Password123"})
    token = client.post("/api/v1/auth/login", json={"email": "fallback@test.com", "password": "Password123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    hub_res = client.post("/api/v1/hubs", headers={**headers, "X-Idempotency-Key": str(uuid4())}, json={"name": "Fallback Hub"})
    hub_id = hub_res.json()["id"]

    # Mock _call to raise an exception. expand_query should catch it and return [].
    with patch("app.services.gemini._call", side_effect=Exception("AI Down")), \
         patch("app.routers.hubs.embed_texts", return_value=[[0.1]*768]), \
         patch("app.routers.hubs.answer_question", return_value={"answer": "Test", "evidence": None, "grounded": False}):
        
        res = client.post(f"/api/v1/hubs/{hub_id}/query", headers=headers, json={"question": "Test question?"})
        # Should not crash, should fallback gracefully
        assert res.status_code == 200


def test_multihop_question_returns_two_sources(client, db_session):
    # Setup user and hub
    client.post("/api/v1/auth/signup", json={"email": "multihop@test.com", "password": "Password123"})
    token = client.post("/api/v1/auth/login", json={"email": "multihop@test.com", "password": "Password123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    hub_res = client.post("/api/v1/hubs", headers={**headers, "X-Idempotency-Key": str(uuid4())}, json={"name": "MultiHop Hub"})
    hub_id = hub_res.json()["id"]

    # Manually insert two chunks
    from app.models import User, Hub, Document, Chunk
    user = db_session.query(User).filter(User.email == "multihop@test.com").first()
    hub = db_session.query(Hub).filter(Hub.id == hub_id).first()
    doc = Document(id=uuid4(), hub_id=hub.id, owner_id=user.id, origin="upload", filename="test.txt", mime_type="text/plain", size_bytes=10, checksum_sha256="0"*64, status="ready")
    db_session.add(doc)
    db_session.commit()
    
    chunk1 = Chunk(id=uuid4(), document_id=doc.id, hub_id=hub.id, owner_id=user.id, chunk_index=0, text="Chunk one", token_count=5, embedding=[0.1]*768)
    chunk2 = Chunk(id=uuid4(), document_id=doc.id, hub_id=hub.id, owner_id=user.id, chunk_index=1, text="Chunk two", token_count=5, embedding=[0.2]*768)
    db_session.add_all([chunk1, chunk2])
    db_session.commit()

    with patch("app.routers.hubs.expand_query", return_value=["alt1", "alt2"]), \
         patch("app.routers.hubs.embed_texts", return_value=[[0.1]*768, [0.1]*768, [0.2]*768]), \
         patch("app.routers.hubs.answer_question", return_value={"answer": "Combined", "evidence": "Chunk", "grounded": True}):
        
        res = client.post(f"/api/v1/hubs/{hub_id}/query", headers=headers, json={"question": "Question spanning two chunks?"})
        assert res.status_code == 200