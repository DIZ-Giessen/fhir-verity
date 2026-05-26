"""
API endpoints for managing FHIR Servers.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.fhir_server import FhirServer
from app.schemas.server import FhirServerCreate, FhirServerRead

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
