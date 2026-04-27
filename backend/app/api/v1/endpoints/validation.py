"""Endpoints to start and manage validation runs."""

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx


from app.api.v1.endpoints.websocket import broadcast_progress
from app.core.database import AsyncSessionLocal, get_db
from app.models.fhir_server import FhirServer
from app.models.validation_run import ValidationRun, ValidationStatus
from app.schemas.validation import ValidationStartRequest, ValidationRunRead

from app.services.validation_rules import VALIDATORS


router = APIRouter()

logger = logging.getLogger(__name__)


@router.post("/validation/start", response_model=ValidationRunRead)
async def start_validation(
    request: ValidationStartRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Start a new validation run asynchronously."""

    # verify if server exists
    stmt = select(FhirServer).where(
        FhirServer.id == request.server_id,
        FhirServer.is_active.is_(True),
    )

    result = await db.execute(stmt)
    server = result.scalar_one_or_none()

    if not server:
        raise HTTPException(
            status_code=404, detail="FHIR Server not found or is not active"
        )

    # create validation run
    new_run = ValidationRun(
        server_id=request.server_id,
        resource_types=request.resource_types,
        status=ValidationStatus.RUNNING,
        started_at=datetime.now(),
    )

    db.add(new_run)
    await db.commit()
    await db.refresh(new_run)

    # start background task
    background_tasks.add_task(
        run_validation_task,
        new_run.id,
        str(server.base_url),
        request.resource_types,
        server.auth_config or {},
        server.id,
    )

    return new_run


async def run_validation_task(
    run_id: UUID,
    base_url: str,
    resource_types: list[str],
    auth_config: dict,
    server_id: UUID,
):
    """Asynchronous Background task"""

    async with AsyncSessionLocal() as db:
        try:
            to_validate = (
                resource_types
                if "All" not in resource_types
                else list(VALIDATORS.keys())
            )

            # Build Time Out
            timeout = httpx.Timeout(connect=10.0, read=300.0, write=10.0, pool=10.0)

            async with httpx.AsyncClient(timeout=timeout) as client:
                for res_type in to_validate:
                    validator_class = VALIDATORS.get(res_type)
                    if not validator_class:
                        continue

                    await broadcast_progress(
                        str(run_id),
                        {
                            "run_id": str(run_id),
                            "status": "running",
                            "current_resource": res_type,
                        },
                    )

                    validator = validator_class(
                        client, base_url, auth_config, server_id=server_id
                    )
                    await validator.validate_and_save(run_id, db)

            # Run als abgeschlossen markieren
            stmt = select(ValidationRun).where(ValidationRun.id == run_id)
            result = await db.execute(stmt)
            run = result.scalar_one_or_none()

            if run:
                run.status = ValidationStatus.COMPLETED
                run.finished_at = datetime.now()
                await db.commit()

            await broadcast_progress(
                str(run_id),
                {
                    "run_id": str(run_id),
                    "status": "completed",
                    "total_processed": run.total_processed if run else 0,
                    "total_invalid": run.total_invalid if run else 0,
                },
            )

        except Exception as e:

            logger.error("Validation task %s failde: %s", run_id, e)

            try:
                await db.rollback()
            except Exception:
                logger.warning("The session is already down.")

            async with AsyncSessionLocal() as error_db:
                stmt = select(ValidationRun).where(ValidationRun.id == run_id)
                result = await error_db.execute(stmt)
                run = result.scalar_one_or_none()
                if run:
                    run.status = ValidationStatus.FAILED
                    run.error_message = str(e)[:500]
                    await error_db.commit()

            await broadcast_progress(
                str(run_id),
                {
                    "run_id": str(run_id),
                    "status": "failed",
                    "error": str(e),
                },
            )
