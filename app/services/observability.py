import time
import json
import logging
from uuid import UUID
from typing import Callable, Any
from app.services.groq_service import AiUnavailable

logger = logging.getLogger("uvicorn.error")

def log_ai_call(operation: str, user_id: UUID | str, hub_id: UUID | str | None, fn: Callable, *args, **kwargs) -> Any:
    """Wraps an AI call, logs the duration and status, and re-raises exceptions."""
    start = time.monotonic()
    status = "success"
    
    try:
        result = fn(*args, **kwargs)
        return result
    except Exception as e:
        status = "error" if not isinstance(e, AiUnavailable) else e.kind
        raise e
    finally:
        duration_ms = int((time.monotonic() - start) * 1000)
        
        log_data = {
            "event": "ai_call",
            "operation": operation,
            "user_id": str(user_id),
            "hub_id": str(hub_id) if hub_id else None,
            "duration_ms": duration_ms,
            "status": status,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        logger.info(json.dumps(log_data))
