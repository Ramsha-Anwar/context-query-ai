from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(
        title="ContextQuery AI",
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
    )

    @app.get("/healthz", tags=["system"])
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()