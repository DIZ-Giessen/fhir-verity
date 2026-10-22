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
    """Patch Request Schemas"""

    operations: list[PatchOperation]
    reason: Optional[str] = None


class DeleteRequest(BaseModel):
    """Delete Request Schemas"""

    reason: Optional[str] = None


class ActionResult(BaseModel):
    """Aktion Result Schemas"""

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
    server_id: Optional[UUID] = None
    server_base_url: str
    resource_type: str
    resource_id: str
    action: str
    status: str
    error_message: Optional[str] = None
    actor_id: Optional[UUID] = None
    executed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedAuditLog(BaseModel):
    """Pagination for AuditLog"""

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
    """Model for a Aktion Error"""

    resource_type: str
    resource_id: str
    error: str


class BulkActionResult(BaseModel):
    """Model for a Aktion Result"""

    matched: int
    succeeded: int
    failed: int
    dry_run: bool
    elapsed_seconds: float
    errors: list[BulkActionError] = []


class BulkFixRequest(BaseModel):
    """Apply the predefined patch template for a (resource_type, rule) combo."""

    server_id: UUID
    resource_type: str
    rule: str
    dry_run: bool = False
    reason: Optional[str] = None


class FixableTemplate(BaseModel):
    """Model for a Fixable Template"""

    resource_type: str
    rule: str


class AutoFixRequest(BaseModel):
    """Model for a Auto Fix Request"""

    reason: Optional[str] = None


class AuditLogDetail(BaseModel):
    id: UUID
    server_id: Optional[UUID] = None
    server_base_url: str
    resource_type: str
    resource_id: str
    invalid_resource_id: Optional[UUID] = None
    action: str
    fhir_request_payload: Optional[Any] = None
    fhir_response_status: Optional[str] = None
    resource_before: Optional[Any] = None
    status: str
    error_message: Optional[str] = None
    reason: Optional[str] = None
    executed_at: datetime
