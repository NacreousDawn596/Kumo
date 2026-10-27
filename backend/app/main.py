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
from app.calendar.routes import router as calendar_router  # noqa: E402
from app.calls.routes import router as calls_router  # noqa: E402
from app.databases.routes import router as databases_router  # noqa: E402
from app.collaboration.routes import router as collaboration_router  # noqa: E402
from app.groups.routes import router as groups_router  # noqa: E402
from app.knowledge.routes import router as knowledge_router  # noqa: E402
from app.messages.routes import router as messages_router  # noqa: E402
from app.notifications.routes import router as notifications_router  # noqa: E402
from app.pages.routes import router as pages_router  # noqa: E402
from app.projects.routes import router as projects_router  # noqa: E402
from app.settings.routes import router as settings_router  # noqa: E402
from app.study_sessions.routes import router as study_sessions_router  # noqa: E402
from app.tasks.routes import router as tasks_router  # noqa: E402
from app.users.routes import router as users_router  # noqa: E402
from app.vault.routes import router as vault_router  # noqa: E402
from app.whiteboards.routes import router as whiteboards_router  # noqa: E402

app.include_router(auth_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(pages_router, prefix="/api")
app.include_router(knowledge_router, prefix="/api")
app.include_router(vault_router, prefix="/api")
app.include_router(tasks_router, prefix="/api")
app.include_router(projects_router, prefix="/api")
app.include_router(calendar_router, prefix="/api")
app.include_router(messages_router, prefix="/api")
app.include_router(groups_router, prefix="/api")
app.include_router(notifications_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(study_sessions_router, prefix="/api")
app.include_router(whiteboards_router, prefix="/api")
app.include_router(collaboration_router, prefix="/api")
app.include_router(calls_router, prefix="/api")
app.include_router(databases_router, prefix="/api")

from app.realtime.routes import router as realtime_router  # noqa: E402

app.include_router(realtime_router, prefix="/api")

# Public file sharing (no auth) — under /api so nginx proxies it, but read-only.
from app.vault.public import router as public_router  # noqa: E402

app.include_router(public_router, prefix="/api")
