"""Endpoints to delete or patch FHIR resources on the source server."""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
import asyncio
from time import monotonic

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, desc, exists, func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    get_current_user,
    require_role,
    server_access,
    load_server_scoped,
)
from app.models.audit_log import AuditAction, AuditLog, AuditStatus
from app.models.fhir_server import FhirServer
from app.models.invalid_resource import InvalidResource, InvalidResourceIssue
from app.models.user import User, UserRole
from app.schemas.resource_action import (
    ActionResult,
    AuditLogDetail,
    AuditLogListItem,
    AutoFixRequest,
    BulkActionError,
    BulkActionResult,
    BulkDeleteRequest,
    BulkFixRequest,
    DeleteRequest,
    FixableTemplate,
    PaginatedAuditLog,
    PatchRequest,
)
from app.services.fix_templates import get_patch_template, has_template, list_templates
from app.services.fhir_auth import build_httpx_auth

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _fetch_resource_with_etag(
    base_url: str,
    resource_type: str,
    resource_id: str,
    client: httpx.AsyncClient,
) -> tuple[Optional[dict], Optional[str]]:
    """Returns (resource_body, etag) or (None, None) if the resource doesn't exist."""
    url = f"{base_url.rstrip('/')}/{resource_type}/{resource_id}"
    resp = await client.get(url, headers={"Accept": "application/fhir+json"})
    if resp.status_code == 404:
        return None, None
    resp.raise_for_status()
    return resp.json(), resp.headers.get("ETag")


async def _find_invalid_resource(
    server_id: UUID,
    resource_type: str,
    resource_id: str,
    db: AsyncSession,
) -> Optional[InvalidResource]:
    stmt = select(InvalidResource).where(
        InvalidResource.server_id == server_id,
        InvalidResource.resource_type == resource_type,
        InvalidResource.resource_id == resource_id,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


# ---------------------------------------------------------------------------
# DELETE /resources/{server_id}/{resource_type}/{resource_id}
# ---------------------------------------------------------------------------
@router.delete(
    "/resources/{server_id}/{resource_type}/{resource_id}",
    response_model=ActionResult,
)
async def delete_resource(
    resource_type: str,
    resource_id: str,
    payload: Optional[DeleteRequest] = None,
    server: FhirServer = Depends(server_access(UserRole.editor.value)),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a FHIR resource from the source server (with ETag-based optimistic locking).
    On success: also removes the entry from invalid_resources.
    """
    auth_config = server.auth_config or {}
    base_url = str(server.base_url).rstrip("/")

    resource_before: Optional[dict] = None
    fhir_status: Optional[str] = None
    status = AuditStatus.SUCCESS
    error_message: Optional[str] = None

    auth = build_httpx_auth(auth_config)
    timeout = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
    async with httpx.AsyncClient(timeout=timeout, auth=auth) as client:
        try:
            resource_before, etag = await _fetch_resource_with_etag(
                base_url,
                resource_type,
                resource_id,
                client,
            )
            if resource_before is None:
                status = AuditStatus.FAILED
                error_message = "Resource not found on FHIR server"
                fhir_status = "404"
            else:
                headers = {"Accept": "application/fhir+json"}
                if etag:
                    headers["If-Match"] = etag

                url = f"{base_url}/{resource_type}/{resource_id}"
                resp = await client.delete(url, headers=headers)
                fhir_status = str(resp.status_code)

                if resp.status_code in (200, 204):
                    inv = await _find_invalid_resource(
                        server.id, resource_type, resource_id, db
                    )
                    if inv:
                        await db.delete(inv)
                else:
                    status = AuditStatus.FAILED
                    error_message = (
                        f"FHIR server returned {resp.status_code}: {resp.text[:300]}"
                    )
        except httpx.HTTPError as exc:
            status = AuditStatus.FAILED
            error_message = str(exc)[:500]
            logger.error("DELETE failed for %s/%s: %s", resource_type, resource_id, exc)

    inv_for_link = await _find_invalid_resource(
        server.id, resource_type, resource_id, db
    )

    audit = AuditLog(
        server_id=server.id,
        server_base_url=base_url,
        resource_type=resource_type,
        resource_id=resource_id,
        invalid_resource_id=inv_for_link.id if inv_for_link else None,
        action=AuditAction.DELETE,
        fhir_request_payload=None,
        fhir_response_status=fhir_status,
        resource_before=resource_before,
        status=status,
        error_message=error_message,
        reason=payload.reason if payload else None,
        actor_id=user.id,
        executed_at=datetime.now(timezone.utc),
    )
    db.add(audit)
    await db.commit()
    await db.refresh(audit)

    return ActionResult(
        id=audit.id,
        action=audit.action.value,
        status=audit.status.value,
        resource_type=resource_type,
        resource_id=resource_id,
        fhir_response_status=fhir_status,
        error_message=error_message,
        executed_at=audit.executed_at,
    )


# ---------------------------------------------------------------------------
# Bulk helpers
# ---------------------------------------------------------------------------
# Parallel requests against the FHIR server during bulk operations.
BULK_CONCURRENCY = 20
# IN (...) lists are chunked to stay far below asyncpg's 32767 bind-parameter
# limit; a single IN with 50k ids would fail outright.
BULK_ID_CHUNK = 5000
# Longer error texts are cut before grouping so near-identical messages
# collapse into one bucket in the audit summary.
BULK_ERROR_MAX_LEN = 300


class _BulkOutcome:
    """Collects per-resource results of a bulk run without holding bodies."""

    def __init__(self) -> None:
        self.succeeded_ids: list[UUID] = []
        self.succeeded_refs: list[str] = []
        self.failed_by_error: dict[str, list[str]] = {}
        self.errors: list[BulkActionError] = []

    def ok(self, row) -> None:
        self.succeeded_ids.append(row.id)
        self.succeeded_refs.append(f"{row.resource_type}/{row.resource_id}")

    def fail(self, row, error: str) -> None:
        error = (error or "unknown error")[:BULK_ERROR_MAX_LEN]
        ref = f"{row.resource_type}/{row.resource_id}"
        self.failed_by_error.setdefault(error, []).append(ref)
        self.errors.append(
            BulkActionError(
                resource_type=row.resource_type,
                resource_id=row.resource_id,
                error=error,
            )
        )

    @property
    def failed(self) -> int:
        return len(self.errors)


def _invalid_resource_filters(
    server_id: UUID,
    resource_type: Optional[str],
    rule: Optional[str],
    severity: Optional[str],
) -> list:
    """Same filter semantics as the invalid-resources list."""
    filters = [InvalidResource.server_id == server_id]
    if resource_type:
        filters.append(InvalidResource.resource_type == resource_type)
    if rule or severity:
        issue_match = [InvalidResourceIssue.invalid_resource_id == InvalidResource.id]
        if rule:
            issue_match.append(InvalidResourceIssue.rule == rule)
        if severity:
            issue_match.append(InvalidResourceIssue.severity == severity)
        filters.append(exists(select(InvalidResourceIssue.id).where(*issue_match)))
    return filters


async def _count_matches(db: AsyncSession, filters: list) -> int:
    stmt = select(func.count()).select_from(InvalidResource).where(and_(*filters))
    return (await db.execute(stmt)).scalar_one()


async def _load_targets(db: AsyncSession, filters: list):
    """Only the identity columns: 50k rows with full issue JSON would be heavy."""
    stmt = select(
        InvalidResource.id,
        InvalidResource.resource_type,
        InvalidResource.resource_id,
    ).where(and_(*filters))
    return (await db.execute(stmt)).all()


async def _run_concurrently(items, worker) -> None:
    """Fixed pool of workers draining one shared iterator. Unlike one task per
    item, memory stays flat no matter how many resources are matched."""
    iterator = iter(items)

    async def drain() -> None:
        for item in iterator:
            await worker(item)

    await asyncio.gather(*(drain() for _ in range(BULK_CONCURRENCY)))


async def _delete_invalid_rows(db: AsyncSession, ids: list[UUID]) -> None:
    for i in range(0, len(ids), BULK_ID_CHUNK):
        chunk = ids[i : i + BULK_ID_CHUNK]
        await db.execute(delete(InvalidResource).where(InvalidResource.id.in_(chunk)))


def _bulk_audit_entry(
    *,
    action: AuditAction,
    server: FhirServer,
    user: User,
    resource_type: Optional[str],
    filter_used: dict,
    matched: int,
    outcome: _BulkOutcome,
    reason: Optional[str],
    elapsed: float,
) -> AuditLog:
    """
    One audit row for the whole bulk operation instead of one per resource,
    so a 50k cleanup adds one line to the log, not 50k.

    The row still records exactly which resources were changed (as
    "Type/id" references) and why others failed, grouped by error message.
    Per-resource snapshots (resource_before) are not kept here; HAPI's
    version history (GET [type]/[id]/_history) holds the prior versions.
    Single-resource DELETE/PATCH keep their full snapshot.
    """
    failed = outcome.failed
    return AuditLog(
        server_id=server.id,
        server_base_url=str(server.base_url).rstrip("/"),
        resource_type=resource_type or "*",
        resource_id=f"{matched} resources",
        invalid_resource_id=None,
        action=action,
        fhir_request_payload={
            "bulk": True,
            "filter": filter_used,
            "matched": matched,
            "succeeded": len(outcome.succeeded_refs),
            "failed": failed,
            "elapsed_seconds": round(elapsed, 2),
            "succeeded_resources": outcome.succeeded_refs,
            "failed_by_error": outcome.failed_by_error,
        },
        fhir_response_status=None,
        resource_before=None,
        status=AuditStatus.SUCCESS if failed == 0 else AuditStatus.FAILED,
        error_message=(
            None if failed == 0 else f"{failed} of {matched} operations failed"
        ),
        reason=reason,
        actor_id=user.id,
        executed_at=datetime.now(timezone.utc),
    )


def _bulk_result(
    matched: int, outcome: _BulkOutcome, elapsed: float
) -> BulkActionResult:
    return BulkActionResult(
        matched=matched,
        succeeded=len(outcome.succeeded_ids),
        failed=outcome.failed,
        dry_run=False,
        elapsed_seconds=round(elapsed, 2),
        errors=outcome.errors[:50],
    )


def _bulk_timeout() -> httpx.Timeout:
    return httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)


# ---------------------------------------------------------------------------
# POST /resources/bulk-delete
# ---------------------------------------------------------------------------
@router.post("/resources/bulk-delete", response_model=BulkActionResult)
async def bulk_delete_resources(
    payload: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.editor.value)),
):
    """
    Bulk-delete invalid resources matching a filter.

    The filter applies to the invalid_resources table — only resources that
    were previously detected as invalid can be deleted via this endpoint.

    With dry_run=true: returns match count without doing anything.
    Otherwise: deletes each matched resource on the FHIR server
    (BULK_CONCURRENCY in parallel, ETag-guarded), removes successful entries
    from invalid_resources and writes a single BULK_DELETE audit entry.
    """
    server = await load_server_scoped(payload.server_id, user, db)
    base_url = str(server.base_url).rstrip("/")
    filters = _invalid_resource_filters(
        payload.server_id, payload.resource_type, payload.rule, payload.severity
    )

    if payload.dry_run:
        return BulkActionResult(
            matched=await _count_matches(db, filters),
            succeeded=0,
            failed=0,
            dry_run=True,
            elapsed_seconds=0.0,
        )

    rows = await _load_targets(db, filters)
    matched = len(rows)
    start = monotonic()
    outcome = _BulkOutcome()

    auth = build_httpx_auth(server.auth_config or {})
    async with httpx.AsyncClient(timeout=_bulk_timeout(), auth=auth) as client:

        async def delete_one(row) -> None:
            try:
                resource, etag = await _fetch_resource_with_etag(
                    base_url, row.resource_type, row.resource_id, client
                )
                if resource is None:
                    outcome.fail(row, "Resource not found on FHIR server")
                    return
                headers = {"Accept": "application/fhir+json"}
                if etag:
                    headers["If-Match"] = etag
                resp = await client.delete(
                    f"{base_url}/{row.resource_type}/{row.resource_id}",
                    headers=headers,
                )
                if resp.status_code in (200, 204):
                    outcome.ok(row)
                else:
                    outcome.fail(
                        row,
                        f"FHIR server returned {resp.status_code}: {resp.text}",
                    )
            except Exception as exc:  # one bad resource must not abort the batch
                outcome.fail(row, str(exc))

        await _run_concurrently(rows, delete_one)

    elapsed = monotonic() - start
    await _delete_invalid_rows(db, outcome.succeeded_ids)
    if matched:
        db.add(
            _bulk_audit_entry(
                action=AuditAction.BULK_DELETE,
                server=server,
                user=user,
                resource_type=payload.resource_type,
                filter_used={
                    "resource_type": payload.resource_type,
                    "rule": payload.rule,
                    "severity": payload.severity,
                },
                matched=matched,
                outcome=outcome,
                reason=payload.reason,
                elapsed=elapsed,
            )
        )
    await db.commit()

    return _bulk_result(matched, outcome, elapsed)


# ---------------------------------------------------------------------------
# POST /resources/bulk-fix
# ---------------------------------------------------------------------------
@router.post("/resources/bulk-fix", response_model=BulkActionResult)
async def bulk_fix_resources(
    payload: BulkFixRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.editor.value)),
):
    """
    Bulk-PATCH invalid resources matching (server_id, resource_type, rule).

    Requires a pre-defined patch template for the (resource_type, rule) combo.
    Returns 400 if no template exists — in that case use bulk-delete instead.
    Writes a single BULK_PATCH audit entry for the whole operation.
    """
    if not has_template(payload.resource_type, payload.rule):
        raise HTTPException(
            status_code=400,
            detail=(
                f"No patch template available for "
                f"{payload.resource_type}/{payload.rule}. Use bulk-delete instead."
            ),
        )

    server = await load_server_scoped(payload.server_id, user, db)
    base_url = str(server.base_url).rstrip("/")
    filters = _invalid_resource_filters(
        payload.server_id, payload.resource_type, payload.rule, None
    )

    if payload.dry_run:
        return BulkActionResult(
            matched=await _count_matches(db, filters),
            succeeded=0,
            failed=0,
            dry_run=True,
            elapsed_seconds=0.0,
        )

    rows = await _load_targets(db, filters)
    matched = len(rows)
    start = monotonic()
    outcome = _BulkOutcome()

    auth = build_httpx_auth(server.auth_config or {})
    async with httpx.AsyncClient(timeout=_bulk_timeout(), auth=auth) as client:

        async def patch_one(row) -> None:
            try:
                resource, etag = await _fetch_resource_with_etag(
                    base_url, row.resource_type, row.resource_id, client
                )
                if resource is None:
                    outcome.fail(row, "Resource not found on FHIR server")
                    return
                patch_body = (
                    get_patch_template(
                        payload.resource_type, payload.rule, resource=resource
                    )
                    or []
                )
                if not patch_body:
                    outcome.fail(
                        row,
                        "Template produced no operations "
                        "(resource may already be clean)",
                    )
                    return
                headers = {
                    "Content-Type": "application/json-patch+json",
                    "Accept": "application/fhir+json",
                }
                if etag:
                    headers["If-Match"] = etag
                resp = await client.patch(
                    f"{base_url}/{row.resource_type}/{row.resource_id}",
                    json=patch_body,
                    headers=headers,
                )
                if resp.status_code in (200, 201):
                    outcome.ok(row)
                else:
                    outcome.fail(
                        row,
                        f"FHIR server returned {resp.status_code}: {resp.text}",
                    )
            except Exception as exc:  # one bad resource must not abort the batch
                outcome.fail(row, str(exc))

        await _run_concurrently(rows, patch_one)

    elapsed = monotonic() - start
    await _delete_invalid_rows(db, outcome.succeeded_ids)
    if matched:
        db.add(
            _bulk_audit_entry(
                action=AuditAction.BULK_PATCH,
                server=server,
                user=user,
                resource_type=payload.resource_type,
                filter_used={
                    "resource_type": payload.resource_type,
                    "rule": payload.rule,
                    "patch_template": f"{payload.resource_type}/{payload.rule}",
                },
                matched=matched,
                outcome=outcome,
                reason=payload.reason,
                elapsed=elapsed,
            )
        )
    await db.commit()

    return _bulk_result(matched, outcome, elapsed)


# ---------------------------------------------------------------------------
# PATCH /resources/{server_id}/{resource_type}/{resource_id}
# ---------------------------------------------------------------------------
@router.patch(
    "/resources/{server_id}/{resource_type}/{resource_id}",
    response_model=ActionResult,
)
async def patch_resource(
    resource_type: str,
    resource_id: str,
    payload: PatchRequest,
    server: FhirServer = Depends(server_access(UserRole.editor.value)),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Apply JSON Patch operations (RFC 6902) to a FHIR resource.
    Content-Type: application/json-patch+json
    """
    auth_config = server.auth_config or {}
    base_url = str(server.base_url).rstrip("/")

    patch_body = [
        op.model_dump(by_alias=True, exclude_none=True) for op in payload.operations
    ]

    resource_before: Optional[dict] = None
    fhir_status: Optional[str] = None
    status = AuditStatus.SUCCESS
    error_message: Optional[str] = None

    timeout = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
    auth = build_httpx_auth(auth_config)
    async with httpx.AsyncClient(timeout=timeout, auth=auth) as client:
        try:
            resource_before, etag = await _fetch_resource_with_etag(
                base_url,
                resource_type,
                resource_id,
                client,
            )
            if resource_before is None:
                status = AuditStatus.FAILED
                error_message = "Resource not found on FHIR server"
                fhir_status = "404"
            else:
                headers = {
                    "Content-Type": "application/json-patch+json",
                    "Accept": "application/fhir+json",
                }
                if etag:
                    headers["If-Match"] = etag

                url = f"{base_url}/{resource_type}/{resource_id}"
                resp = await client.patch(url, json=patch_body, headers=headers)
                fhir_status = str(resp.status_code)

                if resp.status_code in (200, 201):
                    inv = await _find_invalid_resource(
                        server.id, resource_type, resource_id, db
                    )
                    if inv:
                        await db.delete(inv)
                else:
                    status = AuditStatus.FAILED
                    error_message = (
                        f"FHIR server returned {resp.status_code}: {resp.text[:300]}"
                    )
        except httpx.HTTPError as exc:
            status = AuditStatus.FAILED
            error_message = str(exc)[:500]
            logger.error("PATCH failed for %s/%s: %s", resource_type, resource_id, exc)

    inv_for_link = await _find_invalid_resource(
        server.id, resource_type, resource_id, db
    )

    audit = AuditLog(
        server_id=server.id,
        server_base_url=base_url,
        resource_type=resource_type,
        resource_id=resource_id,
        invalid_resource_id=inv_for_link.id if inv_for_link else None,
        action=AuditAction.PATCH,
        fhir_request_payload=patch_body,
        fhir_response_status=fhir_status,
        resource_before=resource_before,
        status=status,
        error_message=error_message,
        reason=payload.reason,
        actor_id=user.id,
        executed_at=datetime.now(timezone.utc),
    )
    db.add(audit)
    await db.commit()
    await db.refresh(audit)

    return ActionResult(
        id=audit.id,
        action=audit.action.value,
        status=audit.status.value,
        resource_type=resource_type,
        resource_id=resource_id,
        fhir_response_status=fhir_status,
        error_message=error_message,
        executed_at=audit.executed_at,
    )


# ---------------------------------------------------------------------------
# GET /audit-log
# ---------------------------------------------------------------------------
@router.get("/audit-log", response_model=PaginatedAuditLog)
async def list_audit_log(
    skip: int = 0,
    limit: int = 50,
    server_id: Optional[UUID] = None,
    resource_type: Optional[str] = None,
    action: Optional[AuditAction] = None,
    status_filter: Optional[AuditStatus] = None,
    actor_id: Optional[UUID] = None,
    _: User = Depends(require_role(UserRole.admin.value)),
    db: AsyncSession = Depends(get_db),
):
    """Audit log (admin only)."""
    filters = []
    if server_id:
        filters.append(AuditLog.server_id == server_id)
    if resource_type:
        filters.append(AuditLog.resource_type == resource_type)
    if action:
        filters.append(AuditLog.action == action)
    if status_filter:
        filters.append(AuditLog.status == status_filter)
    if actor_id:
        filters.append(AuditLog.actor_id == actor_id)

    where_clause = and_(*filters) if filters else None

    count_stmt = select(func.count(AuditLog.id))
    if where_clause is not None:
        count_stmt = count_stmt.where(where_clause)
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = select(AuditLog).order_by(desc(AuditLog.executed_at))
    if where_clause is not None:
        stmt = stmt.where(where_clause)
    stmt = stmt.offset(skip).limit(min(limit, 500))
    rows = (await db.execute(stmt)).scalars().all()

    return PaginatedAuditLog(
        total=total,
        skip=skip,
        limit=limit,
        items=[AuditLogListItem.model_validate(r) for r in rows],
    )


# ---------------------------------------------------------------------------
# GET /resources/fix-templates
# ---------------------------------------------------------------------------
@router.get("/resources/fix-templates", response_model=list[FixableTemplate])
async def list_fix_templates():
    """All (resource_type, rule) combos the frontend may offer a one-click fix for."""
    return [FixableTemplate(**t) for t in list_templates()]


# ---------------------------------------------------------------------------
# POST /resources/{server_id}/{resource_type}/{resource_id}/auto-fix
# ---------------------------------------------------------------------------
@router.post(
    "/resources/{server_id}/{resource_type}/{resource_id}/auto-fix",
    response_model=ActionResult,
)
async def auto_fix_resource(
    resource_type: str,
    resource_id: str,
    payload: Optional[AutoFixRequest] = None,
    server: FhirServer = Depends(server_access(UserRole.editor.value)),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Apply every available template for the rules this resource actually violates,
    accumulated into a single PATCH. Backend is authoritative: it reads the rules
    from invalid_resources, not from the client.
    Returns 400 if none of the resource's rules has a template.
    """
    auth_config = server.auth_config or {}
    base_url = str(server.base_url).rstrip("/")

    inv = await _find_invalid_resource(server.id, resource_type, resource_id, db)
    if inv is None:
        raise HTTPException(
            status_code=404, detail="No invalid_resources entry for this resource"
        )

    rules = {
        i.get("rule")
        for i in (inv.metrics or {}).get("issues_detail", [])
        if i.get("rule")
    }
    fixable_rules = [r for r in rules if has_template(resource_type, r)]
    if not fixable_rules:
        raise HTTPException(
            status_code=400,
            detail=(
                f"No patch template for any rule on {resource_type}/{resource_id}. "
                "Use delete instead."
            ),
        )

    resource_before: Optional[dict] = None
    fhir_status: Optional[str] = None
    status = AuditStatus.SUCCESS
    error_message: Optional[str] = None
    patch_body: list[dict] = []

    timeout = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
    auth = build_httpx_auth(auth_config)
    async with httpx.AsyncClient(timeout=timeout, auth=auth) as client:
        try:
            resource_before, etag = await _fetch_resource_with_etag(
                base_url, resource_type, resource_id, client
            )
            if resource_before is None:
                status = AuditStatus.FAILED
                error_message = "Resource not found on FHIR server"
                fhir_status = "404"
            else:
                for rule in fixable_rules:
                    patch_body.extend(
                        get_patch_template(
                            resource_type, rule, resource=resource_before
                        )
                        or []
                    )
                if not patch_body:
                    status = AuditStatus.FAILED
                    error_message = "Templates produced no operations (already clean?)"
                else:
                    headers = {
                        "Content-Type": "application/json-patch+json",
                        "Accept": "application/fhir+json",
                    }
                    if etag:
                        headers["If-Match"] = etag
                    url = f"{base_url}/{resource_type}/{resource_id}"
                    resp = await client.patch(url, json=patch_body, headers=headers)
                    fhir_status = str(resp.status_code)
                    if resp.status_code in (200, 201):
                        await db.delete(inv)
                    else:
                        status = AuditStatus.FAILED
                        error_message = f"FHIR server returned {resp.status_code}: {resp.text[:300]}"
        except httpx.HTTPError as exc:
            status = AuditStatus.FAILED
            error_message = str(exc)[:500]
            logger.error(
                "AUTO-FIX failed for %s/%s: %s", resource_type, resource_id, exc
            )

    audit = AuditLog(
        server_id=server.id,
        server_base_url=base_url,
        resource_type=resource_type,
        resource_id=resource_id,
        invalid_resource_id=inv.id,
        action=AuditAction.PATCH,
        fhir_request_payload=patch_body or None,
        fhir_response_status=fhir_status,
        resource_before=resource_before,
        status=status,
        error_message=error_message,
        reason=payload.reason if payload else None,
        actor_id=user.id,
        executed_at=datetime.now(timezone.utc),
    )
    db.add(audit)
    await db.commit()
    await db.refresh(audit)

    return ActionResult(
        id=audit.id,
        action=audit.action.value,
        status=audit.status.value,
        resource_type=resource_type,
        resource_id=resource_id,
        fhir_response_status=fhir_status,
        error_message=error_message,
        executed_at=audit.executed_at,
    )


# ---------------------------------------------------------------------------
# GET /audit-log/{audit_id}
# ---------------------------------------------------------------------------
@router.get("/audit-log/{audit_id}", response_model=AuditLogDetail)
async def get_audit_log(
    audit_id: UUID,
    _: User = Depends(require_role(UserRole.admin.value)),
    db: AsyncSession = Depends(get_db),
):
    row = (
        await db.execute(select(AuditLog).where(AuditLog.id == audit_id))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Audit log entry not found")

    return AuditLogDetail(
        id=row.id,
        server_id=row.server_id,
        server_base_url=row.server_base_url,
        resource_type=row.resource_type,
        resource_id=row.resource_id,
        invalid_resource_id=row.invalid_resource_id,
        action=row.action.value,
        fhir_request_payload=row.fhir_request_payload,
        fhir_response_status=row.fhir_response_status,
        resource_before=row.resource_before,
        status=row.status.value,
        error_message=row.error_message,
        reason=row.reason,
        actor_id=row.actor_id,
        executed_at=row.executed_at,
    )
