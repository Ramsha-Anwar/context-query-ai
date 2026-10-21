import hashlib
import io
from uuid import UUID
from fastapi import APIRouter, Depends, File, UploadFile, Header, status
from sqlalchemy.orm import Session
from pypdf import PdfReader

from app.db import get_db
from app.deps import get_current_user
from app.models import User, Hub, Document, Chunk
from app.schemas import DocumentResponse
from app.errors import AppError
from app.idempotency import (
    require_idempotency_key, purge_stale, claim_key, 
    complete_key, release_claim, replay_or_conflict
)
from app.services.embeddings import embed_texts
from app.chunking import chunk_text

router = APIRouter(prefix="/hubs/{hub_id}/documents", tags=["documents"])

@router.post("", response_model=DocumentResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    hub_id: UUID,
    file: UploadFile = File(...),
    key: UUID = Depends(require_idempotency_key),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    hub = db.query(Hub).filter(Hub.id == hub_id, Hub.owner_id == current_user.id).first()
    if not hub:
        raise AppError(404, "HUB_NOT_FOUND", "Hub not found.")

    allowed_mimes = ["application/pdf", "text/plain", "text/markdown"]
    if file.content_type not in allowed_mimes:
        raise AppError(415, "UNSUPPORTED_MIME_TYPE", "Only PDF, TXT, and MD are allowed.")
    
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise AppError(413, "DOCUMENT_TOO_LARGE", "File exceeds 10MB.")

    checksum = hashlib.sha256(contents).hexdigest()
    hash_input = f"{hub_id}{file.filename}{len(contents)}{checksum}"
    req_hash = hashlib.sha256(hash_input.encode()).hexdigest()

    purge_stale(db, current_user.id)
    if not claim_key(db, current_user.id, key, req_hash, f"/api/v1/hubs/{hub_id}/documents"):
        return replay_or_conflict(db, current_user.id, key, req_hash)

    existing = db.query(Document).filter(Document.hub_id == hub_id, Document.checksum_sha256 == checksum).first()
    if existing:
        release_claim(db, current_user.id, key)
        raise AppError(409, "DOCUMENT_ALREADY_EXISTS", "This file has already been uploaded to this hub.")

    new_doc = Document(
        hub_id=hub_id, owner_id=current_user.id, origin="upload",
        filename=file.filename, mime_type=file.content_type, size_bytes=len(contents),
        checksum_sha256=checksum, status="pending", file_bytes=contents
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)

    payload = DocumentResponse.model_validate(new_doc).model_dump(mode="json")
    complete_key(db, current_user.id, key, 202, payload)
    return payload

@router.post("/{doc_id}/process", response_model=DocumentResponse)
def process_document(
    hub_id: UUID,
    doc_id: UUID,
    key: UUID | None = Header(default=None, alias="X-Idempotency-Key"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(
        Document.id == doc_id, Document.hub_id == hub_id, Document.owner_id == current_user.id
    ).first()
    
    if not doc:
        raise AppError(404, "DOCUMENT_NOT_FOUND", "Document not found.")
    if doc.status in ("ready", "failed"):
        raise AppError(409, "DOCUMENT_NOT_PROCESSABLE", "Document is already complete or failed.")

    if key and doc.process_claim and str(doc.process_claim) == str(key):
        return DocumentResponse.model_validate(doc)

    if key:
        doc.process_claim = key
        db.commit()

    if doc.status == "pending":
        rows = db.query(Document).filter(
            Document.id == doc.id, Document.status == "pending"
        ).update({"status": "chunking"}, synchronize_session=False)
        db.commit()
        db.refresh(doc)
        return DocumentResponse.model_validate(doc)
        
    elif doc.status == "chunking":
        rows = db.query(Document).filter(
            Document.id == doc.id, Document.status == "chunking"
        ).update({"status": "embedding"}, synchronize_session=False)
        db.commit()
        
        if rows == 0:
            db.refresh(doc)
            return DocumentResponse.model_validate(doc)

        try:
            if doc.mime_type == "application/pdf":
                reader = PdfReader(io.BytesIO(doc.file_bytes))
                text = "\n".join(page.extract_text() for page in reader.pages if page.extract_text())
            else:
                text = doc.file_bytes.decode("utf-8", errors="ignore")
                
            if not text.strip():
                raise ValueError("No text extracted")

            chunks_data = chunk_text(text)
            for i, (chunk_text_str, tokens) in enumerate(chunks_data):
                db.add(Chunk(
                    document_id=doc.id, hub_id=hub_id, owner_id=current_user.id,
                    chunk_index=i, text=chunk_text_str, token_count=tokens,
                    embedding=[0.0] * 768
                ))
                
            doc.file_bytes = None
            db.commit()
        except Exception as e:
            doc.status = "failed"
            doc.error_message = "PDF parsing failed: " + str(e)
            db.commit()
            
    elif doc.status == "embedding":
        rows = db.query(Document).filter(
            Document.id == doc.id, Document.status == "embedding"
        ).update({"status": "ready"}, synchronize_session=False)
        db.commit()
        
        if rows == 0:
            db.refresh(doc)
            return DocumentResponse.model_validate(doc)

        chunks = db.query(Chunk).filter(Chunk.document_id == doc.id).order_by(Chunk.chunk_index).all()
        if not chunks:
            doc.status = "failed"
            doc.error_message = "No chunks found to embed."
            db.commit()
        else:
            try:
                texts = [c.text for c in chunks]
                embeddings = embed_texts(texts)
                
                for chunk, emb in zip(chunks, embeddings):
                    chunk.embedding = emb
                
                db.commit()
            except Exception as e:
                doc.status = "failed"
                doc.error_message = "Embedding failed: " + str(e)
                db.commit()
                
    db.refresh(doc)
    return DocumentResponse.model_validate(doc)