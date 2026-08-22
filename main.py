"""Main FastAPI application entry point."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import settings
from src.presentation.api.routes import router as api_router

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    version="0.1.0",
)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "X-Internal-Token"],
    )

app.include_router(api_router)


@app.on_event("startup")
async def startup_event() -> None:
    """Application startup event."""
    logger.info(f"Starting {settings.app_name}")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Application shutdown event."""
    logger.info(f"Shutting down {settings.app_name}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
