from uuid import UUID
from sqlalchemy.orm import Session
from app.models import Hub
from app.models import Chunk
from app.config import settings

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

def retrieve_chunks_for_query(db: Session, owner_id: UUID, hub_id: UUID, query_embedding: list[float]):
    # We filter by owner and hub FIRST, then order by cosine distance
    return (
        db.query(Chunk)
        .filter(Chunk.owner_id == owner_id, Chunk.hub_id == hub_id)
        .order_by(Chunk.embedding.cosine_distance(query_embedding))
        .limit(settings.RAG_TOP_K)
        .all()
    )