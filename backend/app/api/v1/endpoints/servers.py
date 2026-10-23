"""
API endpoints for managing FHIR Servers.
"""

import asyncio
from time import monotonic
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    DEV_USER_SUB,
    can_manage_server,
    get_current_user,
    has_role,
    require_role,
    server_access,
    visible_servers_clause,
)
from app.models.audit_log import AuditAction
from app.models.fhir_server import FhirServer
from app.models.server_member import ServerMember
from app.models.user import User, UserRole
from app.models.validation_run import ValidationRun, ValidationStatus
from app.schemas.server import (
    FhirServerCreate,
    FhirServerRead,
    FhirServerUpdate,
    ResourceCount,
    ServerAuthRead,
    ServerAuthUpdate,
    ServerMemberCreate,
    ServerMemberRead,
    ServerMetadata,
)
from app.services.audit import server_audit_entry
from app.services.rules import RESOURCE_TYPES
from app.services.fhir_auth import build_httpx_auth, normalize_auth_config
from app.services.url_policy import check_outbound_url, same_origin

router = APIRouter()

manage_access = server_access(UserRole.editor.value, manage=True)


def _check_url(url: str) -> None:
    try:
        check_outbound_url(url)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


def _to_read(server: FhirServer, user: User) -> FhirServerRead:
    cfg = normalize_auth_config(server.auth_config)
    return FhirServerRead(
        id=server.id,
        name=server.name,
        base_url=server.base_url,
        project_id=server.project_id,
        is_active=server.is_active,
        write_fhir_reports=server.write_fhir_reports,
        has_auth_config=cfg["type"] != "none",
        auth_type=cfg["type"],
        owner_id=server.owner_id,
        can_write=has_role(user, UserRole.editor.value),
        can_manage=can_manage_server(server, user),
        created_at=server.created_at,
        updated_at=server.updated_at,
    )


@router.post(
    "/servers", response_model=FhirServerRead, status_code=status.HTTP_201_CREATED
)
async def create_fhir_server(
    server_in: FhirServerCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.editor.value)),
):
    """Create a new FHIR server. The creating user becomes the owner."""
    base_url_str = str(server_in.base_url)
    _check_url(base_url_str)

    existing = (
        await db.execute(select(FhirServer).where(FhirServer.base_url == base_url_str))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="FHIR Server with this base URL already exists",
        )

    new_server = FhirServer(
        name=server_in.name,
        base_url=base_url_str,
        project_id=server_in.project_id,
        is_active=server_in.is_active,
        owner_id=user.id,
    )
    db.add(new_server)
    await db.commit()
    await db.refresh(new_server)
    return _to_read(new_server, user)


@router.get("/servers", response_model=list[FhirServerRead])
async def list_fhir_servers(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100,
):
    """List FHIR servers. Admins see all, others their own and shared ones."""
    stmt = select(FhirServer).order_by(FhirServer.name)
    clause = visible_servers_clause(user)
    if clause is not None:
        stmt = stmt.where(clause)
    stmt = stmt.offset(skip).limit(min(limit, 500))
    result = await db.execute(stmt)
    return [_to_read(s, user) for s in result.scalars().all()]


@router.patch(
    "/servers/{server_id}",
    response_model=FhirServerRead,
    summary="Update FHIR server",
)
async def update_fhir_server(
    payload: FhirServerUpdate,
    server: FhirServer = Depends(manage_access),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FhirServerRead:
    """
    Update a FHIR server. When the base URL moves to another host, the stored
    credentials are dropped so they are never sent to a host they were not
    entered for.
    """
    updates = payload.model_dump(exclude_unset=True)
    if updates.get("base_url") is not None:
        updates["base_url"] = str(updates["base_url"])
        _check_url(updates["base_url"])
        old_url = server.base_url
        old_auth = normalize_auth_config(server.auth_config)["type"]
        if old_auth != "none" and not same_origin(old_url, updates["base_url"]):
            server.auth_config = None
            db.add(
                server_audit_entry(
                    AuditAction.SERVER_AUTH_CHANGE,
                    user,
                    server,
                    payload={
                        "type_before": old_auth,
                        "type_after": "none",
                        "reason": "base URL moved to another host",
                        "base_url_before": old_url,
                        "base_url_after": updates["base_url"],
                    },
                )
            )

    for key, value in updates.items():
        setattr(server, key, value)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A server with this base_url already exists",
        ) from exc

    await db.refresh(server)
    return _to_read(server, user)


@router.delete(
    "/servers/{server_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete FHIR server",
)
async def delete_fhir_server(
    server: FhirServer = Depends(manage_access),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a FHIR server together with everything Verity stored for it:
    validation runs, invalid resources (and their issues), server-specific
    configs and shares. All of it cascades in the database. Audit log entries
    are kept (server_id is set to NULL) and a SERVER_DELETE entry is added.
    The FHIR server itself is not touched.

    Refused with 409 while a run is in progress, since the background task
    would keep writing rows for a server that no longer exists.
    """
    running = (
        await db.execute(
            select(ValidationRun.id).where(
                ValidationRun.server_id == server.id,
                ValidationRun.status == ValidationStatus.RUNNING,
            )
        )
    ).scalar_one_or_none()
    if running is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A validation run is in progress for this server. "
            "Cancel it first, then delete the server.",
        )

    snapshot = {
        "name": server.name,
        "base_url": server.base_url,
        "project_id": server.project_id,
        "is_active": server.is_active,
        "write_fhir_reports": server.write_fhir_reports,
        "owner_id": str(server.owner_id) if server.owner_id else None,
    }
    entry = server_audit_entry(
        AuditAction.SERVER_DELETE,
        user,
        server,
        before=snapshot,
        keep_server_link=False,
    )
    await db.delete(server)
    db.add(entry)
    await db.commit()


# ---------------------------------------------------------------------------
# Authentication against the FHIR server
# ---------------------------------------------------------------------------


def _auth_read(cfg: dict) -> ServerAuthRead:
    return ServerAuthRead(
        type=cfg["type"],
        username=cfg.get("username"),
        client_id=cfg.get("client_id"),
        token_url=cfg.get("token_url"),
        scope=cfg.get("scope"),
    )


@router.get("/servers/{server_id}/auth", response_model=ServerAuthRead)
async def get_server_auth(server: FhirServer = Depends(manage_access)):
    """Return the non-secret parts of a server's auth config."""
    return _auth_read(normalize_auth_config(server.auth_config))


@router.patch("/servers/{server_id}/auth", response_model=ServerAuthRead)
async def update_server_auth(
    payload: ServerAuthUpdate,
    server: FhirServer = Depends(manage_access),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Replace a server's auth. Omitted secrets keep their existing value."""
    existing = normalize_auth_config(server.auth_config)

    if payload.type == "none":
        new_cfg: dict = {"type": "none"}

    elif payload.type == "basic":
        username = (
            payload.username
            if payload.username is not None
            else existing.get("username")
        )
        password = (
            payload.password
            if payload.password is not None
            else existing.get("password")
        )
        if not username or not password:
            raise HTTPException(400, "basic auth requires username and password")
        new_cfg = {"type": "basic", "username": username, "password": password}

    else:  # oauth2_client_credentials
        token_url = (
            payload.token_url
            if payload.token_url is not None
            else existing.get("token_url")
        )
        client_id = (
            payload.client_id
            if payload.client_id is not None
            else existing.get("client_id")
        )
        client_secret = (
            payload.client_secret
            if payload.client_secret is not None
            else existing.get("client_secret")
        )
        scope = payload.scope if payload.scope is not None else existing.get("scope")
        if not token_url or not client_id or not client_secret:
            raise HTTPException(
                400, "oauth2 requires token_url, client_id and client_secret"
            )
        _check_url(token_url)
        new_cfg = {
            "type": "oauth2_client_credentials",
            "token_url": token_url,
            "client_id": client_id,
            "client_secret": client_secret,
        }
        if scope:
            new_cfg["scope"] = scope

    # Names of the changed fields only, never their values
    changed = sorted(
        key
        for key in set(existing) | set(new_cfg)
        if existing.get(key) != new_cfg.get(key)
    )
    server.auth_config = new_cfg
    if changed:
        db.add(
            server_audit_entry(
                AuditAction.SERVER_AUTH_CHANGE,
                user,
                server,
                payload={
                    "type_before": existing["type"],
                    "type_after": new_cfg["type"],
                    "changed_fields": changed,
                },
            )
        )
    await db.commit()
    await db.refresh(server)
    return _auth_read(normalize_auth_config(server.auth_config))


# ---------------------------------------------------------------------------
# Sharing
# ---------------------------------------------------------------------------


@router.get("/servers/{server_id}/members", response_model=list[ServerMemberRead])
async def list_server_members(
    server: FhirServer = Depends(manage_access),
    db: AsyncSession = Depends(get_db),
):
    """Users the server is shared with (besides its owner)."""
    rows = (
        await db.execute(
            select(ServerMember, User)
            .join(User, User.id == ServerMember.user_id)
            .where(ServerMember.server_id == server.id)
            .order_by(User.username)
        )
    ).all()
    return [
        ServerMemberRead(
            user_id=u.id,
            username=u.username,
            full_name=u.full_name,
            role=u.role,
            created_at=m.created_at,
        )
        for m, u in rows
    ]


@router.post(
    "/servers/{server_id}/members",
    response_model=ServerMemberRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_server_member(
    payload: ServerMemberCreate,
    server: FhirServer = Depends(manage_access),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Share the server with a user."""
    target = await db.get(User, payload.user_id)
    if target is None or target.keycloak_sub == DEV_USER_SUB:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if target.id == server.owner_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "User already owns this server")

    member = ServerMember(server_id=server.id, user_id=target.id, added_by_id=user.id)
    db.add(member)
    db.add(
        server_audit_entry(
            AuditAction.SERVER_SHARE,
            user,
            server,
            target_type="User",
            target_id=target.username or str(target.id),
            payload={"user_id": str(target.id), "role": target.role},
        )
    )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "The server is already shared with this user"
        ) from exc
    await db.refresh(member)
    return ServerMemberRead(
        user_id=target.id,
        username=target.username,
        full_name=target.full_name,
        role=target.role,
        created_at=member.created_at,
    )


@router.delete(
    "/servers/{server_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_server_member(
    user_id: UUID,
    server: FhirServer = Depends(manage_access),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Stop sharing the server with a user."""
    member = (
        await db.execute(
            select(ServerMember).where(
                ServerMember.server_id == server.id, ServerMember.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User is not a member")
    target = await db.get(User, user_id)
    await db.delete(member)
    db.add(
        server_audit_entry(
            AuditAction.SERVER_UNSHARE,
            user,
            server,
            target_type="User",
            target_id=(target.username if target else None) or str(user_id),
            payload={"user_id": str(user_id)},
        )
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Read-only views
# ---------------------------------------------------------------------------


@router.get("/servers/{server_id}", response_model=FhirServerRead)
async def get_fhir_server(
    server: FhirServer = Depends(server_access()),
    user: User = Depends(get_current_user),
):
    """Single FHIR server details."""
    return _to_read(server, user)


@router.get("/servers/{server_id}/metadata", response_model=ServerMetadata)
async def get_server_metadata(server: FhirServer = Depends(server_access())):
    """
    Connection test: fetch the FHIR server's CapabilityStatement and report
    version + response time. Returns ok=false instead of raising so the
    frontend can render a clean error state.
    """
    auth = build_httpx_auth(server.auth_config)
    base_url = str(server.base_url).rstrip("/")
    url = f"{base_url}/metadata"

    started = monotonic()
    timeout = httpx.Timeout(connect=10.0, read=15.0, write=10.0, pool=10.0)

    try:
        async with httpx.AsyncClient(timeout=timeout, auth=auth) as client:
            resp = await client.get(
                url,
                headers={"Accept": "application/fhir+json"},
            )
            elapsed_ms = int((monotonic() - started) * 1000)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        elapsed_ms = int((monotonic() - started) * 1000)
        return ServerMetadata(ok=False, response_ms=elapsed_ms, error=str(exc)[:300])

    software = data.get("software") or {}
    return ServerMetadata(
        ok=True,
        response_ms=elapsed_ms,
        fhir_version=data.get("fhirVersion"),
        software_name=software.get("name"),
        software_version=software.get("version"),
        publisher=data.get("publisher"),
    )


@router.get(
    "/servers/{server_id}/resource-counts",
    response_model=list[ResourceCount],
)
async def get_server_resource_counts(server: FhirServer = Depends(server_access())):
    """`_summary=count` per supported resource type, fired in parallel."""
    auth = build_httpx_auth(server.auth_config)
    base_url = str(server.base_url).rstrip("/")

    timeout = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)

    async with httpx.AsyncClient(timeout=timeout, auth=auth) as client:

        async def fetch_one(rt: str) -> ResourceCount:
            try:
                resp = await client.get(
                    f"{base_url}/{rt}",
                    params={"_summary": "count"},
                    headers={"Accept": "application/fhir+json"},
                )
                resp.raise_for_status()
                data = resp.json()
                return ResourceCount(
                    resource_type=rt,
                    total=int(data.get("total", 0)),
                    ok=True,
                )
            except Exception as exc:
                return ResourceCount(
                    resource_type=rt,
                    total=0,
                    ok=False,
                    error=str(exc)[:200],
                )

        return await asyncio.gather(*[fetch_one(rt) for rt in RESOURCE_TYPES])
