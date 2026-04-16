from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx

from uuid import UUID
from app.core.database import get_db
from app.models.fhir_server import FhirServer
from app.models.validation_run import ValidationRun, ValidationStatus
from app.schemas.validation import ValidationStartRequest, ValidationRunRead

from app.services.validation_rules import VALIDATORS


router = APIRouter() 

@router.post("/validation/start", response_model=ValidationRunRead)
async def start_validation(
    request: ValidationStartRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Start a new validation run asynchronously."""

    # verify if server exists
    stmt = select(FhirServer).where(FhirServer.id == request.server_id, FhirServer.is_active == True)
    result = await db.execute(stmt)
    server = result.scalar_one_or_none()

    if not server: 
        raise HTTPException(status_code=404, detail="FHIR Server not found or is not active")

    # create validation run
    new_run = ValidationRun(
        server_id=request.server_id,
        resource_types=request.resource_types,
        status=ValidationStatus.RUNNING,
        started_at=datetime.now()
    ) 

    db.add(new_run)
    await db.commit()
    await db.refresh(new_run)

    # start background task
    background_tasks.add_task(run_validation_task, new_run.id, str(server.base_url), request.resource_types, request.server_id, db)

    return new_run


async def run_validation_task(run_id: UUID, base_url: str, resource_types: list,server_id: UUID, db: AsyncSession):
    """Background task to run the validation."""

    try: 
        print(f"Starting validation run {run_id} for {base_url} with resource types {resource_types}")

        # fetch server mit config 
        stmt = select(FhirServer).where(FhirServer.id == server_id)
        result = await db.execute(stmt)
        server = result.scalar_one_or_none()

        auth_config = server.auth_config if server else {}


        async with httpx.AsyncClient(timeout=60.0) as client:
            # get all bundles
            to_validate = resource_types if "All" not in resource_types else ["Patient", "Encounter", "Medication", "MedicationAdministration", "MedicationRequest"]

            for res_type in to_validate:
                validator_class = VALIDATORS.get(res_type)
                if validator_class:
                    validator = validator_class(client, base_url, auth_config)
                    await validator.validate_and_save(run_id,db)
                else:
                    print(f"Not Validator Resource for: {res_type}")


        stmt = select(ValidationRun).where(ValidationRun.id == run_id)
        result = await db.execute(stmt)
        run = result.scalar_one_or_none()

        if run: 
            run.status = ValidationStatus.COMPLETED
            run.finished_at = datetime.now()
            await db.commit()
            print(f"Validation run {run_id} completed successfully")
    except Exception as e:
        print(f"Error running validation task: {e}")

        # Run as failed set
        stmt = select(ValidationRun).where(ValidationRun.id == run_id)
        result = await db.execute(stmt)
        run = result.scalar_one_or_none()
        if run: 
            run.status = ValidationStatus.FAILED
            run.error_message = str(e)
            await db.commit()
        