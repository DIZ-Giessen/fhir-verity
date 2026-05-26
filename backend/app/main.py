import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.validation_config import ValidationConfig
from app.services.config_defaults import MII_KDS_DEFAULTS
from app.api.v1.endpoints import (
    servers,
    validation,
    websocket,
    config,
    resource_actions,
)

logger = logging.getLogger(__name__)
settings = get_settings()


async def seed_default_configs() -> None:
    """
    Write MII KDS defaults to DB on startup.
    Idempotent: skips resource types that already have a global config.
    """
    async with AsyncSessionLocal() as db:
        try:
            for resource_type, rules in MII_KDS_DEFAULTS.items():
                stmt = select(ValidationConfig).where(
                    ValidationConfig.server_id.is_(None),
                    ValidationConfig.resource_type == resource_type,
                )
                result = await db.execute(stmt)
                existing = result.scalar_one_or_none()

                if not existing:
                    db.add(
                        ValidationConfig(
                            server_id=None,
                            resource_type=resource_type,
                            rules=rules,
                        )
                    )
                    logger.info("Seeded default config for %s", resource_type)
                else:
                    logger.debug(
                        "Default config for %s already exists, skipping", resource_type
                    )

            await db.commit()
            logger.info("Default config seeding complete")

        except Exception as e:
            await db.rollback()
            logger.error("Failed to seed default configs: %s", e)
            raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    logger.info("Starting FHIR Verity API")
    await seed_default_configs()
    yield
    logger.info("Shutting down FHIR Verity API")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.PROJECT_VERSION,
    lifespan=lifespan,
    license_info={
        "name": "MIT License",
    },
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
    """Principal Root"""
    return {
        "message": "Welcome to the FHIR Verity API",
        "version": settings.PROJECT_VERSION,
    }


app.include_router(servers.router, prefix="/api/v1", tags=["servers"])
app.include_router(validation.router, prefix="/api/v1", tags=["validation"])
app.include_router(websocket.router, prefix="/api/v1", tags=["websocket"])
app.include_router(config.router, prefix="/api/config", tags=["config"])
app.include_router(resource_actions.router, tags=["resource-actions"])
