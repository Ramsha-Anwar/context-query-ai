import pytest
from uuid import uuid4
from app.models import Hub

def create_test_hub(db_session, owner_id, name="Test Hub"):
    hub = Hub(owner_id=owner_id, name=name)
    db_session.add(hub)
    db_session.commit()
    return hub

def test_user_b_cannot_read_user_a_hub(client, db_session):
    # 1. Create two users
    client.post("/api/v1/auth/signup", json={"email": "usera@example.com", "password": "Pass1234"})
    client.post("/api/v1/auth/signup", json={"email": "userb@example.com", "password": "Pass1234"})
    
    token_a = client.post("/api/v1/auth/login", json={"email": "usera@example.com", "password": "Pass1234"}).json()["access_token"]
    token_b = client.post("/api/v1/auth/login", json={"email": "userb@example.com", "password": "Pass1234"}).json()["access_token"]
    
    from app.models import User
    user_a = db_session.query(User).filter(User.email == "usera@example.com").first()
    user_b = db_session.query(User).filter(User.email == "userb@example.com").first()

    # 2. Create a hub for User A
    hub_a = create_test_hub(db_session, user_a.id, "A's Secret Hub")

    # 3. User A can read it
    r_a = client.get(f"/api/v1/hubs/{hub_a.id}", headers={"Authorization": f"Bearer {token_a}"})
    assert r_a.status_code == 200
    
    # 4. User B CANNOT read it (404 Cloaking)
    r_b = client.get(f"/api/v1/hubs/{hub_a.id}", headers={"Authorization": f"Bearer {token_b}"})
    assert r_b.status_code == 404
    assert r_b.json()["error"]["code"] == "HUB_NOT_FOUND"

    # 5. User B cannot list it
    r_list_b = client.get("/api/v1/hubs", headers={"Authorization": f"Bearer {token_b}"})
    assert r_list_b.json()["total"] == 0

    # 6. User B cannot delete it
    r_del_b = client.delete(f"/api/v1/hubs/{hub_a.id}", headers={"Authorization": f"Bearer {token_b}"})
    assert r_del_b.status_code == 404
    
    # 7. User A can delete it
    r_del_a = client.delete(f"/api/v1/hubs/{hub_a.id}", headers={"Authorization": f"Bearer {token_a}"})
    assert r_del_a.status_code == 204