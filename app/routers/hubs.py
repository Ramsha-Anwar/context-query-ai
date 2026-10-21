from uuid import UUID
from fastapi import APIRouter, Depends, status, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text

from app.db import get_db
from app.deps import get_current_user
from app.models import User, Hub, Document, Chunk
from app.schemas import HubResponse, HubDetail, HubCreate, QueryRequest, QueryResponse, QuerySource
from app.errors import AppError
from app import repo
from app.idempotency import (
    require_idempotency_key, body_hash, purge_stale, 
    claim_key, complete_key, release_claim, replay_or_conflict
)
from app.chunking import chunk_text
from app.services.embeddings import embed_texts
from app.services.gemini import hub_insights, answer_question, expand_query
from app.services.observability import log_ai_call
from app.config import settings

router = APIRouter(prefix="/hubs", tags=["hubs"])

@router.get("", response_model=dict)
def list_hubs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    hubs, total = repo.list_hubs_for_owner(db, current_user.id, limit, offset)
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

    if db.query(Hub).filter(Hub.owner_id == user_id, Hub.name == body.name).first():
        release_claim(db, user_id, key)
        raise AppError(409, "HUB_NAME_CONFLICT", "You already have a hub with this name.")

    if body.content:
        summary, questions = log_ai_call("hub_insights", user_id, None, hub_insights, body.content)
    else:
        summary, questions = None, []

    new_hub = Hub(
        owner_id=user_id, name=body.name, description=body.description, 
        ai_summary=summary, suggested_questions=questions
    )
    db.add(new_hub)
    
    try:
        db.flush() 
        
        doc_count = 0
        chunk_count = 0
        
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
                embeddings = log_ai_call("embed_texts", user_id, new_hub.id, embed_texts, texts)
                
                for i, ((text, tokens), emb) in enumerate(zip(chunks_data, embeddings)):
                    db.add(Chunk(
                        document_id=new_doc.id, hub_id=new_hub.id, owner_id=user_id, 
                        chunk_index=i, text=text, token_count=tokens, embedding=emb
                    ))
                    chunk_count += 1
                new_doc.status = "ready"
            except Exception:
                new_doc.status = "failed"
                new_doc.error_message = "Embedding failed"

        db.commit()
        db.refresh(new_hub)

        hub_resp = HubResponse.model_validate(new_hub)
        hub_resp.document_count = doc_count
        hub_resp.chunk_count = chunk_count
        payload = hub_resp.model_dump(mode="json")

        complete_key(db, user_id, key, 201, payload)
        return payload

    except IntegrityError as e:
        db.rollback()
        release_claim(db, user_id, key)
        if getattr(e.orig.diag, "constraint_name", None) == "uq_hub_name_per_owner":
            raise AppError(409, "HUB_NAME_CONFLICT", "You already have a hub with this name.")
        raise

@router.post("/{hub_id}/query", response_model=QueryResponse)
def query_hub(
    hub_id: UUID,
    req: QueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    hub = repo.get_hub_for_owner(db, hub_id, current_user.id)
    if not hub:
        raise AppError(404, "HUB_NOT_FOUND", "Hub not found.")

    alt_queries = expand_query(req.question)
    all_queries = [req.question] + alt_queries
    embeddings = embed_texts(all_queries)

    chunks = repo.retrieve_chunks_for_queries(db, current_user.id, hub_id, embeddings)
    
    raw_sql = text("""
        SELECT id, text, chunk_index, document_id, 1 - (embedding <=> :q) as similarity
        FROM chunks
        WHERE owner_id = :u AND hub_id = :h
        AND 1 - (embedding <=> :q) >= :threshold
        ORDER BY embedding <=> :q
        LIMIT :k
    """)
    
    results = db.execute(
        raw_sql, 
        {"q": str(embeddings[0]), "u": current_user.id, "h": hub_id, "threshold": settings.RAG_MIN_SIMILARITY, "k": settings.RAG_TOP_K}
    ).fetchall()

    db.rollback()

    if not results:
        return QueryResponse(
            hub_id=hub_id, question=req.question, answer="I couldn't find an answer in this hub.",
            evidence=None, model=settings.GEMINI_MODEL, grounded=False, sources=[], retrieved_chunks=0
        )

    context_texts = [row.text for row in results]
    context = "\n\n---\n\n".join(context_texts)

    ai_result = answer_question(context, req.question)

    sources = []
    if ai_result["evidence"]:
        for row in results:
            if ai_result["evidence"].lower() in row.text.lower():
                doc = db.query(Document).filter(Document.id == row.document_id).first()
                if doc:
                    sources.append(QuerySource(
                        document_id=row.document_id, filename=doc.filename, chunk_index=row.chunk_index
                    ))

    return QueryResponse(
        hub_id=hub_id,
        question=req.question,
        answer=ai_result["answer"],
        evidence=ai_result["evidence"],
        model=settings.GEMINI_MODEL,
        grounded=ai_result["grounded"],
        sources=sources,
        retrieved_chunks=len(results)
    )