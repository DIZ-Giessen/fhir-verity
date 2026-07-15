"""Endpoints to start and manage validation runs."""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, desc, exists, func, select
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
from app.models.invalid_resource import InvalidResource, InvalidResourceIssue
from app.services.fhir_auth import build_httpx_auth

from app.core.security import get_current_user, load_server_scoped
from app.models.user import User, UserRole
from app.core.config import get_settings
from app.services.email_service import build_run_notification, send_email
from app.models.validation_config import ValidationConfig
from app.services.validation_filters import build_filter_params, validate_filters


router = APIRouter()

logger = logging.getLogger(__name__)

settings = get_settings()


async def _load_filter_params(
    server_id: UUID, resource_type: str, db: AsyncSession
) -> dict:
    """Load the server-specific filter for this resource type (falling back to
    the global default), validate it, and translate to FHIR search params.
    Returns {} when no filter is configured -> unchanged crawl behaviour."""
    # server-specific first, then global default (server_id IS NULL)
    stmt = select(ValidationConfig).where(
        ValidationConfig.resource_type == resource_type,
        ValidationConfig.server_id == server_id,
    )
    cfg = (await db.execute(stmt)).scalar_one_or_none()
    if cfg is None:
        stmt = select(ValidationConfig).where(
            ValidationConfig.resource_type == resource_type,
            ValidationConfig.server_id.is_(None),
        )
        cfg = (await db.execute(stmt)).scalar_one_or_none()

    raw = (cfg.filters if cfg else None) or {}
    try:
        cleaned = validate_filters(raw)
    except Exception as e:
        logger.warning(
            "Invalid filters for %s on server %s, ignoring: %s",
            resource_type,
            server_id,
            e,
        )
        return {}
    return build_filter_params(cleaned)


async def _load_run_scoped(run_id: UUID, user: User, db: AsyncSession) -> ValidationRun:
    """Load a run, enforcing ownership through its server.
    404 if the run is missing or its server isn't visible to this user."""
    run = (
        await db.execute(select(ValidationRun).where(ValidationRun.id == run_id))
    ).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Validation run not found")
    await load_server_scoped(run.server_id, user, db)  # raises 404 if not owned
    return run


@router.post("/validation/start", response_model=ValidationRunRead)
async def start_validation(
    request: ValidationStartRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Start a new validation run asynchronously."""

    # Ownership scope (404 for foreign servers), then active check.
    server = await load_server_scoped(request.server_id, user, db)
    if not server.is_active:
        raise HTTPException(
            status_code=404, detail="FHIR Server not found or is not active"
        )

    # create validation run
    new_run = ValidationRun(
        server_id=request.server_id,
        resource_types=request.resource_types,
        status=ValidationStatus.RUNNING,
        started_at=datetime.now(),
        triggered_by_id=user.id,
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
        server.name,
    )

    return new_run


@router.post("/validation/runs/{run_id}/resume", response_model=ValidationRunRead)
async def resume_validation(
    run_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Resume a run interrupted by a full process crash (status FAILED or
    CANCELLED). Each resource type continues from the _lastUpdated watermark in
    ValidationRun.checkpoint; already-completed types are skipped. Transient
    paging failures mid-run are self-healed by iter_pages and need no resume.
    """
    run = (
        await db.execute(select(ValidationRun).where(ValidationRun.id == run_id))
    ).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Validation run not found")

    if run.status == ValidationStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Run is already running")
    if run.status == ValidationStatus.COMPLETED:
        raise HTTPException(status_code=409, detail="Run is already completed")

    server = await load_server_scoped(run.server_id, user, db)
    if not server.is_active:
        raise HTTPException(
            status_code=404, detail="FHIR Server not found or is not active"
        )

    run.status = ValidationStatus.RUNNING
    run.error_message = None
    run.finished_at = None
    await db.commit()
    await db.refresh(run)

    background_tasks.add_task(
        run_validation_task,
        run.id,
        str(server.base_url),
        run.resource_types,  # gleiche Scope wie beim ursprünglichen Lauf
        server.auth_config or {},
        server.id,
        server.name,
    )
    return run


async def _mark_type_completed(run_id: UUID, resource_type: str, db: AsyncSession):
    """Record a resource type as fully validated in the run's checkpoint."""
    run = (
        await db.execute(select(ValidationRun).where(ValidationRun.id == run_id))
    ).scalar_one_or_none()
    if not run:
        return
    cp = dict(run.checkpoint or {})
    completed = list(cp.get("_completed", []))
    if resource_type not in completed:
        completed.append(resource_type)
    cp["_completed"] = completed
    run.checkpoint = cp
    await db.commit()


async def _notify_run_finished(
    run_id: UUID,
    server_name: str,
    db: AsyncSession,
) -> None:
    """Look up the trigger user and send a completion/failure email.
    No-op if the run has no trigger user or the user opted out."""
    run = (
        await db.execute(select(ValidationRun).where(ValidationRun.id == run_id))
    ).scalar_one_or_none()
    if not run or not run.triggered_by_id:
        return

    user = (
        await db.execute(select(User).where(User.id == run.triggered_by_id))
    ).scalar_one_or_none()
    if not user or not user.email_notifications_enabled or not user.email:
        return

    status_value = run.status.value if hasattr(run.status, "value") else str(run.status)
    run_url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/runs/{run_id}"

    subject, body = build_run_notification(
        recipient_name=user.full_name or user.username,
        status=status_value,
        server_name=server_name,
        total_processed=run.total_processed or 0,
        total_invalid=run.total_invalid or 0,
        run_url=run_url,
        error_message=run.error_message,
    )
    await send_email(user.email, subject, body)


async def run_validation_task(
    run_id: UUID,
    base_url: str,
    resource_types: list[str],
    auth_config: dict,
    server_id: UUID,
    server_name: str,
):
    """Asynchronous Background task"""

    async with AsyncSessionLocal() as db:
        try:
            to_validate = (
                resource_types
                if "All" not in resource_types
                else list(VALIDATORS.keys())
            )

            # Resume-aware: types already fully validated in a prior attempt are
            # skipped; an in-progress type resumes from its _lastUpdated watermark
            # inside iter_pages automatically.
            run = (
                await db.execute(
                    select(ValidationRun).where(ValidationRun.id == run_id)
                )
            ).scalar_one_or_none()
            completed = (
                set((run.checkpoint or {}).get("_completed", [])) if run else set()
            )

            # Build Time Out
            timeout = httpx.Timeout(connect=10.0, read=300.0, write=10.0, pool=10.0)
            auth = build_httpx_auth(auth_config)
            async with httpx.AsyncClient(timeout=timeout, auth=auth) as client:
                for res_type in to_validate:
                    validator_class = VALIDATORS.get(res_type)
                    if not validator_class:
                        continue

                    if res_type in completed:
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
                    validator.filter_params = await _load_filter_params(
                        server_id, res_type, db
                    )
                    await validator.validate_and_save(run_id, db)
                    await _mark_type_completed(run_id, res_type, db)

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

            await _notify_run_finished(run_id, server_name, db)

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
            async with AsyncSessionLocal() as notify_db:
                await _notify_run_finished(run_id, server_name, notify_db)


@router.get("/validation/runs", response_model=PaginatedRuns)
async def list_validation_runs(
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = None,
    server_id: Optional[UUID] = None,
    started_after: Optional[datetime] = None,
    started_before: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
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

    is_admin = user.role == UserRole.admin.value

    count_stmt = select(func.count(ValidationRun.id))
    page_stmt = select(ValidationRun)
    if not is_admin:
        count_stmt = count_stmt.join(
            FhirServer, FhirServer.id == ValidationRun.server_id
        ).where(FhirServer.owner_id == user.id)
        page_stmt = page_stmt.join(
            FhirServer, FhirServer.id == ValidationRun.server_id
        ).where(FhirServer.owner_id == user.id)
    if where_clause is not None:
        count_stmt = count_stmt.where(where_clause)
        page_stmt = page_stmt.where(where_clause)

    total = (await db.execute(count_stmt)).scalar_one()

    page_stmt = (
        page_stmt.order_by(desc(ValidationRun.started_at)).offset(skip).limit(limit)
    )
    result = await db.execute(page_stmt)
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
    user: User = Depends(get_current_user),
):
    """
    Detail view of a single validation run, including per-resource breakdown.
    """
    run = await _load_run_scoped(run_id, user, db)

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
        test_report=run.test_report or {},
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
    user: User = Depends(get_current_user),
):
    """
    Paginated invalid resources for a given run. Rule/severity filters use the normalized invalid_resource_issues table via EXISTS, so pagination and counts run entirely in SQL.
    """
    run = await _load_run_scoped(run_id, user, db)

    # When rule/severity filters are present we need to inspect issues_detail.
    base_filters = [InvalidResource.server_id == run.server_id]
    if only_current_run:
        base_filters.append(InvalidResource.last_seen_run_id == run_id)
    if resource_type:
        base_filters.append(InvalidResource.resource_type == resource_type)

    if rule or severity:
        issue_match = [InvalidResourceIssue.invalid_resource_id == InvalidResource.id]
        if rule:
            issue_match.append(InvalidResourceIssue.rule == rule)
        if severity:
            issue_match.append(InvalidResourceIssue.severity == severity)
        base_filters.append(exists(select(InvalidResourceIssue.id).where(*issue_match)))

    where_clause = and_(*base_filters)

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
                run_id=str(row.last_seen_run_id),
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
    user: User = Depends(get_current_user),
):
    """
    Aggregated summary from precomputed run.rule_stats — O(1) regardless of
    how many invalid resources the run produced. The numbers are a snapshot
    of this run, written incrementally during validation.
    """
    run = await _load_run_scoped(run_id, user, db)

    per_stats = run.per_resource_stats or {}
    by_resource_type = []
    for rt, bucket in (run.rule_stats or {}).items():
        by_rule = []
        for key, count in sorted(bucket.items(), key=lambda x: -x[1]):
            rule, _, severity = key.partition("|")
            by_rule.append(
                RuleViolationCount(rule=rule, severity=severity, count=count)
            )
        by_resource_type.append(
            ResourceTypeSummary(
                resource_type=rt,
                total_invalid=per_stats.get(rt, {}).get("invalid", 0),
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
