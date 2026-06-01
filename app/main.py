from fastapi import FastAPI
from pydantic import BaseModel

from app.modules.receipts.api.router import router as receipts_router
from app.modules.study_assets.api.router import router as study_assets_router
from app.modules.videos.api.router import router as videos_router
from app.shared.errors.handlers import register_error_handlers
from app.shared.observability.logging import configure_logging
from app.shared.observability.middleware import RequestLoggingMiddleware
from app.shared.security.middleware import BotGatewayHardeningMiddleware


class HealthResponse(BaseModel):
    status: str


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="Kiroku API",
        version="0.1.0",
    )
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(BotGatewayHardeningMiddleware)
    register_error_handlers(app)

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    async def health() -> HealthResponse:
        return HealthResponse(status="ok")

    app.include_router(videos_router, prefix="/api/v1")
    app.include_router(receipts_router, prefix="/api/v1")
    app.include_router(study_assets_router, prefix="/api/v1")
    return app


app = create_app()
