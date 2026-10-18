from uuid import UUID
import jwt
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.config import settings
from app.db import get_db
from app.models import User
from app.errors import AppError

bearer_scheme = HTTPBearer(auto_error=False)

def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db)
) -> User:
    if creds is None or creds.scheme.lower() != "bearer":
        raise AppError(
            401, "AUTH_MISSING", 
            "Authorization header with a Bearer token is required.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        payload = jwt.decode(
            creds.credentials, 
            settings.JWT_SECRET_KEY,
            algorithms=["HS256"], 
            options={"require": ["exp", "sub"]}
        )
    except jwt.ExpiredSignatureError:
        raise AppError(401, "TOKEN_EXPIRED", "Access token has expired. Log in again.")
    except jwt.PyJWTError:
        raise AppError(401, "TOKEN_INVALID", "Access token is malformed or has an invalid signature.")

    try:
        user_id = UUID(payload["sub"])
    except (ValueError, KeyError):
        raise AppError(401, "TOKEN_INVALID", "Token subject is not a valid user id.")

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise AppError(401, "TOKEN_INVALID", "Token does not map to an active user.")

    return user