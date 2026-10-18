import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from uuid import UUID
from app.config import settings

# A dummy hash used to prevent timing attacks when an email doesn't exist
_DUMMY_HASH = bcrypt.hashpw(b"not-a-real-password", bcrypt.gensalt()).decode()

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, stored_hash: str | None) -> bool:
    # Always runs one bcrypt comparison, even if stored_hash is None
    ok = bcrypt.checkpw(plain.encode(), (stored_hash or _DUMMY_HASH).encode())
    return ok and stored_hash is not None

def create_access_token(user_id: UUID, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=60),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")