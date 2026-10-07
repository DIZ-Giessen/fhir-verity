"""Session-based authentication and role-based authorization (BFF)."""

import logging
import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.fhir_server import FhirServer

logger = logging.getLogger(__name__)
settings = get_settings()

ROLE_ORDER = {
    UserRole.viewer.value: 0,
    UserRole.editor.value: 1,
    UserRole.admin.value: 2,
}


def _admin_bootstrap_set() -> set[str]:
    raw = settings.INITIAL_ADMIN_USERS or ""
    return {x.strip().lower() for x in raw.split(",") if x.strip()}


# Built-in user every request runs as when AUTH_ENABLED=false.
DEV_USER_ID = uuid.UUID(int=0)
DEV_USER_SUB = "dev-bypass"


def _dev_user() -> User:
    return User(
        id=DEV_USER_ID,
        keycloak_sub=DEV_USER_SUB,
        username="dev",
        email=None,
        full_name="Development User",
        role=UserRole.admin.value,
    )


async def provision_user(claims: dict, db: AsyncSession) -> User:
    """Just-in-time provisioning from Keycloak userinfo / id_token claims."""
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(status_code=400, detail="Claims missing subject")

    username = claims.get("preferred_username")
    email = claims.get("email")
    full_name = claims.get("name")

    user = (
        await db.execute(select(User).where(User.keycloak_sub == sub))
    ).scalar_one_or_none()

    admins = _admin_bootstrap_set()
    is_bootstrap_admin = (username or "").lower() in admins or (
        email or ""
    ).lower() in admins

    if user is None:
        user = User(
            keycloak_sub=sub,
            username=username,
            email=email,
            full_name=full_name,
            role=UserRole.admin.value if is_bootstrap_admin else UserRole.viewer.value,
        )
        db.add(user)
    else:
        user.username = username or user.username
        user.email = email or user.email
        user.full_name = full_name or user.full_name
        if is_bootstrap_admin and ROLE_ORDER.get(user.role, 0) < ROLE_ORDER["admin"]:
            user.role = UserRole.admin.value

    await db.commit()
    await db.refresh(user)
    return user


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    if not settings.AUTH_ENABLED:
        return await ensure_dev_user(db)

    user_id_str = request.session.get("user_id")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        user_id = uuid.UUID(user_id_str)
    except (ValueError, TypeError):
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session",
        )

    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None:
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


def require_role(min_role: str):
    async def _dep(user: User = Depends(get_current_user)) -> User:
        if ROLE_ORDER.get(user.role, -1) < ROLE_ORDER[min_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires '{min_role}' role or higher",
            )
        return user

    return _dep


def require_roles_by_method(read_min: str, write_min: str):
    async def _dep(request: Request, user: User = Depends(get_current_user)) -> User:
        needed = (
            write_min
            if request.method in {"POST", "PUT", "PATCH", "DELETE"}
            else read_min
        )
        if ROLE_ORDER.get(user.role, -1) < ROLE_ORDER[needed]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires '{needed}' role or higher",
            )
        return user

    return _dep


async def load_server_scoped(
    server_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> FhirServer:
    """Load a server enforcing ownership: non-admins may only touch their own.

    Returns 404 (not 403) for foreign servers so their existence is not leaked.
    """
    server = (
        await db.execute(select(FhirServer).where(FhirServer.id == server_id))
    ).scalar_one_or_none()
    if server is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "FHIR server not found")
    if user.role != UserRole.admin.value and server.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "FHIR server not found")
    return server


def server_access(min_role: str = UserRole.viewer.value):
    """Dependency for path endpoints carrying `server_id`: checks role capability
    AND ownership scope in one step, returning the resolved server."""

    async def _dep(
        server_id: uuid.UUID,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> FhirServer:
        if ROLE_ORDER.get(user.role, -1) < ROLE_ORDER[min_role]:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Requires '{min_role}' role or higher",
            )
        return await load_server_scoped(server_id, user, db)

    return _dep


async def ensure_dev_user(db: AsyncSession) -> User:
    """Return the persisted dev-bypass user, creating it if missing.

    Loaded from the session (not built in memory) so preference changes are
    saved and owner_id/actor_id foreign keys resolve. Always admin: in this
    mode there is nobody else to grant roles.
    """
    user = await db.get(User, DEV_USER_ID)
    if user is None:
        user = _dev_user()
        db.add(user)
    elif user.role == UserRole.admin.value:
        return user
    else:
        user.role = UserRole.admin.value
    await db.commit()
    await db.refresh(user)
    return user
