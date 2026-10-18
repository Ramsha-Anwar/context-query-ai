from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.db import get_db
from app.models import User
from app.schemas import UserCreate, UserResponse
from app.security import hash_password
from app.errors import AppError

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    # 1. Check if email exists (using lower() for case-insensitivity)
    existing_user = db.query(User).filter(User.email.ilike(user_data.email)).first()
    if existing_user:
        raise AppError(
            status_code=409,
            code="EMAIL_ALREADY_REGISTERED",
            message="An account with this email already exists.",
        )

    # 2. Hash password and create user
    new_user = User(
        email=user_data.email,
        password_hash=hash_password(user_data.password)
    )
    
    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except IntegrityError:
        # Catch race conditions where two requests hit at the exact same time
        db.rollback()
        raise AppError(
            status_code=409,
            code="EMAIL_ALREADY_REGISTERED",
            message="An account with this email already exists.",
        )

    return new_user