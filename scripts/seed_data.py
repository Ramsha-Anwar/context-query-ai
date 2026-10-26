import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import User, Hub, Document, Chunk
import bcrypt

def seed():
    db: Session = SessionLocal()
    print("Seeding database with fake data...")

    # 1. Create a user
    password_hash = bcrypt.hashpw(b"Password123", bcrypt.gensalt()).decode()
    user = User(
        id=uuid.uuid4(),
        email=f"seed_{uuid.uuid4().hex[:6]}@example.com",
        password_hash=password_hash,
        role="owner",
        is_active=True
    )
    db.add(user)
    db.commit()

    # 2. Create 10 Hubs
    hubs = []
    for i in range(10):
        hub = Hub(id=uuid.uuid4(), owner_id=user.id, name=f"Seed Hub {i}")
        db.add(hub)
        hubs.append(hub)
    db.commit()

    # 3. Create 5 documents per hub
    docs = []
    for hub in hubs:
        for j in range(5):
            doc = Document(
                id=uuid.uuid4(), hub_id=hub.id, owner_id=user.id, origin="upload",
                filename=f"doc_{j}.txt", mime_type="text/plain", size_bytes=1000,
                checksum_sha256=uuid.uuid4().hex + uuid.uuid4().hex, status="ready"
            )
            db.add(doc)
            docs.append(doc)
    db.commit()

    # 4. Create 2000 chunks per document (10 hubs * 5 docs * 2000 = 100,000 chunks)
    print("Generating 100,000 chunks (this takes a few seconds)...")
    chunks = []
    for i, doc in enumerate(docs):
        for k in range(2000):
            # Random 384-dimensional vector
            embedding = [random.uniform(-1, 1) for _ in range(384)]
            chunk = Chunk(
                id=uuid.uuid4(), document_id=doc.id, hub_id=doc.hub_id, owner_id=user.id,
                chunk_index=k, text=f"Fake chunk text {k} for doc {doc.id}",
                token_count=10, embedding=embedding
            )
            chunks.append(chunk)
        
        # Commit in batches to save memory
        if len(chunks) >= 10000:
            db.bulk_save_objects(chunks)
            db.commit()
            chunks = []
            print(f"Inserted {len(docs) * 2000 if i == len(docs)-1 else (i+1)*2000} chunks...")

    if chunks:
        db.bulk_save_objects(chunks)
        db.commit()

    print("Seeding complete!")
    db.close()

if __name__ == "__main__":
    seed()