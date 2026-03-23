from fastapi import FastAPI

from app.modules.videos.api.router import router as videos_router
from app.shared.errors.handlers import register_error_handlers
from app.shared.observability.logging import configure_logging
from app.shared.observability.middleware import RequestLoggingMiddleware


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="Kiroku API", version="0.1.0")
    app.add_middleware(RequestLoggingMiddleware)
    register_error_handlers(app)

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(videos_router, prefix="/api/v1")
    return app


app = create_app()
