"""Kumo FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine
from app.vault.storage import storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("kumo")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure storage root exists.
    storage.root.mkdir(parents=True, exist_ok=True)
    # Tables are managed by Alembic; in tests we may create them directly.
    if settings.environment == "test":
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Kumo API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": settings.app_name, "environment": settings.environment}


# Routers (added as modules land).
from app.auth.routes import router as auth_router  # noqa: E402
from app.users.routes import router as users_router  # noqa: E402

app.include_router(auth_router, prefix="/api")
app.include_router(users_router, prefix="/api")
