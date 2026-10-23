"""Audit log for FHIR resource modifications executed by Verity."""

from typing import Any


import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    JSON,
    Enum as SQLEnum,
    ForeignKey,
    DateTime,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, TimestampMixin


class AuditAction(str, enum.Enum):
    DELETE = "DELETE"
    PATCH = "PATCH"
    # One summary row per bulk operation instead of one row per resource
    BULK_DELETE = "BULK_DELETE"
    BULK_PATCH = "BULK_PATCH"
    # Changes to Verity itself rather than to a FHIR resource
    SERVER_DELETE = "SERVER_DELETE"
    SERVER_AUTH_CHANGE = "SERVER_AUTH_CHANGE"
    SERVER_SHARE = "SERVER_SHARE"
    SERVER_UNSHARE = "SERVER_UNSHARE"
    USER_ROLE_CHANGE = "USER_ROLE_CHANGE"


class AuditStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"


class AuditLog(Base, TimestampMixin):
    """One row per modification of a FHIR resource, a server or a user's role."""

    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Target. Set to NULL when the server is deleted so its history survives;
    # server_base_url still identifies it.
    server_id = Column(
        UUID(as_uuid=True),
        ForeignKey("fhir_servers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    server_base_url = Column(String, nullable=True)  # NULL for USER_ROLE_CHANGE
    resource_type = Column(String(100), nullable=False, index=True)
    resource_id = Column(String, nullable=False, index=True)

    # Optional links to validation context
    triggering_run_id = Column(UUID(as_uuid=True), nullable=True)
    invalid_resource_id = Column(UUID(as_uuid=True), nullable=True)

    # Action
    action = Column(SQLEnum(AuditAction), nullable=False)
    fhir_request_payload = Column(JSON, nullable=True)  # patch body for PATCH
    fhir_response_status = Column(String, nullable=True)

    # Resource snapshot BEFORE modification — for forensics / rollback
    resource_before = Column[Any](JSON, nullable=True)

    # Outcome
    status = Column(SQLEnum(AuditStatus), nullable=False)
    error_message = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)

    # Who triggered this
    actor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    executed_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
