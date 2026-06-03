"""Endpoints to start and manage validation runs."""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, desc, func, select
import httpx


from app.api.v1.endpoints.websocket import broadcast_progress
from app.core.database import AsyncSessionLocal, get_db
from app.models.fhir_server import FhirServer
from app.models.validation_run import ValidationRun, ValidationStatus
from app.schemas.validation import (
    InvalidResourceRead,
    IssueDetail,
    PaginatedInvalidResources,
    PaginatedRuns,
    PerResourceStats,
    ResourceTypeSummary,
    RuleViolationCount,
    RunSummary,
    ValidationRunDetail,
    ValidationRunListItem,
    ValidationStartRequest,
    ValidationRunRead,
)

from app.services.validation_rules import VALIDATORS
from app.services.fhir_report_service import generate_and_post_reports
from app.models.invalid_resource import InvalidResource
from app.services.fhir_auth import build_httpx_auth


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
            auth = build_httpx_auth(auth_config)
            async with httpx.AsyncClient(timeout=timeout, auth=auth) as client:
                for res_type in to_validate:
                    validator_class = VALIDATORS.get(res_type)
                    if not validator_class:
                        continue

                    await broadcast_progress(
                        str(run_id),
                        {
                            "type": "resource_start",
                            "run_id": str(run_id),
                            "status": "running",
                            "resource_type": res_type,
                            "message": f"Starting validation for {res_type}",
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
                await db.refresh(run)

                # FHIR Reports generieren und posten
                await generate_and_post_reports(
                    run=run,
                    server_base_url=base_url,
                    server_id=str(server_id),
                    auth_config=auth_config,
                    db=db,
                )

            await broadcast_progress(
                str(run_id),
                {
                    "type": "completed",
                    "run_id": str(run_id),
                    "status": "completed",
                    "total_processed": run.total_processed if run else 0,
                    "total_invalid": run.total_invalid if run else 0,
                    "message": "Validation run completed successfully",
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
                    "type": "failled",
                    "run_id": str(run_id),
                    "status": "failed",
                    "error": str(e),
                },
            )


@router.get("/validation/runs", response_model=PaginatedRuns)
async def list_validation_runs(
    skip: int = 0,
    limit: int = 20,
    status: Optional[str] = None,
    server_id: Optional[UUID] = None,
    started_after: Optional[datetime] = None,
    started_before: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Pagined list of validation runs. Supports filterig by status, server amd time range. Sorted by started_at DESC
    """
    filters = []
    if status:
        filters.append(ValidationRun.status == status)
    if server_id:
        filters.append(ValidationRun.server_id == server_id)
    if started_after:
        filters.append(ValidationRun.started_at >= started_after)
    if started_before:
        filters.append(ValidationRun.started_at <= started_before)

    where_clause = and_(*filters) if filters else None

    # Count total for Pagination metadata
    count_stmt = select(func.count(ValidationRun.id))
    if where_clause is not None:
        count_stmt = count_stmt.where(where_clause)
    total = (await db.execute(count_stmt)).scalar_one()

    # Fetch page
    stmt = select(ValidationRun).order_by(desc(ValidationRun.started_at))
    if where_clause is not None:
        stmt = stmt.where(where_clause)
    stmt = stmt.offset(skip).limit(limit)

    result = await db.execute(stmt)

    runs = result.scalars().all()

    return PaginatedRuns(
        total=total,
        skip=skip,
        limit=limit,
        items=[ValidationRunListItem.model_validate(r) for r in runs],
    )


# GET Detail View


@router.get("/validation/runs/{run_id}", response_model=ValidationRunDetail)
async def get_validation_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Detail view of a single validation run, including per-resource breakdown.
    """
    stmt = select(ValidationRun).where(ValidationRun.id == run_id)
    result = await db.execute(stmt)
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Validation run not found")

    per_resource = []
    for resource_type, stats in (run.per_resource_stats or {}).items():
        processed = stats.get("processed", 0)
        invalid = stats.get("invalid", 0)
        rate = (invalid / processed) if processed > 0 else 0.0
        per_resource.append(
            PerResourceStats(
                resource_type=resource_type,
                processed=processed,
                invalid=invalid,
                invalid_rate=round(rate, 4),
            )
        )

    elapsed = None
    if run.finished_at and run.started_at:
        elapsed = int((run.finished_at - run.started_at).total_seconds())

    return ValidationRunDetail(
        id=run.id,
        server_id=run.server_id,
        status=run.status.value if hasattr(run.status, "value") else str(run.status),
        started_at=run.started_at,
        finished_at=run.finished_at,
        total_processed=run.total_processed or 0,
        total_invalid=run.total_invalid or 0,
        resource_types=run.resource_types or [],
        error_message=run.error_message,
        per_resource_stats=per_resource,
        elapsed_seconds=elapsed,
    )


# ---------------------------------------------------------------------------
# GET /validation/runs/{run_id}/invalid-resources — Paginated invalid list
# ---------------------------------------------------------------------------


@router.get(
    "/validation/runs/{run_id}/invalid-resources",
    response_model=PaginatedInvalidResources,
)
async def list_invalid_resources(
    run_id: UUID,
    skip: int = 0,
    limit: int = 50,
    resource_type: Optional[str] = None,
    rule: Optional[str] = None,
    severity: Optional[str] = None,
    only_current_run: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """
    Paginated invalid resources for a given run, with optional filters.
    Filters by rule and severity scan metrics['issues_detail'] in-memory
    AFTER fetching, since JSON-level filtering isn't portable across DBs.
    For very large result sets this should be migrated to JSONB + GIN index.
    """
    run_stmt = select(ValidationRun).where(ValidationRun.id == run_id)
    run_result = await db.execute(run_stmt)
    run = run_result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Validation run not found")

    base_filters = [InvalidResource.server_id == run.server_id]
    if only_current_run:
        base_filters.append(InvalidResource.last_seen_run_id == run_id)
    if resource_type:
        base_filters.append(InvalidResource.resource_type == resource_type)

    where_clause = and_(*base_filters)

    # When rule/severity filters are present we need to inspect issues_detail.
    # Strategy: fetch a larger window, filter in Python, then paginate.
    needs_post_filter = bool(rule or severity)

    if needs_post_filter:
        stmt = (
            select(InvalidResource)
            .where(where_clause)
            .order_by(desc(InvalidResource.last_seen_at))
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()

        filtered = []
        for row in rows:
            issues = (row.metrics or {}).get("issues_detail", [])
            match = True
            if rule:
                match = match and any(i.get("rule") == rule for i in issues)
            if severity:
                match = match and any(i.get("severity") == severity for i in issues)
            if match:
                filtered.append(row)

        total = len(filtered)
        page = filtered[skip : skip + limit]
    else:
        count_stmt = select(func.count(InvalidResource.id)).where(where_clause)
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = (
            select(InvalidResource)
            .where(where_clause)
            .order_by(desc(InvalidResource.created_at))
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(stmt)
        page = result.scalars().all()

    items = []
    for row in page:
        issues_detail = [
            IssueDetail(**i) for i in (row.metrics or {}).get("issues_detail", [])
        ]
        items.append(
            InvalidResourceRead(
                id=row.id,
                run_id=row.run_id,
                server_base_url=row.server_base_url,
                resource_type=row.resource_type,
                resource_id=row.resource_id,
                issues=row.issues or [],
                issues_detail=issues_detail,
                metrics={
                    k: v for k, v in (row.metrics or {}).items() if k != "issues_detail"
                },
                created_at=row.created_at,
            )
        )

    return PaginatedInvalidResources(
        total=total,
        skip=skip,
        limit=limit,
        items=items,
    )


# ---------------------------------------------------------------------------
# GET /validation/runs/{run_id}/summary — Aggregated stats for dashboards
# ---------------------------------------------------------------------------


@router.get("/validation/runs/{run_id}/summary", response_model=RunSummary)
async def get_run_summary(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Aggregated summary: total counts and rule-violation breakdown
    per resource type. Used for heatmaps and dashboard tiles.
    """
    run_stmt = select(ValidationRun).where(ValidationRun.id == run_id)
    run = (await db.execute(run_stmt)).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Validation run not found")

    inv_stmt = select(InvalidResource).where(
        InvalidResource.server_id == run.server_id,
        InvalidResource.last_seen_run_id == run.id,
    )
    invalid_rows = (await db.execute(inv_stmt)).scalars().all()

    # Aggregate rule violations per resource_type
    # Structure: {resource_type: {(rule, severity): count}}
    aggregated: dict[str, dict[tuple[str, str], int]] = {}
    totals_by_type: dict[str, int] = {}

    for row in invalid_rows:
        rt = row.resource_type
        totals_by_type[rt] = totals_by_type.get(rt, 0) + 1
        rt_bucket = aggregated.setdefault(rt, {})
        for issue in (row.metrics or {}).get("issues_detail", []):
            key = (issue.get("rule", "unknown"), issue.get("severity", "unknown"))
            rt_bucket[key] = rt_bucket.get(key, 0) + 1

    by_resource_type = []
    for rt, rule_counts in aggregated.items():
        by_rule = [
            RuleViolationCount(rule=r, severity=s, count=c)
            for (r, s), c in sorted(rule_counts.items(), key=lambda x: -x[1])
        ]
        by_resource_type.append(
            ResourceTypeSummary(
                resource_type=rt,
                total_invalid=totals_by_type.get(rt, 0),
                by_rule=by_rule,
            )
        )

    total_processed = run.total_processed or 0
    total_invalid = run.total_invalid or 0
    rate = (total_invalid / total_processed) if total_processed > 0 else 0.0

    return RunSummary(
        run_id=run.id,
        total_processed=total_processed,
        total_invalid=total_invalid,
        overall_invalid_rate=round(rate, 4),
        by_resource_type=by_resource_type,
    )
