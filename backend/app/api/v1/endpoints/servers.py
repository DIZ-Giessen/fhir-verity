"""
API endpoints for managing FHIR Servers.
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.fhir_server import FhirServer
from app.schemas.server import FhirServerCreate, FhirServerRead, FhirServerUpdate
from app.schemas.server import ServerAuthRead, ServerAuthUpdate
from app.services.fhir_auth import normalize_auth_config

router = APIRouter()


@router.post(
    "/servers", response_model=FhirServerRead, status_code=status.HTTP_201_CREATED
)
async def create_fhir_server(
    server_in: FhirServerCreate, db: AsyncSession = Depends(get_db)
):
    """Create a new FHIR server."""
    base_url_str = str(server_in.base_url)
    # Prüfen ob Base-Url schon existiert.
    stmt = select(FhirServer).where(FhirServer.base_url == base_url_str)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="FHIR Server with this base URL already exists",
        )
    new_server = FhirServer(
        name=server_in.name,
        base_url=base_url_str,
        project_id=server_in.project_id,
        auth_config=server_in.auth_config,
        is_active=True,
    )

    db.add(new_server)
    await db.commit()
    await db.refresh(new_server)

    return FhirServerRead.model_validate(new_server)


@router.get("/servers", response_model=list[FhirServerRead])
async def list_fhir_servers(
    db: AsyncSession = Depends(get_db), skip: int = 0, limit: int = 100
):
    """List all FHIR servers."""
    stmt = select(FhirServer).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


def _to_read(server: FhirServer) -> FhirServerRead:
    return FhirServerRead(
        id=server.id,
        name=server.name,
        base_url=server.base_url,
        project_id=server.project_id,
        is_active=server.is_active,
        has_auth_config=server.auth_config is not None,
        created_at=server.created_at,
        updated_at=server.updated_at,
    )


@router.patch(
    "/servers/{server_id}",
    response_model=FhirServerRead,
    summary="Update FHIR server",
)
async def update_fhir_server(
    server_id: UUID,
    payload: FhirServerUpdate,
    db: AsyncSession = Depends(get_db),
) -> FhirServerRead:
    """Update FHIR Server"""
    stmt = select(FhirServer).where(FhirServer.id == server_id)
    result = await db.execute(stmt)
    server = result.scalar_one_or_none()

    if server is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FHIR server not found",
        )

    updates = payload.model_dump(exclude_unset=True)
    if "base_url" in updates and updates["base_url"] is not None:
        updates["base_url"] = str(updates["base_url"])

    for key, value in updates.items():
        setattr(server, key, value)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A server with this base_url already exists",
        )

    await db.refresh(server)
    return _to_read(server)


@router.delete(
    "/servers/{server_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete FHIR server",
)
async def delete_fhir_server(
    server_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete FHIR Servers"""
    stmt = select(FhirServer).where(FhirServer.id == server_id)
    result = await db.execute(stmt)
    server = result.scalar_one_or_none()

    if server is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FHIR server not found",
        )

    await db.delete(server)
    await db.commit()


async def _get_server_or_404(server_id: UUID, db: AsyncSession) -> FhirServer:
    server = (
        await db.execute(select(FhirServer).where(FhirServer.id == server_id))
    ).scalar_one_or_none()
    if server is None:
        raise HTTPException(status_code=404, detail="FHIR server not found")
    return server


def _auth_read(cfg: dict) -> ServerAuthRead:
    return ServerAuthRead(
        type=cfg["type"],
        username=cfg.get("username"),
        client_id=cfg.get("client_id"),
        token_url=cfg.get("token_url"),
        scope=cfg.get("scope"),
    )


@router.get("/servers/{server_id}/auth", response_model=ServerAuthRead)
async def get_server_auth(server_id: UUID, db: AsyncSession = Depends(get_db)):
    """Return the non-secret parts of a server's auth config."""
    server = await _get_server_or_404(server_id, db)
    return _auth_read(normalize_auth_config(server.auth_config))


@router.patch("/servers/{server_id}/auth", response_model=ServerAuthRead)
async def update_server_auth(
    server_id: UUID,
    payload: ServerAuthUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Replace a server's auth. Omitted secrets keep their existing value."""
    server = await _get_server_or_404(server_id, db)
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
        new_cfg = {
            "type": "oauth2_client_credentials",
            "token_url": token_url,
            "client_id": client_id,
            "client_secret": client_secret,
        }
        if scope:
            new_cfg["scope"] = scope

    server.auth_config = new_cfg
    await db.commit()
    await db.refresh(server)
    return _auth_read(normalize_auth_config(server.auth_config))
