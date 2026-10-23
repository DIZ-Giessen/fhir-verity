"""Session-based authentication and role-based authorization (BFF)."""

import logging
import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import exists, or_, select
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.fhir_server import FhirServer
from app.models.server_member import ServerMember

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


async def _admin_exists(db: AsyncSession) -> bool:
    stmt = select(User.id).where(
        User.role == UserRole.admin.value,
        User.keycloak_sub != DEV_USER_SUB,
    )
    return (await db.execute(stmt.limit(1))).first() is not None


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

    # E-mail addresses only count when Keycloak has verified them, otherwise
    # anyone who can set their own e-mail could claim a listed address.
    admins = _admin_bootstrap_set()
    is_bootstrap_admin = (username or "").lower() in admins or (
        claims.get("email_verified") is True and (email or "").lower() in admins
    )

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
        # Existing users are only promoted while there is no admin at all, so
        # a listed admin can still be demoted later.
        if (
            is_bootstrap_admin
            and user.role != UserRole.admin.value
            and not await _admin_exists(db)
        ):
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


def has_role(user: User, min_role: str) -> bool:
    return ROLE_ORDER.get(user.role, -1) >= ROLE_ORDER[min_role]


def visible_servers_clause(user: User) -> ColumnElement | None:
    """
    SQL condition for the servers a user may see: their own and those shared
    with them. None for admins, who see every server.
    """
    if user.role == UserRole.admin.value:
        return None
    return or_(
        FhirServer.owner_id == user.id,
        exists().where(
            ServerMember.server_id == FhirServer.id,
            ServerMember.user_id == user.id,
        ),
    )


def can_manage_server(server: FhirServer, user: User) -> bool:
    """Edit, authentication, sharing and delete: admins and editor owners."""
    if user.role == UserRole.admin.value:
        return True
    return server.owner_id == user.id and has_role(user, UserRole.editor.value)


async def load_server_scoped(
    server_id: uuid.UUID,
    user: User,
    db: AsyncSession,
    *,
    manage: bool = False,
) -> FhirServer:
    """
    Load a server the user may see. Returns 404 (not 403) for servers outside
    their scope so their existence is not leaked. With manage=True the user
    must also be allowed to manage it (403 otherwise).
    """
    stmt = select(FhirServer).where(FhirServer.id == server_id)
    clause = visible_servers_clause(user)
    if clause is not None:
        stmt = stmt.where(clause)
    server = (await db.execute(stmt)).scalar_one_or_none()
    if server is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "FHIR server not found")
    if manage and not can_manage_server(server, user):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only the owner of this server or an admin can do this",
        )
    return server


def server_access(min_role: str = UserRole.viewer.value, *, manage: bool = False):
    """Dependency for path endpoints carrying `server_id`: checks role capability
    AND server scope in one step, returning the resolved server."""

    async def _dep(
        server_id: uuid.UUID,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> FhirServer:
        if not has_role(user, min_role):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Requires '{min_role}' role or higher",
            )
        return await load_server_scoped(server_id, user, db, manage=manage)

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
