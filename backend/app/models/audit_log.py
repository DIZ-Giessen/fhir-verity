"""Audit log for FHIR resource modifications executed by Verity."""

from typing import Any


import uuid
import enum
from datetime import datetime

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


class AuditStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"


class AuditLog(Base, TimestampMixin):
    """One row per modification attempt on a FHIR resource."""

    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Target
    server_id = Column(
        UUID(as_uuid=True),
        ForeignKey("fhir_servers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    server_base_url = Column(String, nullable=False)
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

    # Who triggered this (for when auth is added later)
    actor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    executed_at = Column(
        DateTime(timezone=True),
        default=datetime.now,
        nullable=False,
    )
