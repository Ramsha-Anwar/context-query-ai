import time
from collections import defaultdict, deque
from fastapi import Depends
from uuid import UUID
from app.models import User
from app.deps import get_current_user
from app.errors import AppError

# Dictionary mapping user_id -> deque of timestamps
_hits: dict[UUID, deque] = defaultdict(deque)

def check_query_rate(current_user: User = Depends(get_current_user)) -> None:
    """Sliding window rate limiter: 10 queries per 60 seconds per user."""
    limit = 10
    window = 60
    user_id = current_user.id
    
    now = time.monotonic()
    q = _hits[user_id]
    
    # Remove timestamps older than the window
    while q and now - q[0] > window:
        q.popleft()
        
    if len(q) >= limit:
        raise AppError(
            429, 
            "RATE_LIMITED", 
            f"At most {limit} queries per {window} seconds.",
            headers={"Retry-After": str(window)}
        )
        
    q.append(now)