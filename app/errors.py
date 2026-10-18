from typing import Any
from fastapi import Request
from fastapi.responses import JSONResponse

class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: list[dict] | None = None, headers: dict | None = None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or []
        self.headers = headers

def error_response(request: Request, status_code: int, code: str, message: str, details: list[dict] | None = None, headers: dict | None = None) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    
    envelope = {
        "error": {
            "code": code,
            "message": message,
            "status": status_code,
            "request_id": request_id,
            "details": details or []
        }
    }
    
    return JSONResponse(
        status_code=status_code,
        content=envelope,
        headers=headers
    )