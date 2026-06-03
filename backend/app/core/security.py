"""Session-based authentication and role-based authorization (BFF)."""

import logging
import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User, UserRole

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


def _dev_user() -> User:
    return User(
        id=uuid.UUID(int=0),
        keycloak_sub="dev-bypass",
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
        return _dev_user()

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
