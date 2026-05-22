"""Schemas for resource modification endpoints."""

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PatchOperation(BaseModel):
    """Single JSON Patch operation per RFC 6902."""

    op: Literal["add", "remove", "replace", "move", "copy", "test"]
    path: str
    value: Optional[Any] = None
    from_: Optional[str] = Field(default=None, alias="from")

    model_config = ConfigDict(populate_by_name=True)


class PatchRequest(BaseModel):
    operations: list[PatchOperation]
    reason: Optional[str] = None


class DeleteRequest(BaseModel):
    reason: Optional[str] = None


class ActionResult(BaseModel):
    id: UUID
    action: str
    status: str
    resource_type: str
    resource_id: str
    fhir_response_status: Optional[str] = None
    error_message: Optional[str] = None
    executed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogListItem(BaseModel):
    id: UUID
    server_id: UUID
    resource_type: str
    resource_id: str
    action: str
    status: str
    error_message: Optional[str] = None
    executed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedAuditLog(BaseModel):
    total: int
    skip: int
    limit: int
    items: list[AuditLogListItem]


class BulkDeleteRequest(BaseModel):
    """Filter criteria for bulk-deleting invalid resources from the FHIR server."""

    server_id: UUID
    resource_type: Optional[str] = None
    rule: Optional[str] = None
    severity: Optional[str] = None
    dry_run: bool = False
    reason: Optional[str] = None


class BulkActionError(BaseModel):
    resource_type: str
    resource_id: str
    error: str


class BulkActionResult(BaseModel):
    matched: int
    succeeded: int
    failed: int
    dry_run: bool
    elapsed_seconds: float
    errors: list[BulkActionError] = []
