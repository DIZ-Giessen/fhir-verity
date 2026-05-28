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
