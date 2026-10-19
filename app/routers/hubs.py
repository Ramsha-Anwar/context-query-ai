from uuid import UUID
from fastapi import APIRouter, Depends, status, Query, Response
from sqlalchemy.orm import Session
from app.db import get_db
from app.deps import get_current_user
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