"""Endpoints to delete or patch FHIR resources on the source server."""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
import asyncio
from time import monotonic

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, desc, func, select, delete
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
from app.models.invalid_resource import InvalidResource
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
    Otherwise: deletes each matched resource on the FHIR server in parallel
    (max 20 concurrent), removes successful entries from invalid_resources,
    and writes one audit log entry per attempt.
    """
    server = await load_server_scoped(payload.server_id, user, db)
    auth_config = server.auth_config or {}
    base_url = str(server.base_url).rstrip("/")

    base_filters = [InvalidResource.server_id == payload.server_id]
    if payload.resource_type:
        base_filters.append(InvalidResource.resource_type == payload.resource_type)

    stmt = select(InvalidResource).where(and_(*base_filters))
    rows = (await db.execute(stmt)).scalars().all()

    if payload.rule or payload.severity:
        filtered = []
        for row in rows:
            issues = (row.metrics or {}).get("issues_detail", [])
            ok = True
            if payload.rule:
                ok = ok and any(i.get("rule") == payload.rule for i in issues)
            if payload.severity:
                ok = ok and any(i.get("severity") == payload.severity for i in issues)
            if ok:
                filtered.append(row)
        rows = filtered

    matched = len(rows)

    if payload.dry_run:
        return BulkActionResult(
            matched=matched,
            succeeded=0,
            failed=0,
            dry_run=True,
            elapsed_seconds=0.0,
        )

    start = monotonic()
    semaphore = asyncio.Semaphore(20)
    audit_entries: list[AuditLog] = []
    succeeded_invalid_ids: list = []
    errors: list[BulkActionError] = []

    timeout = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
    auth = build_httpx_auth(auth_config)
    async with httpx.AsyncClient(timeout=timeout, auth=auth) as client:

        async def delete_one(row: InvalidResource):
            resource_before = None
            fhir_status: Optional[str] = None
            audit_status = AuditStatus.SUCCESS
            error_message: Optional[str] = None

            async with semaphore:
                try:
                    resource_before, etag = await _fetch_resource_with_etag(
                        base_url,
                        row.resource_type,
                        row.resource_id,
                        client,
                    )
                    if resource_before is None:
                        audit_status = AuditStatus.FAILED
                        error_message = "Resource not found on FHIR server"
                        fhir_status = "404"
                    else:
                        headers = {"Accept": "application/fhir+json"}
                        if etag:
                            headers["If-Match"] = etag
                        url = f"{base_url}/{row.resource_type}/{row.resource_id}"
                        resp = await client.delete(url, headers=headers)
                        fhir_status = str(resp.status_code)
                        if resp.status_code not in (200, 204):
                            audit_status = AuditStatus.FAILED
                            error_message = (
                                f"FHIR server returned {resp.status_code}: "
                                f"{resp.text[:300]}"
                            )
                except Exception as exc:
                    audit_status = AuditStatus.FAILED
                    error_message = str(exc)[:500]

            audit = AuditLog(
                server_id=payload.server_id,
                server_base_url=base_url,
                resource_type=row.resource_type,
                resource_id=row.resource_id,
                invalid_resource_id=row.id,
                action=AuditAction.DELETE,
                fhir_request_payload=None,
                fhir_response_status=fhir_status,
                resource_before=resource_before,
                status=audit_status,
                error_message=error_message,
                reason=payload.reason,
                actor_id=user.id,
                executed_at=datetime.now(timezone.utc),
            )
            audit_entries.append(audit)

            if audit_status == AuditStatus.SUCCESS:
                succeeded_invalid_ids.append(row.id)
            else:
                errors.append(
                    BulkActionError(
                        resource_type=row.resource_type,
                        resource_id=row.resource_id,
                        error=error_message or "unknown error",
                    )
                )

        await asyncio.gather(*[delete_one(row) for row in rows])

    db.add_all(audit_entries)
    if succeeded_invalid_ids:
        await db.execute(
            delete(InvalidResource).where(InvalidResource.id.in_(succeeded_invalid_ids))
        )
    await db.commit()

    elapsed = monotonic() - start

    return BulkActionResult(
        matched=matched,
        succeeded=len(succeeded_invalid_ids),
        failed=len(errors),
        dry_run=False,
        elapsed_seconds=round(elapsed, 2),
        errors=errors[:50],
    )


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
    Returns 400 if no template exists — in that case use bulk-delete instead,
    or wait for the LLM assistant (Block 3) to generate context-aware fixes.
    """
    if not has_template(payload.resource_type, payload.rule):
        raise HTTPException(
            status_code=400,
            detail=(
                f"No patch template available for "
                f"{payload.resource_type}/{payload.rule}. "
                f"Either use bulk-delete, or wait for the LLM assistant."
            ),
        )

    server = await load_server_scoped(payload.server_id, user, db)
    auth_config = server.auth_config or {}
    base_url = str(server.base_url).rstrip("/")

    stmt = select(InvalidResource).where(
        InvalidResource.server_id == payload.server_id,
        InvalidResource.resource_type == payload.resource_type,
    )
    rows = (await db.execute(stmt)).scalars().all()

    filtered = []
    for row in rows:
        issues = (row.metrics or {}).get("issues_detail", [])
        if any(i.get("rule") == payload.rule for i in issues):
            filtered.append(row)
    rows = filtered

    matched = len(rows)

    if payload.dry_run:
        return BulkActionResult(
            matched=matched,
            succeeded=0,
            failed=0,
            dry_run=True,
            elapsed_seconds=0.0,
        )

    start = monotonic()
    semaphore = asyncio.Semaphore(20)
    audit_entries: list[AuditLog] = []
    succeeded_invalid_ids: list = []
    errors: list[BulkActionError] = []

    auth = build_httpx_auth(auth_config)
    timeout = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
    async with httpx.AsyncClient(timeout=timeout, auth=auth) as client:

        async def patch_one(row: InvalidResource):
            resource_before = None
            fhir_status: Optional[str] = None
            audit_status = AuditStatus.SUCCESS
            error_message: Optional[str] = None
            patch_body: list[dict] = []

            async with semaphore:
                try:
                    resource_before, etag = await _fetch_resource_with_etag(
                        base_url,
                        row.resource_type,
                        row.resource_id,
                        client,
                    )
                    if resource_before is None:
                        audit_status = AuditStatus.FAILED
                        error_message = "Resource not found on FHIR server"
                        fhir_status = "404"
                    else:
                        patch_body = (
                            get_patch_template(
                                payload.resource_type,
                                payload.rule,
                                resource=resource_before,
                            )
                            or []
                        )

                        if not patch_body:
                            audit_status = AuditStatus.FAILED
                            error_message = (
                                "Template produced no operations "
                                "(resource may already be clean)"
                            )
                        else:
                            headers = {
                                "Content-Type": "application/json-patch+json",
                                "Accept": "application/fhir+json",
                            }
                            if etag:
                                headers["If-Match"] = etag
                            url = f"{base_url}/{row.resource_type}/{row.resource_id}"
                            resp = await client.patch(
                                url,
                                json=patch_body,
                                headers=headers,
                            )
                            fhir_status = str(resp.status_code)
                            if resp.status_code not in (200, 201):
                                audit_status = AuditStatus.FAILED
                                error_message = (
                                    f"FHIR server returned {resp.status_code}: "
                                    f"{resp.text[:300]}"
                                )
                except Exception as exc:
                    audit_status = AuditStatus.FAILED
                    error_message = str(exc)[:500]

            audit = AuditLog(
                server_id=payload.server_id,
                server_base_url=base_url,
                resource_type=row.resource_type,
                resource_id=row.resource_id,
                invalid_resource_id=row.id,
                action=AuditAction.PATCH,
                fhir_request_payload=patch_body if patch_body else None,
                fhir_response_status=fhir_status,
                resource_before=resource_before,
                status=audit_status,
                error_message=error_message,
                reason=payload.reason,
                actor_id=user.id,
                executed_at=datetime.now(timezone.utc),
            )
            audit_entries.append(audit)

            if audit_status == AuditStatus.SUCCESS:
                succeeded_invalid_ids.append(row.id)
            else:
                errors.append(
                    BulkActionError(
                        resource_type=row.resource_type,
                        resource_id=row.resource_id,
                        error=error_message or "unknown error",
                    )
                )

        await asyncio.gather(*[patch_one(row) for row in rows])

    db.add_all(audit_entries)
    if succeeded_invalid_ids:
        await db.execute(
            delete(InvalidResource).where(InvalidResource.id.in_(succeeded_invalid_ids))
        )
    await db.commit()

    elapsed = monotonic() - start

    return BulkActionResult(
        matched=matched,
        succeeded=len(succeeded_invalid_ids),
        failed=len(errors),
        dry_run=False,
        elapsed_seconds=round(elapsed, 2),
        errors=errors[:50],
    )


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
    action: Optional[str] = None,
    status_filter: Optional[str] = None,
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
    stmt = stmt.offset(skip).limit(limit)
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
