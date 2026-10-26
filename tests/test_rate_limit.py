import pytest
from uuid import uuid4
from unittest.mock import patch
from app.rate_limit import _hits

def test_query_rate_limit(client, db_session):
    # Clear the in-memory rate limit dictionary between tests
    _hits.clear()
    
    client.post("/api/v1/auth/signup", json={"email": "ratelimit@test.com", "password": "Password123"})
    token = client.post("/api/v1/auth/login", json={"email": "ratelimit@test.com", "password": "Password123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    hub_res = client.post("/api/v1/hubs", headers={**headers, "X-Idempotency-Key": str(uuid4())}, json={"name": "Rate Limit Hub"})
    hub_id = hub_res.json()["id"]

    # We mock the AI to be fast so we can make 10 rapid requests
    with patch("app.routers.hubs.expand_query", return_value=[]), \
         patch("app.routers.hubs.embed_texts", return_value=[[0.1]*384]), \
         patch("app.routers.hubs.answer_question", return_value={"answer": "Test", "evidence": None, "grounded": False}):
        
        # Make 10 successful queries
        for _ in range(10):
            res = client.post(f"/api/v1/hubs/{hub_id}/query", headers=headers, json={"question": "Test query?"})
            assert res.status_code == 200

        # The 11th query should be rate limited
        res_11 = client.post(f"/api/v1/hubs/{hub_id}/query", headers=headers, json={"question": "Test query?"})
        assert res_11.status_code == 429
        assert res_11.json()["error"]["code"] == "RATE_LIMITED"
        assert "Retry-After" in res_11.headers

    # A different user should not be rate limited (per-user isolation)
    client.post("/api/v1/auth/signup", json={"email": "ratelimit2@test.com", "password": "Password123"})
    token2 = client.post("/api/v1/auth/login", json={"email": "ratelimit2@test.com", "password": "Password123"}).json()["access_token"]
    
    with patch("app.routers.hubs.expand_query", return_value=[]), \
         patch("app.routers.hubs.embed_texts", return_value=[[0.1]*384]), \
         patch("app.routers.hubs.answer_question", return_value={"answer": "Test", "evidence": None, "grounded": False}):
         
        res_other = client.post(f"/api/v1/hubs/{hub_id}/query", headers={"Authorization": f"Bearer {token2}"}, json={"question": "Test query?"})
        assert res_other.status_code == 404 # Because User 2 doesn't own Hub 1
