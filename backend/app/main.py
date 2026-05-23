from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes_cameras import router as cameras_router
from app.api.routes_detection import router as detection_router
from app.api.routes_events import router as events_router
from app.api.routes_health import router as health_router
from app.api.routes_telegram import router as telegram_router
from app.config import settings
from app.db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.include_router(health_router)
    app.include_router(cameras_router)
    app.include_router(detection_router)
    app.include_router(events_router)
    app.include_router(telegram_router)
    return app


app = create_app()
