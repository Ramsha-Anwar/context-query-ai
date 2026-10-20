import hashlib
import json
from uuid import UUID
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from fastapi import Header, Response
from app.models import IdempotencyKey
from app.errors import AppError

def require_idempotency_key(x_idempotency_key: str | None = Header(default=None)) -> UUID:
    if x_idempotency_key is None:
        raise AppError(400, "IDEMPOTENCY_KEY_MISSING", "Header X-Idempotency-Key is required.")
    try:
        key = UUID(x_idempotency_key)
        if key.version != 4:
            raise ValueError
        return key
    except ValueError:
        raise AppError(422, "IDEMPOTENCY_KEY_INVALID", "X-Idempotency-Key must be a UUIDv4.")

def body_hash(data: dict) -> str:
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()

def purge_stale(db: Session, user_id: UUID):
    now = datetime.now(timezone.utc)
    # Delete expired keys OR in_progress keys older than 60 seconds
    db.query(IdempotencyKey).filter(
        IdempotencyKey.user_id == user_id,
        (IdempotencyKey.expires_at < now) | 
        ((IdempotencyKey.status == "in_progress") & (IdempotencyKey.created_at < now - timedelta(seconds=60)))
    ).delete()
    db.commit()

def claim_key(db: Session, user_id: UUID, key: UUID, req_hash: str, path: str) -> bool:
    stmt = insert(IdempotencyKey).values(
        user_id=user_id, key=key, request_method="POST", request_path=path,
        request_hash=req_hash, status="in_progress",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
    ).on_conflict_do_nothing().returning(IdempotencyKey.key)
    
    result = db.execute(stmt)
    db.commit()
    # fetchone() returns None if the insert was skipped (conflict)
    return result.fetchone() is not None

def complete_key(db: Session, user_id: UUID, key: UUID, status: int, body: dict):
    row = db.query(IdempotencyKey).filter_by(user_id=user_id, key=key).first()
    if row:
        row.status = "completed"
        row.response_status = status
        row.response_body = body
        db.commit()

def release_claim(db: Session, user_id: UUID, key: UUID):
    db.query(IdempotencyKey).filter_by(user_id=user_id, key=key).delete()
    db.commit()

def replay_or_conflict(db: Session, user_id: UUID, key: UUID, req_hash: str):
    row = db.query(IdempotencyKey).filter_by(user_id=user_id, key=key).first()
    if not row:
        raise AppError(500, "INTERNAL_ERROR", "Idempotency key vanished.")
    
    if row.request_hash != req_hash:
        raise AppError(422, "IDEMPOTENCY_KEY_REUSED", "This idempotency key was used with a different payload.")
    
    if row.status == "in_progress":
        raise AppError(409, "IDEMPOTENCY_REQUEST_IN_PROGRESS", "Original request still processing.", headers={"Retry-After": "2"})
    
    return Response(
        content=json.dumps(row.response_body),
        status_code=row.response_status,
        media_type="application/json",
        headers={"Idempotent-Replayed": "true"}
    )