"""Main App"""

import logging
import secrets
from contextlib import asynccontextmanager
import time
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from sqlalchemy import select
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.security import ensure_dev_user, require_role
from app.models.user import User  # noqa: F401 - register table with Base
from app.models.validation_run import ValidationRun, ValidationStatus
from app.api.v1.endpoints import (
    auth,
    config,
    resource_actions,
    servers,
    validation,
    websocket,
)
from app.api.v1.endpoints import users

logger = logging.getLogger(__name__)
settings = get_settings()


async def reconcile_orphaned_runs() -> None:
    """Mark RUNNING runs left over from a prior process as FAILED.

    Validation runs execute as in-process BackgroundTasks: if the backend
    is restarted/killed mid-run, the row is never updated and stays
    RUNNING forever, permanently blocking new runs against that server
    (see the one-running-run-per-server lock in validation.py). Since this
    runs before anything in the fresh process could set RUNNING, every
    such row found here is by definition orphaned. Their checkpoint is
    preserved, so users can resume from where the crawl left off.
    """
    async with AsyncSessionLocal() as db:
        stmt = select(ValidationRun).where(ValidationRun.status == ValidationStatus.RUNNING)
        orphaned = (await db.execute(stmt)).scalars().all()
        if not orphaned:
            return
        for run in orphaned:
            run.status = ValidationStatus.FAILED
            run.error_message = "Interrupted by a backend restart; use resume to continue."
        await db.commit()
        logger.warning(
            "Marked %d orphaned RUNNING run(s) as FAILED on startup: %s",
            len(orphaned),
            [str(r.id) for r in orphaned],
        )


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Default seed App"""
    logger.info("Starting FHIR Verity API")
    await reconcile_orphaned_runs()
    if not settings.AUTH_ENABLED:
        logger.warning(
            "AUTH_ENABLED=false: authentication is off, every request runs as "
            "the built-in admin 'dev'. Use only for development and demos."
        )
        async with AsyncSessionLocal() as db:
            await ensure_dev_user(db)
    yield
    logger.info("Shutting down FHIR Verity API")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.PROJECT_VERSION,
    lifespan=lifespan,
    license_info={
        "name": "AGPL-3.0-or-later",
        "url": "https://www.gnu.org/licenses/agpl-3.0.html",
    },
)

# Keyed by client IP (real IP via uvicorn --proxy-headers behind Caddy, see
# dockerfile). Generous enough for normal UI usage (a page load fires ~10
# parallel GETs, the run detail page polls every 5s) while still bounding
# runaway loops/scripted abuse.
limiter = Limiter(key_func=get_remote_address, default_limits=["300/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


# SessionMiddleware FIRST so CORS wraps it (CORS handles preflight, session
# manages the cookie inside).
app.add_middleware(
    SessionMiddleware,
    # Without auth no session data matters, so a per-process key is enough.
    secret_key=settings.SESSION_SECRET_KEY or secrets.token_urlsafe(32),
    same_site="lax",
    https_only=settings.ENVIRONMENT == "production",
    session_cookie="verity_session",
    max_age=60 * 60 * 24 * 7,  # 7 days
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
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
    dependencies=[Depends(require_role("viewer"))],
)
app.include_router(
    validation.router,
    prefix="/api/v1",
    tags=["validation"],
    dependencies=[Depends(require_role("viewer"))],
)
app.include_router(websocket.router, prefix="/api/v1", tags=["websocket"])
app.include_router(
    config.router,
    prefix="/api/v1",
    tags=["config"],
    dependencies=[Depends(require_role("viewer"))],
)
app.include_router(
    resource_actions.router,
    prefix="/api/v1",
    tags=["resource-actions"],
    dependencies=[Depends(require_role("viewer"))],
)
app.include_router(users.router, prefix="/api/v1", tags=["users"])




@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    logger.info("%s %s: %.3fs", request.method, request.url.path, duration)
    return response