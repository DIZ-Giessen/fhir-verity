"""Backend-for-Frontend OIDC endpoints.

Flow:
  1) Frontend opens /api/v1/auth/login (full navigation).
  2) We redirect to Keycloak with the state stored in the session middleware.
  3) Keycloak redirects to /api/v1/auth/callback with the code.
  4) We exchange the code (using the confidential client_secret, server-side),
     provision the user, set the session cookie, then redirect back to the SPA.
"""

import logging
from urllib.parse import quote

import httpx
from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import get_current_user, provision_user
from app.models.user import User
from app.schemas.user import UserRead

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()

# Applies to every call the client makes (metadata discovery, code exchange,
# userinfo): without it a network blip to Keycloak hangs until the OS-level
# TCP timeout gives up (~15 min), holding the login request open the whole
# time.
KEYCLOAK_TIMEOUT = httpx.Timeout(connect=10.0, read=15.0, write=10.0, pool=10.0)

oauth = OAuth()
oauth.register(
    name="keycloak",
    client_id=settings.KEYCLOAK_CLIENT_ID,
    client_secret=settings.KEYCLOAK_CLIENT_SECRET,
    server_metadata_url=settings.KEYCLOAK_DISCOVERY_URL,
    client_kwargs={"scope": "openid profile email", "timeout": KEYCLOAK_TIMEOUT},
)


def _frontend_url(path: str = "/") -> str:
    return settings.FRONTEND_BASE_URL.rstrip("/") + path


@router.get("/auth/login")
async def login(request: Request):
    """Starts the authentication process by redirecting to Keycloak."""
    redirect_uri = f"{settings.BACKEND_BASE_URL.rstrip('/')}/api/v1/auth/callback"
    try:
        return await oauth.keycloak.authorize_redirect(request, redirect_uri)
    except httpx.HTTPError as exc:
        logger.error("Keycloak unreachable during login redirect: %s", exc)
        return RedirectResponse(_frontend_url("/login?error=idp_unreachable"))


@router.get("/auth/callback")
async def callback(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Callback endpoint for Keycloak OAuth2. Exchanges the authorization code for tokens,
    fetches user info from the IdP, provisions the user in the local DB, and sets a session.
    """
    try:
        token = await oauth.keycloak.authorize_access_token(request)
    except OAuthError as exc:
        message = exc.description or exc.error or "oauth_error"
        logger.warning("OIDC code exchange failed: %s", message)
        return RedirectResponse(_frontend_url(f"/login?error={quote(str(message))}"))
    except httpx.HTTPError as exc:
        logger.error("Keycloak unreachable during code exchange: %s", exc)
        return RedirectResponse(_frontend_url("/login?error=idp_unreachable"))

    userinfo = token.get("userinfo")
    if not userinfo:
        try:
            userinfo = await oauth.keycloak.userinfo(token=token)
        except Exception as exc:
            logger.error("Failed to fetch userinfo: %s", exc)
            return RedirectResponse(_frontend_url("/login?error=userinfo_failed"))

    user = await provision_user(dict(userinfo), db)
    request.session["user_id"] = str(user.id)
    return RedirectResponse(_frontend_url("/"))


@router.post("/auth/logout")
async def logout(request: Request):
    """Logs out the current user by clearing the session."""
    request.session.clear()
    return {"status": "ok"}


@router.get("/auth/me", response_model=UserRead)
async def me(user: User = Depends(get_current_user)):
    """Get the current authenticated user's profile."""
    return UserRead.model_validate(user)
