import uuid
import logging
from fastapi import FastAPI, Request, Depends
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.errors import AppError, error_response
from app.routers import auth, hubs, documents
from app.deps import get_current_user
from app.models import User
from app.services.groq_service import AiUnavailable
logger = logging.getLogger("uvicorn.error")

def create_app() -> FastAPI:
    app = FastAPI(
        title="ContextQuery AI",
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
    )

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(hubs.router, prefix="/api/v1")
    app.include_router(documents.router, prefix="/api/v1")

    @app.middleware("http")
    async def catch_unhandled(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception:
            logger.exception("unhandled error", extra={"request_id": getattr(request.state, "request_id", "unknown")})
            return error_response(request, 500, "INTERNAL_ERROR", "Unexpected server error.")

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request.state.request_id = str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return error_response(request, exc.status_code, exc.code, exc.message, exc.details, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        details = []
        for error in exc.errors():
            loc = error.get("loc", [])
            field = ".".join(str(x) for x in loc) if loc else "unknown"
            details.append({
                "field": field,
                "reason": error.get("type", "invalid"),
                "message": error.get("msg", "Invalid value")
            })
        return error_response(request, 422, "VALIDATION_ERROR", "Request validation failed.", details=details)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        if exc.status_code == 404:
            return error_response(request, 404, "ROUTE_NOT_FOUND", "The requested route does not exist.")
        if exc.status_code == 405:
            return error_response(request, 405, "METHOD_NOT_ALLOWED", "Method not allowed for this route.")
        return error_response(request, exc.status_code, "HTTP_ERROR", str(exc.detail))

    AI_ERRORS = {
        "rate_limited": (429, "AI_RATE_LIMITED", "The AI provider's free quota is used up. Try again later."),
        "timeout": (504, "AI_TIMEOUT", "The AI provider took too long to answer."),
        "provider": (502, "AI_PROVIDER_ERROR", "The AI provider returned an error."),
    }

    @app.exception_handler(AiUnavailable)
    async def ai_unavailable_handler(request: Request, exc: AiUnavailable):
        status, code, message = AI_ERRORS[exc.kind]
        headers = {"Retry-After": "30"} if exc.kind == "rate_limited" else None
        return error_response(request, status, code, message, headers=headers)

    @app.get("/healthz", tags=["system"])
    def healthz() -> dict[str, str]:
        return {"status": "ok"}
        
    @app.get("/api/v1/protected", tags=["system"])
    def protected_route(current_user: User = Depends(get_current_user)):
        return {"message": "You are authenticated!", "user_id": str(current_user.id)}

    return app

app = create_app()