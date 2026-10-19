from uuid import UUID
from sqlalchemy.orm import Session
from app.models import Hub

def list_hubs_for_owner(db: Session, owner_id: UUID, limit: int, offset: int):
    query = db.query(Hub).filter(Hub.owner_id == owner_id).order_by(Hub.created_at.desc())
    total = query.count()
    hubs = query.offset(offset).limit(limit).all()
    return hubs, total

def get_hub_for_owner(db: Session, hub_id: UUID, owner_id: UUID) -> Hub | None:
    return db.query(Hub).filter(Hub.id == hub_id, Hub.owner_id == owner_id).first()

def delete_hub_for_owner(db: Session, hub_id: UUID, owner_id: UUID) -> int:
    # Returns the number of rows deleted (0 or 1)
    return db.query(Hub).filter(Hub.id == hub_id, Hub.owner_id == owner_id).delete()