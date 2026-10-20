from uuid import UUID
from fastapi import APIRouter, Depends, status, Query, Response
from sqlalchemy.orm import Session
from app.db import get_db
from app.deps import get_current_user
from app.models import User, Hub, Document, Chunk
from app.schemas import HubResponse, HubDetail, HubCreate
from app.errors import AppError
from app import repo
from app.idempotency import require_idempotency_key, body_hash, purge_stale, claim_key, complete_key, release_claim, replay_or_conflict
from app.chunking import chunk_text
from app.services.embeddings import embed_texts
from app.services.gemini import hub_insights
router = APIRouter(prefix="/hubs", tags=["hubs"])



@router.post("", response_model=HubResponse, status_code=status.HTTP_201_CREATED)
def create_hub(
    body: HubCreate,
    key: UUID = Depends(require_idempotency_key),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id = current_user.id
    req_hash = body_hash(body.model_dump())
    
    purge_stale(db, user_id)
    if not claim_key(db, user_id, key, req_hash, "/api/v1/hubs"):
        return replay_or_conflict(db, user_id, key, req_hash)

    # Name pre-check
    if db.query(Hub).filter(Hub.owner_id == user_id, Hub.name == body.name).first():
        release_claim(db, user_id, key)
        raise AppError(409, "HUB_NAME_CONFLICT", "You already have a hub with this name.")

    # AI Summary
    summary, questions = hub_insights(body.content) if body.content else (None, [])

    # Create Hub
    new_hub = Hub(owner_id=user_id, name=body.name, description=body.description, ai_summary=summary, suggested_questions=questions)
    db.add(new_hub)
    db.flush()

    doc_count = 0
    chunk_count = 0

    # Inline Document
    if body.content.strip():
        doc_count = 1
        new_doc = Document(
            hub_id=new_hub.id, owner_id=user_id, origin="inline", filename="inline.txt",
            mime_type="text/plain", size_bytes=len(body.content), checksum_sha256="0"*64, status="pending"
        )
        db.add(new_doc)
        db.flush()
        try:
            chunks_data = chunk_text(body.content)
            texts = [c[0] for c in chunks_data]
            embeddings = embed_texts(texts)
            for i, ((text, tokens), emb) in enumerate(zip(chunks_data, embeddings)):
                db.add(Chunk(document_id=new_doc.id, hub_id=new_hub.id, owner_id=user_id, chunk_index=i, text=text, token_count=tokens, embedding=emb))
                chunk_count += 1
            new_doc.status = "ready"
        except Exception:
            new_doc.status = "failed"
            new_doc.error_message = "Embedding failed"

    db.commit()
    db.refresh(new_hub)

    # Build response
    hub_resp = HubResponse.model_validate(new_hub)
    hub_resp.document_count = doc_count
    hub_resp.chunk_count = chunk_count
    payload = hub_resp.model_dump(mode="json")

    complete_key(db, user_id, key, 201, payload)
    return payload

from app.models import User
from app.schemas import HubResponse, HubDetail
from app.errors import AppError
from app import repo

router = APIRouter(prefix="/hubs", tags=["hubs"])

@router.get("", response_model=dict)
def list_hubs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    hubs, total = repo.list_hubs_for_owner(db, current_user.id, limit, offset)
    
    # Convert ORM models to Pydantic models to include counts
    items = []
    for hub in hubs:
        hub_data = HubResponse.model_validate(hub)
        hub_data.document_count = len(hub.documents)
        hub_data.chunk_count = len(hub.chunks)
        items.append(hub_data)
        
    return {"items": items, "total": total, "limit": limit, "offset": offset}

@router.get("/{hub_id}", response_model=HubDetail)
def get_hub(
    hub_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    hub = repo.get_hub_for_owner(db, hub_id, current_user.id)
    if not hub:
        # Cloaked 404
        raise AppError(404, "HUB_NOT_FOUND", "Hub not found.")
    
    hub_data = HubDetail.model_validate(hub)
    hub_data.document_count = len(hub.documents)
    hub_data.chunk_count = len(hub.chunks)
    return hub_data

@router.delete("/{hub_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_hub(
    hub_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    deleted_count = repo.delete_hub_for_owner(db, hub_id, current_user.id)
    if deleted_count == 0:
        raise AppError(404, "HUB_NOT_FOUND", "Hub not found.")
    
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)