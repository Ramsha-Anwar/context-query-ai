from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.db import get_db
from app.models import User
from app.schemas import UserCreate, UserResponse, UserLogin, TokenResponse, ChangePasswordRequest
from app.security import hash_password, verify_password, create_access_token
from app.errors import AppError
from app.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email.ilike(user_data.email)).first()
    if existing_user:
        raise AppError(
            status_code=409,
            code="EMAIL_ALREADY_REGISTERED",
            message="An account with this email already exists.",
        )

    new_user = User(
        email=user_data.email,
        password_hash=hash_password(user_data.password)
    )
    
    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except IntegrityError:
        db.rollback()
        raise AppError(
            status_code=409,
            code="EMAIL_ALREADY_REGISTERED",
            message="An account with this email already exists.",
        )

    return new_user

@router.post("/login", response_model=TokenResponse)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email.ilike(credentials.email)).first()
    
    if not verify_password(credentials.password, user.password_hash if user else None):
        raise AppError(401, "INVALID_CREDENTIALS", "Incorrect email or password.")
        
    if not user.is_active:
        raise AppError(401, "INVALID_CREDENTIALS", "Incorrect email or password.")

    token = create_access_token(user.id, user.role)
    return {"access_token": token, "token_type": "bearer", "expires_in": 3600}

@router.put("/change-password", status_code=status.HTTP_200_OK)
def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not verify_password(data.current_password, current_user.password_hash):
        raise AppError(
            401,
            "INVALID_CREDENTIALS",
            "The current password provided is incorrect."
        )
    
    current_user.password_hash = hash_password(data.new_password)
    db.commit()
    
    return {"message": "Password updated successfully."}