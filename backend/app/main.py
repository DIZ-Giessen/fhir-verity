"""Main App"""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.security import require_role, require_roles_by_method
from app.models.user import User  # noqa: F401 - register table with Base
from app.models.validation_config import ValidationConfig
from app.services.config_defaults import MII_KDS_DEFAULTS
from app.api.v1.endpoints import (
    auth,
    config,
    resource_actions,
    servers,
    validation,
    websocket,
)

logger = logging.getLogger(__name__)
settings = get_settings()


async def seed_default_configs() -> None:
    """Write MII KDS defaults to DB on startup. Idempotent."""
    async with AsyncSessionLocal() as db:
        try:
            for resource_type, rules in MII_KDS_DEFAULTS.items():
                stmt = select(ValidationConfig).where(
                    ValidationConfig.server_id.is_(None),
                    ValidationConfig.resource_type == resource_type,
                )
                existing = (await db.execute(stmt)).scalar_one_or_none()
                if not existing:
                    db.add(
                        ValidationConfig(
                            server_id=None,
                            resource_type=resource_type,
                            rules=rules,
                        )
                    )
            await db.commit()
            logger.info("Default config seeding complete")
        except Exception as e:
            await db.rollback()
            logger.error("Failed to seed default configs: %s", e)
            raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting FHIR Verity API")
    await seed_default_configs()
    yield
    logger.info("Shutting down FHIR Verity API")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.PROJECT_VERSION,
    lifespan=lifespan,
    license_info={"name": "MIT License"},
)

# SessionMiddleware FIRST so CORS wraps it (CORS handles preflight, session
# manages the cookie inside).
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET_KEY,
    same_site="lax",
    https_only=settings.ENVIRONMENT == "production",
    session_cookie="verity_session",
    max_age=60 * 60 * 24 * 7,  # 7 days
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["health"])
async def root():
    """Default public Root"""
    return {
        "message": "Welcome to the FHIR Verity API",
        "version": settings.PROJECT_VERSION,
    }


# /auth is public; /auth/me is gated inside the endpoint via Depends(get_current_user).
app.include_router(auth.router, prefix="/api/v1", tags=["auth"])

app.include_router(
    servers.router,
    prefix="/api/v1",
    tags=["servers"],
    dependencies=[Depends(require_roles_by_method("viewer", "editor"))],
)
app.include_router(
    validation.router,
    prefix="/api/v1",
    tags=["validation"],
    dependencies=[Depends(require_roles_by_method("viewer", "editor"))],
)
app.include_router(websocket.router, prefix="/api/v1", tags=["websocket"])
app.include_router(
    config.router,
    prefix="/api/v1",
    tags=["config"],
    dependencies=[Depends(require_role("editor"))],
)
app.include_router(
    resource_actions.router,
    tags=["resource-actions"],
    dependencies=[Depends(require_role("admin"))],
)
