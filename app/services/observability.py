import time
import json
import logging
from uuid import UUID
from typing import Callable, Any
from app.services.groq_service import AiUnavailable

logger = logging.getLogger("uvicorn.error")

def log_ai_call(operation: str, user_id: UUID | str, hub_id: UUID | str | None, fn: Callable, *args, **kwargs) -> Any:
    """Wraps an AI call, logs the duration/tokens/status, and re-raises exceptions."""
    start = time.monotonic()
    status = "success"
    input_tokens = 0
    output_tokens = 0
    
    try:
        result = fn(*args, **kwargs)
        # If the wrapped function returns (data, in_tok, out_tok), unpack it
        if isinstance(result, tuple) and len(result) == 3 and isinstance(result[1], int) and isinstance(result[2], int):
            data, input_tokens, output_tokens = result
            return data
        return result
    except Exception as e:
        status = getattr(e, "kind", "error")
        raise e
    finally:
        duration_ms = int((time.monotonic() - start) * 1000)
        
        log_data = {
            "event": "ai_call",
            "operation": operation,
            "user_id": str(user_id),
            "hub_id": str(hub_id) if hub_id else None,
            "duration_ms": duration_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "status": status,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        logger.info(json.dumps(log_data))